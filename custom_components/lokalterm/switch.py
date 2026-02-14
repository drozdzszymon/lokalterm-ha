from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


@dataclass(frozen=True, kw_only=True)
class EltermSwitchDescription(SwitchEntityDescription):
    pass


SWITCHES: list[EltermSwitchDescription] = [
    EltermSwitchDescription(
        key="co_enable",
        name="CO Włączone",
        icon="mdi:radiator",
    )
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    server = hass.data[DOMAIN][entry.entry_id]["server"]
    async_add_entities([EltermCoEnableSwitch(coordinator, server, entry, SWITCHES[0])])


class EltermCoEnableSwitch(CoordinatorEntity, SwitchEntity):
    entity_description: EltermSwitchDescription

    def __init__(self, coordinator, server, entry: ConfigEntry, description: EltermSwitchDescription):
        super().__init__(coordinator)
        self.entity_description = description
        self._server = server

        # Stabilny object_id -> entity_id z prefiksem lokalterm_
        self._attr_suggested_object_id = f"lokalterm_{description.key}"

        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.unique_id)},
            "name": entry.title,
            "manufacturer": "Elterm",
            "model": "SKZP (serwer lokalny)",
        }

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data or {}
        val = data.get("CH1Mode")
        return str(val) != "Stop" if val is not None else None

    async def async_turn_on(self, **kwargs) -> None:
        await self._server.send_data_to_send({"CH1Mode": "Still_On"})

    async def async_turn_off(self, **kwargs) -> None:
        await self._server.send_data_to_send({"CH1Mode": "Stop"})
