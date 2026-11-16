from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CO_MAX_TEMP,
    CO_MIN_TEMP,
    CWU_MAX_TEMP,
    CWU_MIN_TEMP,
    DOMAIN,
    HIST_MAX,
    HIST_MIN,
)
from .entity import EltermEntity, temp_to_wire, to_temp_celsius


@dataclass(frozen=True, kw_only=True)
class EltermNumberDescription(NumberEntityDescription):
    field: str


NUMBERS: tuple[EltermNumberDescription, ...] = (
    EltermNumberDescription(
        key="co_temperatura_zadana",
        name="CO Temperatura",
        icon="mdi:thermometer",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=CO_MIN_TEMP,
        native_max_value=CO_MAX_TEMP,
        native_step=1.0,
        mode=NumberMode.SLIDER,
        field="BoilerTempCmd",
    ),
    EltermNumberDescription(
        key="co_histereza",
        name="CO Histereza",
        icon="mdi:delta",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=HIST_MIN,
        native_max_value=HIST_MAX,
        native_step=1.0,
        mode=NumberMode.SLIDER,
        field="BoilerHist",
    ),
    EltermNumberDescription(
        key="cwu_temperatura_zadana",
        name="CWU Temperatura",
        icon="mdi:thermometer",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=CWU_MIN_TEMP,
        native_max_value=CWU_MAX_TEMP,
        native_step=1.0,
        mode=NumberMode.SLIDER,
        field="DHWTempCmd",
    ),
    EltermNumberDescription(
        key="cwu_histereza",
        name="CWU Histereza",
        icon="mdi:delta",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=HIST_MIN,
        native_max_value=HIST_MAX,
        native_step=1.0,
        mode=NumberMode.SLIDER,
        field="DHWHist",
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
        [EltermNumber(coordinator, server, devid, dev_name, desc) for desc in NUMBERS]
    )


class EltermNumber(EltermEntity, NumberEntity):
    entity_description: EltermNumberDescription

    def __init__(
        self,
        coordinator,
        server,
        devid: str,
        dev_name: str,
        description: EltermNumberDescription,
    ) -> None:
        super().__init__(coordinator, devid, dev_name)
        self.entity_description = description
        self._server = server
        self._attr_suggested_object_id = f"lokalterm_{description.key}"
        self._attr_unique_id = f"{devid}_{description.key}"

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data or {}
        return to_temp_celsius(data.get(self.entity_description.field))

    async def async_set_native_value(self, value: float) -> None:
        wire_val = temp_to_wire(
            value,
            min_val=self.entity_description.native_min_value,
            max_val=self.entity_description.native_max_value,
        )
        await self._server.send_data_to_send({self.entity_description.field: wire_val})
