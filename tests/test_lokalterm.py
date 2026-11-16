from __future__ import annotations

import asyncio
import json
import socket
import time
from pathlib import Path
from typing import Any

import pytest
from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import AbortFlow, ConfigEntryNotReady
from homeassistant.helpers.selector import TextSelector, TextSelectorType

from custom_components.lokalterm import async_setup_entry, async_unload_entry
from custom_components.lokalterm.climate import (
    PRESET_NORMALNY,
    PRESET_PRIORYTET,
)
from custom_components.lokalterm.climate import (
    async_setup_entry as setup_climate,
)
from custom_components.lokalterm.config_flow import ConfigFlow, LokalTermOptionsFlow
from custom_components.lokalterm.const import (
    CONF_DEVID,
    CONF_DEVPIN,
    CONF_LISTEN_HOST,
    CONF_LISTEN_PORT,
    DOMAIN,
    MAX_LINE_BYTES,
)
from custom_components.lokalterm.coordinator import (
    EltermLocalCfg,
    EltermLocalServer,
    _decode_json_line,
    _mask_sensitive,
)
from custom_components.lokalterm.entity import (
    status_power_percent,
    temp_to_wire,
    to_energy_kwh,
    to_temp_celsius,
    values_match,
)
from custom_components.lokalterm.number import async_setup_entry as setup_numbers
from custom_components.lokalterm.select import async_setup_entry as setup_selects
from custom_components.lokalterm.sensor import async_setup_entry as setup_sensors
from custom_components.lokalterm.switch import async_setup_entry as setup_switches

COMPONENT_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "lokalterm"


def _free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _collect_nested_keys(obj: dict[str, Any], prefix: str = "") -> set[str]:
    keys: set[str] = set()
    for k, v in obj.items():
        path = f"{prefix}.{k}" if prefix else k
        keys.add(path)
        if isinstance(v, dict):
            keys |= _collect_nested_keys(v, path)
    return keys


# ---------------------------------------------------------------------------
# 1. Pure Helpers, Protocol Conversions & Edge Cases
# ---------------------------------------------------------------------------


def test_temperature_and_energy_conversions() -> None:
    assert to_temp_celsius("4550") == 45.5
    assert to_temp_celsius(2125) == 21.25
    assert to_temp_celsius(" 0000 ") == 0.0
    assert to_temp_celsius("-525") == -5.25
    assert to_temp_celsius(None) is None
    assert to_temp_celsius(True) is None
    assert to_temp_celsius("") is None
    assert to_temp_celsius("---") is None
    assert to_temp_celsius("nan") is None
    assert to_temp_celsius("inf") is None
    assert to_temp_celsius(float("-inf")) is None

    assert temp_to_wire(45.0, min_val=20.0, max_val=69.0) == "4500"
    assert temp_to_wire(5.0, min_val=20.0, max_val=69.0) == "2000"
    assert temp_to_wire(99.0, min_val=20.0, max_val=69.0) == "6900"
    with pytest.raises(ValueError):
        temp_to_wire(float("nan"))
    with pytest.raises(ValueError):
        temp_to_wire(float("inf"))

    assert to_energy_kwh("123.456") == 123.46
    assert to_energy_kwh(0) == 0.0
    assert to_energy_kwh(None) is None
    assert to_energy_kwh(False) is None
    assert to_energy_kwh("") is None
    assert to_energy_kwh("ERR") is None
    assert to_energy_kwh("nan") is None
    assert to_energy_kwh("inf") is None
    assert to_energy_kwh("-0.01") is None


