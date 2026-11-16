from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_DEVID,
    CONF_DEVPIN,
    CONF_LISTEN_HOST,
    CONF_LISTEN_PORT,
    DEFAULT_LISTEN_HOST,
    DEFAULT_LISTEN_PORT,
    DOMAIN,
    THROTTLE_SECONDS,
)
from .coordinator import EltermLocalCfg, EltermLocalServer

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.CLIMATE,
    Platform.SWITCH,
]


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _create_coordinator(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> DataUpdateCoordinator[dict[str, Any] | None]:
    try:
        return DataUpdateCoordinator(
            hass,
            logger=_LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_method=None,
            update_interval=None,
        )
    except TypeError:
        return DataUpdateCoordinator(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_method=None,
            update_interval=None,
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    cfg_source = {**entry.data, **entry.options}
    listen_host = str(cfg_source.get(CONF_LISTEN_HOST, DEFAULT_LISTEN_HOST)).strip()
    listen_port = int(cfg_source.get(CONF_LISTEN_PORT, DEFAULT_LISTEN_PORT))
    devid = str(cfg_source[CONF_DEVID])
    devpin = str(cfg_source[CONF_DEVPIN])

    coordinator = _create_coordinator(hass, entry)

    last_publish: float = 0.0
    latest_obj: dict[str, Any] | None = None
    scheduled_handle: asyncio.TimerHandle | None = None
    unloaded = False

    @callback
    def _cancel_timer() -> None:
        nonlocal scheduled_handle
        if scheduled_handle is not None:
            scheduled_handle.cancel()
            scheduled_handle = None

    @callback
    def _publish_latest() -> None:
        nonlocal last_publish, scheduled_handle
        scheduled_handle = None
        if unloaded or latest_obj is None:
            return
        last_publish = time.monotonic()
        coordinator.async_set_updated_data(latest_obj)

    @callback
    def _handle_status_on_loop(obj: dict[str, Any], immediate: bool) -> None:
        nonlocal latest_obj, scheduled_handle
        if unloaded:
            return

        latest_obj = obj
        now = time.monotonic()

        if immediate or coordinator.data is None or last_publish == 0.0:
            _cancel_timer()
            _publish_latest()
            return

        elapsed = now - last_publish
        if elapsed >= THROTTLE_SECONDS:
            _cancel_timer()
            _publish_latest()
        elif scheduled_handle is None:
            delay = max(0.0, THROTTLE_SECONDS - elapsed)
            scheduled_handle = hass.loop.call_later(delay, _publish_latest)

    def on_status(obj: dict[str, Any], *, immediate: bool = False) -> None:
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        if running_loop is hass.loop:
            _handle_status_on_loop(obj, immediate)
        else:
            hass.loop.call_soon_threadsafe(_handle_status_on_loop, obj, immediate)

    server = EltermLocalServer(
        hass,
        EltermLocalCfg(
            listen_host=listen_host,
            listen_port=listen_port,
            devid=devid,
            devpin=devpin,
        ),
        on_status=on_status,
        get_current_state=lambda: coordinator.data,
    )

    try:
        await server.start()
    except OSError as err:
        _cancel_timer()
        raise ConfigEntryNotReady(
            f"Nie udało się uruchomić serwera TCP na {listen_host}:{listen_port}: {err}"
        ) from err

    async def _async_stop_on_ha_shutdown(_event: Event) -> None:
        nonlocal unloaded
        unloaded = True
        _cancel_timer()
        await server.stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop_on_ha_shutdown)
    )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    def _cleanup_timers() -> None:
        nonlocal unloaded
        unloaded = True
        _cancel_timer()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "server": server,
        "devid": devid,
        "cleanup": _cleanup_timers,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry_data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        if entry_data:
            cleanup = entry_data.get("cleanup")
            if cleanup:
                cleanup()
            server: EltermLocalServer | None = entry_data.get("server")
            if server is not None:
                await server.stop()
    return unload_ok
