from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


def _to_temp100(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return int(v) / 100.0
    except Exception:
        return None


def _temp_to_wire(value_c: float) -> str:
    return str(int(round(value_c * 100)))


@dataclass(frozen=True, kw_only=True)
class EltermNumberDescription(NumberEntityDescription):
    field: str


NUMBERS: list[EltermNumberDescription] = [
    EltermNumberDescription(
        key="co_temperatura_zadana",
        name="CO Temperatura",
        icon="mdi:thermometer",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=20.0,
        native_max_value=69.0,
        native_step=1,
        field="BoilerTempCmd",
    ),
    EltermNumberDescription(
        key="co_histereza",
        name="CO Histereza",
        icon="mdi:delta",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=0.0,
        native_max_value=6.0,
        native_step=1.0,
        field="BoilerHist",
    ),
    EltermNumberDescription(
        key="cwu_temperatura_zadana",
        name="CWU Temperatura",
        icon="mdi:thermometer",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=30.0,
        native_max_value=69.0,
        native_step=1,
        field="DHWTempCmd",
    ),
    EltermNumberDescription(
        key="cwu_histereza",
        name="CWU Histereza",
        icon="mdi:delta",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=0.0,
        native_max_value=6.0,
        native_step=1.0,
        field="DHWHist",
    ),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    server = hass.data[DOMAIN][entry.entry_id]["server"]
    devid = hass.data[DOMAIN][entry.entry_id]["devid"]
    dev_name = entry.title
    async_add_entities([EltermNumber(coordinator, server, devid, dev_name, desc) for desc in NUMBERS])


class EltermNumber(CoordinatorEntity, NumberEntity):
    entity_description: EltermNumberDescription

    def __init__(self, coordinator, server, devid: str, dev_name: str, description: EltermNumberDescription) -> None:
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
    def native_value(self) -> float | None:
        data = self.coordinator.data or {}
        return _to_temp100(data.get(self.entity_description.field))

    async def async_set_native_value(self, value: float) -> None:
        data = self.coordinator.data or {}
        fields = {self.entity_description.field: _temp_to_wire(float(value))}
        await self._server.send_data_to_send(fields, base_state=dict(data))