def test_values_match_and_status_power_percent() -> None:
    assert values_match("4500", "4500") is True
    assert values_match(4500, "4500") is True
    assert values_match("0000", "0") is True
    assert values_match("0200", "200") is True
    assert values_match("4500.0", "4500") is True
    assert values_match("Still_On", "Still_On") is True
    assert values_match("Stop", "Still_On") is False
    assert values_match(None, "0") is False

    assert status_power_percent({"DevStatus": "ABC067XYZ"}) == 67
    assert status_power_percent({"DevStatus": "ABC999XYZ"}) == 100
    assert status_power_percent({"CH1Mode": "Stop", "DHWMode": "Stop"}) == 0
    assert status_power_percent({"CH1Mode": "Stop", "DHWMode": "Priority", "BuModulMax": "2"}) == 100
    assert status_power_percent({"CH1Mode": "Still_On", "BuModulMax": "0"}) == 33
    assert status_power_percent({"CH1Mode": "Still_On", "BuModulMax": "1"}) == 67
    assert status_power_percent({"CH1Mode": "Still_On", "BuModulMax": "invalid"}) is None


def test_decode_json_line_uart_glitch_resilience_and_masking() -> None:
    # Leading RS-485 transceiver glitch bytes (0xFF / 0x00 / prefix noise)
    raw = b'\xff\xfe\x00noise{"FrameType":"SkzpData","BoilerTempAct":"4200"}\r\n'
    parsed = _decode_json_line(raw)
    assert parsed == {"FrameType": "SkzpData", "BoilerTempAct": "4200"}

    # Non-dict JSON primitives must never return a non-dict object
    for primitive in (b"0\r\n", b"123\r\n", b"[1,2,3]\r\n", b'"str"\r\n', b"null\r\n", b"bad{\r\n"):
        assert _decode_json_line(primitive) is None

    original = {"FrameType": "DataToSend", "vId": "SECRET_ID", "vPin": "9999", "CH1Mode": "Stop"}
    masked = _mask_sensitive(original)
    assert masked["vId"] == "***"
    assert masked["vPin"] == "***"
    assert masked["CH1Mode"] == "Stop"
    assert original["vId"] == "SECRET_ID"


# ---------------------------------------------------------------------------
# 2. TCP Server Protocol, Debouncing, Multi-Field Queue & Concurrency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tcp_wire_format_rapid_slider_debounce_and_confirmation() -> None:
    loop = asyncio.get_running_loop()
    hass = HomeAssistant(loop)
    port = _free_tcp_port()
    updates: list[tuple[dict[str, Any], bool]] = []

    server = EltermLocalServer(
        hass,
        EltermLocalCfg("127.0.0.1", port, "DEV123", "PIN456"),
        on_status=lambda obj, immediate=False: updates.append((dict(obj), immediate)),
    )
    await server.start()

    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        # Boiler sends initial SkzpData frame
        init_frame = {
            "FrameType": "SkzpData",
            "BoilerTempAct": "4000",
            "BoilerTempCmd": "4000",
            "BoilerHist": "200",
            "CH1Mode": "Still_On",
        }
        writer.write(json.dumps(init_frame).encode("ascii") + b"\r\n")
        await writer.drain()
        await asyncio.sleep(0.05)
        assert len(updates) == 1
        assert updates[-1][0]["BoilerTempCmd"] == "4000"

        # Simulate rapid slider drag: 15 updates within ~15ms
        for temp_c in range(41, 56):
            await server.send_data_to_send({"BoilerTempCmd": str(temp_c * 100)})

        # Optimistic UI updated synchronously to final value 5500 with immediate=True
        assert updates[-1][0]["BoilerTempCmd"] == "5500"
        assert updates[-1][1] is True

        # Wait for 100ms debounce: ONLY ONE minimal single-field packet must arrive!
        raw_cmd = await asyncio.wait_for(reader.readline(), timeout=1.0)
        assert raw_cmd.endswith(b"\r\n")
        cmd_text = raw_cmd.decode("ascii").rstrip("\r\n")
        assert " " not in cmd_text  # compact separators=(",", ":")
        cmd = json.loads(cmd_text)
        assert list(cmd.keys()) == ["FrameType", "vId", "vPin", "BoilerTempCmd", "vToken"]
        assert cmd["FrameType"] == "DataToSend"
        assert cmd["vId"] == "DEV123"
        assert cmd["vPin"] == "PIN456"
        assert cmd["BoilerTempCmd"] == "5500"
        assert len(cmd["vToken"]) == 7

        # Ensure no duplicate flooded frames are queued behind it
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(reader.readline(), timeout=0.15)

        # Boiler confirms with zero-padded value "05500" -> confirmed without retry!
        confirm_frame = dict(init_frame, BoilerTempCmd="05500")
        writer.write(json.dumps(confirm_frame).encode("ascii") + b"\r\n")
        await writer.drain()
        await asyncio.sleep(0.18)

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(reader.readline(), timeout=0.12)

        writer.close()
        await writer.wait_closed()
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_multi_field_commands_preserved_as_minimal_single_field_frames() -> None:
    loop = asyncio.get_running_loop()
    hass = HomeAssistant(loop)
    port = _free_tcp_port()
    updates: list[dict[str, Any]] = []

    server = EltermLocalServer(
        hass,
        EltermLocalCfg("127.0.0.1", port, "DEV1", "PIN1"),
        on_status=lambda obj, immediate=False: updates.append(dict(obj)),
    )
    await server.start()

    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(
            b'{"FrameType":"SkzpData","CH1Mode":"Stop","BoilerTempCmd":"3500"}\r\n'
        )
        await writer.drain()
        await asyncio.sleep(0.05)

        # Two separate clicks back-to-back (formerly 2nd click wiped out 1st!)
        await server.send_data_to_send({"CH1Mode": "Still_On"})
        await server.send_data_to_send({"BoilerTempCmd": "4800"})

        # Both values must remain steady in Optimistic UI simultaneously
        assert updates[-1]["CH1Mode"] == "Still_On"
        assert updates[-1]["BoilerTempCmd"] == "4800"

        line1 = await asyncio.wait_for(reader.readline(), timeout=1.0)
        line2 = await asyncio.wait_for(reader.readline(), timeout=1.0)
        f1 = json.loads(line1.decode("ascii"))
        f2 = json.loads(line2.decode("ascii"))

        # Each frame is strictly minimal (1 command field per DataToSend packet)
        assert list(f1.keys()) == ["FrameType", "vId", "vPin", "CH1Mode", "vToken"]
        assert f1["CH1Mode"] == "Still_On"
        assert list(f2.keys()) == ["FrameType", "vId", "vPin", "BoilerTempCmd", "vToken"]
        assert f2["BoilerTempCmd"] == "4800"

        writer.close()
        await writer.wait_closed()
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_port_scanner_and_half_open_reconnect_do_not_break_writer() -> None:
    loop = asyncio.get_running_loop()
    hass = HomeAssistant(loop)
    port = _free_tcp_port()

    server = EltermLocalServer(
        hass,
        EltermLocalCfg("127.0.0.1", port, "DEV1", "PIN1"),
        on_status=lambda _obj, immediate=False: None,
    )
    await server.start()

    try:
        # Connection A: real boiler connects and sends SkzpData + oversized garbage line
        r_a, w_a = await asyncio.open_connection("127.0.0.1", port)
        w_a.write(b"X" * (MAX_LINE_BYTES + 2048) + b"\r\n")
        w_a.write(b'0\r\n{"FrameType":"SkzpData","CH1Mode":"Stop"}\r\n')
        await w_a.drain()
        await asyncio.sleep(0.08)

        # Connection B: LAN port scanner connects, sends garbage, and disconnects immediately
        _r_scan, w_scan = await asyncio.open_connection("127.0.0.1", port)
        w_scan.write(b"GET / HTTP/1.0\r\n\r\n")
        await w_scan.drain()
        w_scan.close()
        await w_scan.wait_closed()
        await asyncio.sleep(0.05)

        # Commands must STILL be delivered to Connection A!
        await server.send_data_to_send({"CH1Mode": "Still_On"})
        cmd_a = json.loads((await asyncio.wait_for(r_a.readline(), timeout=1.0)).decode("ascii"))
        assert cmd_a["CH1Mode"] == "Still_On"

        # Connection C: boiler reconnects on a new socket while A was half-open
        r_c, w_c = await asyncio.open_connection("127.0.0.1", port)
        w_c.write(b'{"FrameType":"SkzpData","CH1Mode":"Still_On"}\r\n')
        await w_c.drain()
        await asyncio.sleep(0.08)

        # Old connection A closing must NOT clear Connection C's active writer
        w_a.close()
        await w_a.wait_closed()
        await asyncio.sleep(0.05)

        await server.send_data_to_send({"CH1Mode": "Stop"})
        cmd_c = json.loads((await asyncio.wait_for(r_c.readline(), timeout=1.0)).decode("ascii"))
        assert cmd_c["CH1Mode"] == "Stop"

        w_c.close()
        await w_c.wait_closed()
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_pending_timeout_reverts_optimistic_ui(monkeypatch: pytest.MonkeyPatch) -> None:
    import custom_components.lokalterm.coordinator as coord_mod

    monkeypatch.setattr(coord_mod, "PENDING_TIMEOUT_SECONDS", 0.05)
    loop = asyncio.get_running_loop()
    hass = HomeAssistant(loop)
    port = _free_tcp_port()
    states: list[dict[str, Any]] = []

    server = EltermLocalServer(
        hass,
        EltermLocalCfg("127.0.0.1", port, "DEV1", "PIN1"),
        on_status=lambda obj, immediate=False: states.append(dict(obj)),
    )
    await server.start()

    try:
        _r, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(b'{"FrameType":"SkzpData","BoilerTempCmd":"4000"}\r\n')
        await writer.drain()
        await asyncio.sleep(0.03)

        await server.send_data_to_send({"BoilerTempCmd": "5000"})
        assert states[-1]["BoilerTempCmd"] == "5000"

        await asyncio.sleep(0.08)
        # Boiler still reports 4000 after timeout -> UI reverts cleanly to 4000
        writer.write(b'{"FrameType":"SkzpData","BoilerTempCmd":"4000"}\r\n')
        await writer.drain()
        await asyncio.sleep(0.05)
        assert states[-1]["BoilerTempCmd"] == "4000"

        writer.close()
        await writer.wait_closed()
    finally:
        await server.stop()


