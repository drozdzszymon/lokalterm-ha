from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import EltermEntity


@dataclass(frozen=True, kw_only=True)
class EltermSelectDescription(SelectEntityDescription):
    field: str
    map_to_wire: dict[str, str]
    map_from_wire: dict[str, str]


CO_POWER_OPTIONS = ["33", "67", "100"]
CO_POWER_TO_STEP: dict[str, str] = {"33": "0", "67": "1", "100": "2"}
CO_STEP_TO_POWER: dict[str, str] = {"0": "33", "1": "67", "2": "100"}

CWU_MODE_OPTIONS = ["Włączony", "STOP", "PRIORYTET"]
CWU_MODE_TO_WIRE: dict[str, str] = {
    "Włączony": "Still_On",
    "STOP": "Stop",
    "PRIORYTET": "Priority",
}
CWU_MODE_FROM_WIRE: dict[str, str] = {
    "Still_On": "Włączony",
    "Stop": "STOP",
    "Priority": "PRIORYTET",
}


SELECTS: tuple[EltermSelectDescription, ...] = (
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
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data["coordinator"]
    server = entry_data["server"]
    devid = entry_data["devid"]
    dev_name = entry.title
    async_add_entities(
        [EltermSelect(coordinator, server, devid, dev_name, desc) for desc in SELECTS]
    )


class EltermSelect(EltermEntity, SelectEntity):
    entity_description: EltermSelectDescription

    def __init__(
        self,
        coordinator,
        server,
        devid: str,
        dev_name: str,
        description: EltermSelectDescription,
    ) -> None:
        super().__init__(coordinator, devid, dev_name)
        self.entity_description = description
        self._server = server
        self._attr_suggested_object_id = f"lokalterm_{description.key}"
        self._attr_unique_id = f"{devid}_{description.key}"

    @property
    def current_option(self) -> str | None:
        data = self.coordinator.data or {}
        raw = data.get(self.entity_description.field)
        if raw is None:
            return None
        return self.entity_description.map_from_wire.get(str(raw).strip())

    async def async_select_option(self, option: str) -> None:
        if option not in (self.entity_description.options or []):
            return
        wire_value = self.entity_description.map_to_wire[option]
        await self._server.send_data_to_send({self.entity_description.field: wire_value})
