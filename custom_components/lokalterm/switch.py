from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import EltermEntity


@dataclass(frozen=True, kw_only=True)
class EltermSwitchDescription(SwitchEntityDescription):
    pass


SWITCHES: tuple[EltermSwitchDescription, ...] = (
    EltermSwitchDescription(
        key="co_enable",
        name="CO Włączone",
        icon="mdi:radiator",
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
    async_add_entities(
        [EltermCoEnableSwitch(coordinator, server, devid, entry.title, SWITCHES[0])]
    )


class EltermCoEnableSwitch(EltermEntity, SwitchEntity):
    entity_description: EltermSwitchDescription

    def __init__(
        self,
        coordinator,
        server,
        devid: str,
        dev_name: str,
        description: EltermSwitchDescription,
    ) -> None:
        super().__init__(coordinator, devid, dev_name)
        self.entity_description = description
        self._server = server
        self._attr_suggested_object_id = f"lokalterm_{description.key}"
        self._attr_unique_id = f"{devid}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data or {}
        val = data.get("CH1Mode")
        return str(val) != "Stop" if val is not None else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._server.send_data_to_send({"CH1Mode": "Still_On"})

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._server.send_data_to_send({"CH1Mode": "Stop"})
