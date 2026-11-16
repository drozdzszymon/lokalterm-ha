from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import EltermEntity, status_power_percent, to_energy_kwh, to_temp_celsius


@dataclass(frozen=True, kw_only=True)
class EltermSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], Any]


SENSORS: tuple[EltermSensorDescription, ...] = (
    EltermSensorDescription(
        key="status_pieca",
        name="Status pieca",
        icon="mdi:flash",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=status_power_percent,
    ),
    EltermSensorDescription(
        key="temp_wody_co",
        name="Temperatura wody CO",
        icon="mdi:radiator",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda d: to_temp_celsius(d.get("BoilerTempAct")),
    ),
    EltermSensorDescription(
        key="temp_wody_cwu",
        name="Temperatura wody CWU",
        icon="mdi:water-boiler",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda d: to_temp_celsius(d.get("DHWTempAct")),
    ),
    EltermSensorDescription(
        key="energia_licznik_kwh",
        name="Energia - licznik (kWh)",
        icon="mdi:counter",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda d: to_energy_kwh(d.get("P033")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data["coordinator"]
    devid = entry_data["devid"]
    dev_name = entry.title
    async_add_entities(
        [EltermSensor(coordinator, devid, dev_name, desc) for desc in SENSORS]
    )


class EltermSensor(EltermEntity, SensorEntity):
    entity_description: EltermSensorDescription

    def __init__(
        self,
        coordinator,
        devid: str,
        dev_name: str,
        description: EltermSensorDescription,
    ) -> None:
        super().__init__(coordinator, devid, dev_name)
        self.entity_description = description
        self._attr_suggested_object_id = f"lokalterm_{description.key}"
        self._attr_unique_id = f"{devid}_{description.key}"

    @property
    def native_value(self) -> Any:
        data = self.coordinator.data or {}
        return self.entity_description.value_fn(data)
