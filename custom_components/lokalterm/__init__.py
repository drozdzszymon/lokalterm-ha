from __future__ import annotations

import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    CONF_LISTEN_HOST,
    CONF_LISTEN_PORT,
    CONF_DEVID,
    CONF_DEVPIN,
)
from .coordinator import EltermLocalCfg, EltermLocalServer

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "number", "select", "climate", "switch"]
THROTTLE_SECONDS = 2.0

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    coordinator = DataUpdateCoordinator(
        hass,
        logger=_LOGGER,
        name=f"{DOMAIN}_{entry.entry_id}",
        update_method=None,
        update_interval=None,
    )

    last_publish: float = 0.0
    latest_obj: dict[str, Any] | None = None
    scheduled_handle = None

    def _publish_latest() -> None:
        nonlocal last_publish, scheduled_handle, latest_obj
        scheduled_handle = None
        if latest_obj is None:
            return
        last_publish = time.monotonic()
        coordinator.async_set_updated_data(latest_obj)

    def _schedule_publish(delay: float) -> None:
        nonlocal scheduled_handle
        if scheduled_handle is not None:
            return
        if delay < 0:
            delay = 0
        scheduled_handle = hass.loop.call_later(delay, _publish_latest)

    def on_status(obj: dict) -> None:
        nonlocal latest_obj, last_publish
        latest_obj = obj
        now = time.monotonic()

        if last_publish == 0.0:
            hass.loop.call_soon_threadsafe(_publish_latest)
            return

        elapsed = now - last_publish
        if elapsed >= THROTTLE_SECONDS:
            hass.loop.call_soon_threadsafe(_publish_latest)
        else:
            hass.loop.call_soon_threadsafe(_schedule_publish, THROTTLE_SECONDS - elapsed)

    server = EltermLocalServer(
        hass,
        EltermLocalCfg(
            listen_host=entry.data[CONF_LISTEN_HOST],
            listen_port=int(entry.data[CONF_LISTEN_PORT]),
            devid=entry.data[CONF_DEVID],
            devpin=entry.data[CONF_DEVPIN],
        ),
        on_status=on_status,
    )

    await server.start()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "server": server,
        "devid": entry.data[CONF_DEVID],
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        server = hass.data[DOMAIN][entry.entry_id].get("server")
        if server:
            # Tutaj można by dodać metodę stop() do serwera, jeśli potrzebna
            pass
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok