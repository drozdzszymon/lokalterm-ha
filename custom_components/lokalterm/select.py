from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


def _get_str(data: dict[str, Any], key: str, default: str | None = None) -> str | None:
    v = data.get(key)
    if v is None:
        return default
    return str(v)


@dataclass(frozen=True, kw_only=True)
class EltermSelectDescription(SelectEntityDescription):
    field: str
    map_to_wire: dict[str, Any]
    map_from_wire: dict[str, str]


CO_POWER_OPTIONS = ["33", "67", "100"]
CO_POWER_TO_STEP: dict[str, str] = {"33": "0", "67": "1", "100": "2"}
CO_STEP_TO_POWER = {"0": "33", "1": "67", "2": "100"}

CWU_MODE_OPTIONS = ["Włączony", "STOP", "PRIORYTET"]
CWU_MODE_TO_WIRE = {"Włączony": "Still_On", "STOP": "Stop", "PRIORYTET": "Priority"}
CWU_MODE_FROM_WIRE = {"Still_On": "Włączony", "Stop": "STOP", "Priority": "PRIORYTET"}


SELECTS: list[EltermSelectDescription] = [
    EltermSelectDescription(
        key="co_moc",
        name="CO Moc maksymalna",
        icon="mdi:flash",
        options=CO_POWER_OPTIONS,
        field="BuModulMax",
        map_to_wire=CO_POWER_TO_STEP,
        map_from_wire=CO_STEP_TO_POWER,
    ),
    EltermSelectDescription(
        key="cwu_tryb_pracy",
        name="CWU Tryb pracy",
        icon="mdi:water-boiler",
        options=CWU_MODE_OPTIONS,
        field="DHWMode",
        map_to_wire=CWU_MODE_TO_WIRE,
        map_from_wire=CWU_MODE_FROM_WIRE,
    ),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    server = hass.data[DOMAIN][entry.entry_id]["server"]
    devid = hass.data[DOMAIN][entry.entry_id]["devid"]
    dev_name = entry.title
    async_add_entities([EltermSelect(coordinator, server, devid, dev_name, desc) for desc in SELECTS])


class EltermSelect(CoordinatorEntity, SelectEntity):
    entity_description: EltermSelectDescription

    def __init__(self, coordinator, server, devid: str, dev_name: str, description: EltermSelectDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._server = server

        # Stabilny object_id -> entity_id z prefiksem lokalterm_
        self._attr_suggested_object_id = f"lokalterm_{description.key}"

        self._attr_unique_id = f"{devid}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, devid)},
            "name": dev_name,
            "manufacturer": "Elterm",
            "model": "SKZP (serwer lokalny)",
        }

    @property
    def available(self) -> bool:
        return self.coordinator.data is not None

    @property
    def current_option(self) -> str | None:
        data = self.coordinator.data or {}
        raw = _get_str(data, self.entity_description.field)
        if raw is None:
            return None
        return self.entity_description.map_from_wire.get(raw)

    async def async_select_option(self, option: str) -> None:
        if option not in self.entity_description.options:
            return

        data = self.coordinator.data or {}
        wire_value = self.entity_description.map_to_wire[option]
        fields = {self.entity_description.field: wire_value}

        await self._server.send_data_to_send(fields, base_state=dict(data))