# ---------------------------------------------------------------------------
# 3. Integration Setup, Unload/Reload Port Reuse, Throttle vs Optimistic UI
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_setup_unload_reload_frees_port_and_optimistic_ui_bypasses_throttle() -> None:
    loop = asyncio.get_running_loop()
    hass = HomeAssistant(loop)
    port = _free_tcp_port()

    entry = ConfigEntry(
        entry_id="lt_1",
        title="Mój Kocioł",
        unique_id="BOILER_01",
        data={
            CONF_DEVID: "BOILER_01",
            CONF_DEVPIN: "1234",
            CONF_LISTEN_HOST: "127.0.0.1",
            CONF_LISTEN_PORT: port,
        },
    )
    hass.config_entries.add_entry(entry)

    assert await async_setup_entry(hass, entry) is True
    coord = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    srv: EltermLocalServer = hass.data[DOMAIN][entry.entry_id]["server"]

    _r, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(b'{"FrameType":"SkzpData","CH1Mode":"Stop","BoilerTempCmd":"4000"}\r\n')
    await writer.drain()
    await asyncio.sleep(0.05)
    assert coord.data is not None
    assert coord.data["CH1Mode"] == "Stop"

    # Second SkzpData within 2.0s throttle is deferred, NOT applied yet
    writer.write(b'{"FrameType":"SkzpData","CH1Mode":"Stop","BoilerTempCmd":"4100"}\r\n')
    await writer.drain()
    await asyncio.sleep(0.05)
    assert coord.data["BoilerTempCmd"] == "4000"

    # User click MUST bypass the 2.0s throttle with 0ms toggle-bounce latency!
    t0 = time.perf_counter()
    await srv.send_data_to_send({"CH1Mode": "Still_On"})
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    assert coord.data["CH1Mode"] == "Still_On"
    assert elapsed_ms < 50.0

    # Unload must close both active client socket and TCP listener so immediate reload works!
    assert await async_unload_entry(hass, entry) is True
    assert entry.entry_id not in hass.data[DOMAIN]

    # Reloading on the exact same port succeeds immediately without Address already in use
    assert await async_setup_entry(hass, entry) is True

    # Attempting to set up a second entry on the already-bound port raises ConfigEntryNotReady
    conflict_entry = ConfigEntry(
        entry_id="lt_conflict",
        data=dict(entry.data),
    )
    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, conflict_entry)

    assert await async_unload_entry(hass, entry) is True


# ---------------------------------------------------------------------------
# 4. All 5 Entity Platforms & HA 2026 Compatibility Contracts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_entities_states_ha2026_features_and_edge_cases() -> None:
    loop = asyncio.get_running_loop()
    hass = HomeAssistant(loop)
    port = _free_tcp_port()

    # Deliberately pass unique_id=None on ConfigEntry to verify switch.py uses devid safely!
    entry = ConfigEntry(
        entry_id="lt_ent",
        title="Piec Dom",
        unique_id=None,
        data={
            CONF_DEVID: "SKZP_99",
            CONF_DEVPIN: "4321",
            CONF_LISTEN_HOST: "127.0.0.1",
            CONF_LISTEN_PORT: port,
        },
    )
    await async_setup_entry(hass, entry)

    created: list[Any] = []
    for setup_fn in (setup_sensors, setup_numbers, setup_selects, setup_climate, setup_switches):
        await setup_fn(hass, entry, created.extend)

    assert len(created) == 13  # 4 sensors + 4 numbers + 2 selects + 2 climates + 1 switch

    # Before first frame, EVERY entity (including switch!) must be unavailable
    for ent in created:
        assert ent.available is False
        assert ent._attr_device_info["identifiers"] == {(DOMAIN, "SKZP_99")}

    by_uid = {ent._attr_unique_id: ent for ent in created}
    co_clim = by_uid["SKZP_99_climate"]
    cwu_clim = by_uid["SKZP_99_climate_cwu"]
    sw = by_uid["SKZP_99_co_enable"]
    temp_co_sensor = by_uid["SKZP_99_temp_wody_co"]
    temp_cwu_sensor = by_uid["SKZP_99_temp_wody_cwu"]
    energy_sensor = by_uid["SKZP_99_energia_licznik_kwh"]
    co_num = by_uid["SKZP_99_co_temperatura_zadana"]
    cwu_sel = by_uid["SKZP_99_cwu_tryb_pracy"]

    # HA 2025/2026 ClimateEntity TURN_ON / TURN_OFF contract + min/max/step
    for clim in (co_clim, cwu_clim):
        assert ClimateEntityFeature.TURN_ON in clim._attr_supported_features
        assert ClimateEntityFeature.TURN_OFF in clim._attr_supported_features
        assert clim._enable_turn_on_off_backwards_compatibility is False
        assert clim._attr_target_temperature_step == 1.0
    assert co_clim._attr_min_temp == 20.0
    assert cwu_clim._attr_min_temp == 30.0

    for sensor in (temp_co_sensor, temp_cwu_sensor):
        assert sensor.entity_description.device_class == SensorDeviceClass.TEMPERATURE
        assert sensor.entity_description.state_class == SensorStateClass.MEASUREMENT
        assert sensor.entity_description.native_unit_of_measurement == UnitOfTemperature.CELSIUS

    coord = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    # Missing DHWMode / CH1Mode / corrupt P033 must return None without crashing
    coord.async_set_updated_data({"FrameType": "SkzpData", "P033": "---"})
    assert co_clim.hvac_mode is None
    assert cwu_clim.hvac_mode is None
    assert cwu_clim.preset_mode is None
    assert energy_sensor.native_value is None
    assert sw.available is True
    assert sw.is_on is None

    # CWU preset memory across OFF -> ON transitions
    coord.async_set_updated_data(
        {
            "FrameType": "SkzpData",
            "CH1Mode": "Still_On",
            "BoilerTempAct": "4250",
            "BoilerTempCmd": "4500",
            "DHWMode": "Priority",
            "DHWTempAct": "4800",
            "DHWTempCmd": "5000",
            "P033": "152.349",
        }
    )
    assert cwu_clim.preset_mode == PRESET_PRIORYTET
    assert cwu_clim.hvac_mode == HVACMode.HEAT
    assert temp_co_sensor.native_value == 42.5
    assert temp_cwu_sensor.native_value == 48.0
    assert energy_sensor.native_value == 152.35
    assert cwu_sel.current_option == "PRIORYTET"

    # Turn CWU OFF -> turn CWU back ON -> remembers Priorytet!
    await cwu_clim.async_turn_off()
    assert cwu_clim.hvac_mode == HVACMode.OFF
    assert cwu_clim.preset_mode == PRESET_PRIORYTET
    await cwu_clim.async_turn_on()
    assert coord.data["DHWMode"] == "Priority"

    # Switch to Normalny preset
    await cwu_clim.async_set_preset_mode(PRESET_NORMALNY)
    assert coord.data["DHWMode"] == "Still_On"

    # Combined climate.set_temperature(hvac_mode=..., temperature=...) + out-of-range clamping
    await co_clim.async_set_temperature(**{ATTR_HVAC_MODE: HVACMode.OFF, ATTR_TEMPERATURE: 95.0})
    assert coord.data["CH1Mode"] == "Stop"
    assert coord.data["BoilerTempCmd"] == "6900"

    await co_num.async_set_native_value(10.0)
    assert coord.data["BoilerTempCmd"] == "2000"

    await async_unload_entry(hass, entry)


