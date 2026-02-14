from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, PERCENTAGE, UnitOfEnergy
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


def _status_power_percent(data: dict[str, Any]) -> int | None:
    ds = data.get("DevStatus")
    if isinstance(ds, str) and len(ds) >= 6 and ds[3:6].isdigit():
        return int(ds[3:6])

    mode = data.get("CH1Mode")
    if isinstance(mode, str) and mode == "Stop":
        return 0

    step = data.get("BuModulMax")
    try:
        step_i = int(step)
    except Exception:
        return None

    return {0: 33, 1: 67, 2: 100}.get(step_i)


@dataclass(frozen=True, kw_only=True)
class EltermSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], Any]


SENSORS: list[EltermSensorDescription] = [
    EltermSensorDescription(
        key="status_pieca",
        name="Status pieca",
        icon="mdi:flash",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=_status_power_percent,
    ),
    EltermSensorDescription(
        key="temp_wody_co",
        name="Temperatura wody CO",
        icon="mdi:radiator",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda d: _to_temp100(d.get("BoilerTempAct")),
    ),
    EltermSensorDescription(
        key="temp_wody_cwu",
        name="Temperatura wody CWU",
        icon="mdi:water-boiler",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda d: _to_temp100(d.get("DHWTempAct")),
    ),
    EltermSensorDescription(
        key="energia_licznik_kwh",
        name="Energia - licznik (kWh)",
        icon="mdi:counter",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: (lambda v: None if v is None else round(float(v), 2))(d.get("P033")),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    devid = hass.data[DOMAIN][entry.entry_id]["devid"]
    dev_name = entry.title
    async_add_entities([EltermSensor(coordinator, devid, dev_name, desc) for desc in SENSORS])


class EltermSensor(CoordinatorEntity, SensorEntity):
    entity_description: EltermSensorDescription

    def __init__(self, coordinator, devid: str, dev_name: str, description: EltermSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description

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
    def native_value(self) -> Any:
        data = self.coordinator.data or {}
        return self.entity_description.value_fn(data)
