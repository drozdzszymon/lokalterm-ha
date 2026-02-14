from __future__ import annotations
from typing import Any

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


PRESET_NORMALNY = "Normalny"
PRESET_PRIORYTET = "Priorytet"


def _to_temp(value: Any) -> float | None:
    try:
        return int(value) / 100.0 if value is not None else None
    except Exception:
        return None


def _temp_to_wire(value_c: float) -> str:
    return str(int(round(value_c * 100)))


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            EltermCoClimate(data["coordinator"], data["server"], data["devid"], entry.title),
            EltermCwuClimate(data["coordinator"], data["server"], data["devid"], entry.title),
        ]
    )


class _BaseEltermClimate(CoordinatorEntity, ClimateEntity):
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator, server, devid: str, dev_name: str) -> None:
        super().__init__(coordinator)
        self._server = server
        self._devid = devid
        self._attr_device_info = {
            "identifiers": {(DOMAIN, devid)},
            "name": dev_name,
            "manufacturer": "Elterm",
            "model": "SKZP (serwer lokalny)",
        }

    @property
    def available(self) -> bool:
        return self.coordinator.data is not None


class EltermCoClimate(_BaseEltermClimate):
    _attr_name = "Termostat CO"
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def __init__(self, coordinator, server, devid: str, dev_name: str) -> None:
        super().__init__(coordinator, server, devid, dev_name)
        self._attr_suggested_object_id = "lokalterm_termostat_co"
        self._attr_unique_id = f"{devid}_climate"

    @property
    def current_temperature(self) -> float | None:
        return _to_temp((self.coordinator.data or {}).get("BoilerTempAct"))

    @property
    def target_temperature(self) -> float | None:
        return _to_temp((self.coordinator.data or {}).get("BoilerTempCmd"))

    @property
    def hvac_mode(self) -> HVACMode | None:
        mode = (self.coordinator.data or {}).get("CH1Mode")
        return HVACMode.OFF if mode == "Stop" else HVACMode.HEAT

    async def async_set_temperature(self, **kwargs) -> None:
        temp = kwargs.get("temperature")
        if temp is None:
            return
        await self._server.send_data_to_send({"BoilerTempCmd": _temp_to_wire(float(temp))})

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        mode = "Stop" if hvac_mode == HVACMode.OFF else "Still_On"
        await self._server.send_data_to_send({"CH1Mode": mode})


class EltermCwuClimate(_BaseEltermClimate):
    _attr_name = "Termostat CWU"
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_preset_modes = [PRESET_NORMALNY, PRESET_PRIORYTET]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE

    def __init__(self, coordinator, server, devid: str, dev_name: str) -> None:
        super().__init__(coordinator, server, devid, dev_name)
        self._attr_suggested_object_id = "lokalterm_termostat_cwu"
        self._attr_unique_id = f"{devid}_climate_cwu"

    @property
    def current_temperature(self) -> float | None:
        return _to_temp((self.coordinator.data or {}).get("DHWTempAct"))

    @property
    def target_temperature(self) -> float | None:
        return _to_temp((self.coordinator.data or {}).get("DHWTempCmd"))

    @property
    def hvac_mode(self) -> HVACMode | None:
        mode = (self.coordinator.data or {}).get("DHWMode")
        return HVACMode.OFF if mode == "Stop" else HVACMode.HEAT

    @property
    def preset_mode(self) -> str | None:
        mode = (self.coordinator.data or {}).get("DHWMode")
        if mode == "Priority":
            return PRESET_PRIORYTET
        return PRESET_NORMALNY

    async def async_set_temperature(self, **kwargs) -> None:
        temp = kwargs.get("temperature")
        if temp is None:
            return
        await self._server.send_data_to_send({"DHWTempCmd": _temp_to_wire(float(temp))})

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self._server.send_data_to_send({"DHWMode": "Stop"})
            return

        current_preset = self.preset_mode or PRESET_NORMALNY
        mode = "Priority" if current_preset == PRESET_PRIORYTET else "Still_On"
        await self._server.send_data_to_send({"DHWMode": mode})

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode not in self._attr_preset_modes:
            return
        mode = "Priority" if preset_mode == PRESET_PRIORYTET else "Still_On"
        await self._server.send_data_to_send({"DHWMode": mode})
