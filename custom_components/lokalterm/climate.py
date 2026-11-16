from __future__ import annotations

from typing import Any, ClassVar

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CO_MAX_TEMP,
    CO_MIN_TEMP,
    CWU_MAX_TEMP,
    CWU_MIN_TEMP,
    DOMAIN,
)
from .entity import EltermEntity, temp_to_wire, to_temp_celsius

PRESET_NORMALNY = "Normalny"
PRESET_PRIORYTET = "Priorytet"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            EltermCoClimate(data["coordinator"], data["server"], data["devid"], entry.title),
            EltermCwuClimate(data["coordinator"], data["server"], data["devid"], entry.title),
        ]
    )


class _BaseEltermClimate(EltermEntity, ClimateEntity):
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1.0
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, coordinator, server, devid: str, dev_name: str) -> None:
        super().__init__(coordinator, devid, dev_name)
        self._server = server

    async def async_turn_on(self) -> None:
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)


class EltermCoClimate(_BaseEltermClimate):
    _attr_name = "Termostat CO"
    _attr_min_temp = CO_MIN_TEMP
    _attr_max_temp = CO_MAX_TEMP
    _attr_hvac_modes: ClassVar[list[HVACMode]] = [HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator, server, devid: str, dev_name: str) -> None:
        super().__init__(coordinator, server, devid, dev_name)
        self._attr_suggested_object_id = "lokalterm_termostat_co"
        self._attr_unique_id = f"{devid}_climate"

    @property
    def current_temperature(self) -> float | None:
        return to_temp_celsius((self.coordinator.data or {}).get("BoilerTempAct"))

    @property
    def target_temperature(self) -> float | None:
        return to_temp_celsius((self.coordinator.data or {}).get("BoilerTempCmd"))

    @property
    def hvac_mode(self) -> HVACMode | None:
        mode = (self.coordinator.data or {}).get("CH1Mode")
        if mode is None:
            return None
        return HVACMode.OFF if str(mode) == "Stop" else HVACMode.HEAT

    async def async_set_temperature(self, **kwargs: Any) -> None:
        fields: dict[str, str] = {}
        hvac_mode = kwargs.get(ATTR_HVAC_MODE)
        if hvac_mode in self._attr_hvac_modes:
            fields["CH1Mode"] = "Stop" if hvac_mode == HVACMode.OFF else "Still_On"

        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            fields["BoilerTempCmd"] = temp_to_wire(
                float(temp),
                min_val=CO_MIN_TEMP,
                max_val=CO_MAX_TEMP,
            )

        if fields:
            await self._server.send_data_to_send(fields)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode not in self._attr_hvac_modes:
            return
        mode = "Stop" if hvac_mode == HVACMode.OFF else "Still_On"
        await self._server.send_data_to_send({"CH1Mode": mode})


class EltermCwuClimate(_BaseEltermClimate):
    _attr_name = "Termostat CWU"
    _attr_min_temp = CWU_MIN_TEMP
    _attr_max_temp = CWU_MAX_TEMP
    _attr_hvac_modes: ClassVar[list[HVACMode]] = [HVACMode.HEAT, HVACMode.OFF]
    _attr_preset_modes: ClassVar[list[str]] = [PRESET_NORMALNY, PRESET_PRIORYTET]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator, server, devid: str, dev_name: str) -> None:
        super().__init__(coordinator, server, devid, dev_name)
        self._attr_suggested_object_id = "lokalterm_termostat_cwu"
        self._attr_unique_id = f"{devid}_climate_cwu"
        self._last_active_preset: str = PRESET_NORMALNY

    @property
    def current_temperature(self) -> float | None:
        return to_temp_celsius((self.coordinator.data or {}).get("DHWTempAct"))

    @property
    def target_temperature(self) -> float | None:
        return to_temp_celsius((self.coordinator.data or {}).get("DHWTempCmd"))

    @property
    def hvac_mode(self) -> HVACMode | None:
        mode = (self.coordinator.data or {}).get("DHWMode")
        if mode is None:
            return None
        return HVACMode.OFF if str(mode) == "Stop" else HVACMode.HEAT

    @property
    def preset_mode(self) -> str | None:
        mode = (self.coordinator.data or {}).get("DHWMode")
        if mode is None:
            return None
        mode_s = str(mode)
        if mode_s == "Priority":
            self._last_active_preset = PRESET_PRIORYTET
            return PRESET_PRIORYTET
        if mode_s == "Still_On":
            self._last_active_preset = PRESET_NORMALNY
            return PRESET_NORMALNY
        return self._last_active_preset

    async def async_set_temperature(self, **kwargs: Any) -> None:
        fields: dict[str, str] = {}
        hvac_mode = kwargs.get(ATTR_HVAC_MODE)
        if hvac_mode in self._attr_hvac_modes:
            if hvac_mode == HVACMode.OFF:
                fields["DHWMode"] = "Stop"
            else:
                preset = self.preset_mode or self._last_active_preset
                fields["DHWMode"] = "Priority" if preset == PRESET_PRIORYTET else "Still_On"

        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            fields["DHWTempCmd"] = temp_to_wire(
                float(temp),
                min_val=CWU_MIN_TEMP,
                max_val=CWU_MAX_TEMP,
            )

        if fields:
            await self._server.send_data_to_send(fields)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode not in self._attr_hvac_modes:
            return
        if hvac_mode == HVACMode.OFF:
            await self._server.send_data_to_send({"DHWMode": "Stop"})
            return

        current_preset = self.preset_mode or self._last_active_preset
        mode = "Priority" if current_preset == PRESET_PRIORYTET else "Still_On"
        await self._server.send_data_to_send({"DHWMode": mode})

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode not in self._attr_preset_modes:
            return
        self._last_active_preset = preset_mode
        mode = "Priority" if preset_mode == PRESET_PRIORYTET else "Still_On"
        await self._server.send_data_to_send({"DHWMode": mode})