# ---------------------------------------------------------------------------
# 5. ConfigFlow, OptionsFlow, Selectors, Translations & Manifest Validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_config_flow_and_options_flow_validation_and_selectors() -> None:
    loop = asyncio.get_running_loop()
    hass = HomeAssistant(loop)
    free_port = _free_tcp_port()

    flow = ConfigFlow()
    flow.hass = hass

    # 1. Empty state (initial form) -> verify PASSWORD selector on vPin
    form = await flow.async_step_user(None)
    assert form["type"] == "form"
    schema_dict = form["data_schema"].schema
    pin_validators = [v for k, v in schema_dict.items() if k.schema == CONF_DEVPIN]
    assert len(pin_validators) == 1
    assert isinstance(pin_validators[0], TextSelector)
    assert pin_validators[0].config.type == TextSelectorType.PASSWORD

    # 2. Invalid host, port, and empty credentials -> inline errors + preserved input
    err_form = await flow.async_step_user(
        {
            "name": "Test",
            CONF_DEVID: "   ",
            CONF_DEVPIN: "",
            CONF_LISTEN_HOST: "bad host!",
            CONF_LISTEN_PORT: 70000,
        }
    )
    assert err_form["errors"] == {
        CONF_DEVID: "empty_devid",
        CONF_DEVPIN: "empty_devpin",
        CONF_LISTEN_HOST: "invalid_host",
        CONF_LISTEN_PORT: "invalid_port",
    }

    # 3. Port already bound by external service -> cannot_bind
    blocker = await asyncio.start_server(lambda _r, _w: None, "127.0.0.1", 0)
    busy_port = blocker.sockets[0].getsockname()[1]
    try:
        bind_err = await flow.async_step_user(
            {
                "name": "Test",
                CONF_DEVID: "ID_1",
                CONF_DEVPIN: "PIN_1",
                CONF_LISTEN_HOST: "127.0.0.1",
                CONF_LISTEN_PORT: float(busy_port),
            }
        )
        assert bind_err["errors"] == {CONF_LISTEN_PORT: "cannot_bind"}
    finally:
        blocker.close()
        await blocker.wait_closed()

    # 4. Valid creation (with float port from NumberSelector, e.g. 1088.0)
    created = await flow.async_step_user(
        {
            "name": " Kocioł CO ",
            CONF_DEVID: " ID_1 ",
            CONF_DEVPIN: " PIN_1 ",
            CONF_LISTEN_HOST: "127.0.0.1",
            CONF_LISTEN_PORT: float(free_port),
        }
    )
    assert created["type"] == "create_entry"
    assert created["title"] == "Kocioł CO"
    assert created["data"] == {
        CONF_DEVID: "ID_1",
        CONF_DEVPIN: "PIN_1",
        CONF_LISTEN_HOST: "127.0.0.1",
        CONF_LISTEN_PORT: free_port,
    }

    # Register entry and test duplicate unique_id + port_in_use + OptionsFlow
    entry = ConfigEntry(
        entry_id="e1",
        title=created["title"],
        unique_id="ID_1",
        data=created["data"],
    )
    hass.config_entries.add_entry(entry)
    await async_setup_entry(hass, entry)

    try:
        dup_flow = ConfigFlow()
        dup_flow.hass = hass
        with pytest.raises(AbortFlow):
            await dup_flow.async_step_user(
                {
                    "name": "Drugi",
                    CONF_DEVID: "ID_1",
                    CONF_DEVPIN: "PIN_2",
                    CONF_LISTEN_HOST: "127.0.0.1",
                    CONF_LISTEN_PORT: _free_tcp_port(),
                }
            )

        port_conflict_flow = ConfigFlow()
        port_conflict_flow.hass = hass
        conflict_res = await port_conflict_flow.async_step_user(
            {
                "name": "Drugi",
                CONF_DEVID: "ID_2",
                CONF_DEVPIN: "PIN_2",
                CONF_LISTEN_HOST: "0.0.0.0",
                CONF_LISTEN_PORT: free_port,
            }
        )
        assert conflict_res["errors"] == {CONF_LISTEN_PORT: "port_in_use"}

        # OptionsFlow allows updating PIN while keeping the SAME active port without false cannot_bind!
        opt_flow: LokalTermOptionsFlow = ConfigFlow.async_get_options_flow(entry)
        opt_flow.hass = hass
        opt_flow._config_entry = entry  # attached by HA runtime in production

        opt_init = await opt_flow.async_step_init(None)
        assert opt_init["type"] == "form"

        opt_saved = await opt_flow.async_step_init(
            {
                CONF_DEVPIN: "NEW_PIN_99",
                CONF_LISTEN_HOST: "127.0.0.1",
                CONF_LISTEN_PORT: float(free_port),
            }
        )
        assert opt_saved["type"] == "create_entry"
        assert opt_saved["data"][CONF_DEVPIN] == "NEW_PIN_99"
    finally:
        await async_unload_entry(hass, entry)


def test_manifest_hassfest_key_order_and_translations_parity() -> None:
    manifest_raw = (COMPONENT_DIR / "manifest.json").read_text(encoding="utf-8")
    manifest = json.loads(manifest_raw)
    keys = list(manifest.keys())
    assert keys[:2] == ["domain", "name"]
    assert keys[2:] == sorted(keys[2:])
    assert manifest["domain"] == "lokalterm"
    assert manifest["iot_class"] == "local_push"
    assert manifest["requirements"] == []
    assert manifest["version"] == "1.1.0"

    strings = json.loads((COMPONENT_DIR / "strings.json").read_text(encoding="utf-8"))
    pl = json.loads((COMPONENT_DIR / "translations" / "pl.json").read_text(encoding="utf-8"))
    en = json.loads((COMPONENT_DIR / "translations" / "en.json").read_text(encoding="utf-8"))

    strings_comparable = {k: v for k, v in strings.items() if k in ("config", "options")}
    assert _collect_nested_keys(strings_comparable) == _collect_nested_keys(pl)
    assert _collect_nested_keys(strings_comparable) == _collect_nested_keys(en)
