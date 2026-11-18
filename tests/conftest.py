from __future__ import annotations

import asyncio
import sys
import types
from collections.abc import Callable
from dataclasses import dataclass
from enum import IntFlag, StrEnum
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_voluptuous_shim() -> None:
    if "voluptuous" in sys.modules:
        return

    vol = types.ModuleType("voluptuous")

    class _Marker:
        def __init__(self, schema: Any, default: Any = None) -> None:
            self.schema = schema
            self.default = default if callable(default) else (lambda d=default: d)

        def __hash__(self) -> int:
            return hash(self.schema)

        def __eq__(self, other: object) -> bool:
            if isinstance(other, _Marker):
                return self.schema == other.schema
            return self.schema == other

    class Required(_Marker):
        pass

    class Optional(_Marker):
        pass

    class Schema:
        def __init__(self, schema: dict[Any, Any]) -> None:
            self.schema = schema

    vol.Required = Required  # type: ignore[attr-defined]
    vol.Optional = Optional  # type: ignore[attr-defined]
    vol.Schema = Schema  # type: ignore[attr-defined]
    sys.modules["voluptuous"] = vol


def _install_homeassistant_shims() -> None:
    if "homeassistant" in sys.modules:
        return

    ha = types.ModuleType("homeassistant")
    sys.modules["homeassistant"] = ha

    # homeassistant.const
    ha_const = types.ModuleType("homeassistant.const")

    class Platform(StrEnum):
        SENSOR = "sensor"
        NUMBER = "number"
        SELECT = "select"
        CLIMATE = "climate"
        SWITCH = "switch"

    class UnitOfTemperature(StrEnum):
        CELSIUS = "°C"

    class UnitOfEnergy(StrEnum):
        KILO_WATT_HOUR = "kWh"

    ha_const.Platform = Platform  # type: ignore[attr-defined]
    ha_const.UnitOfTemperature = UnitOfTemperature  # type: ignore[attr-defined]
    ha_const.UnitOfEnergy = UnitOfEnergy  # type: ignore[attr-defined]
    ha_const.PERCENTAGE = "%"  # type: ignore[attr-defined]
    ha_const.CONF_NAME = "name"  # type: ignore[attr-defined]
    ha_const.ATTR_TEMPERATURE = "temperature"  # type: ignore[attr-defined]
    ha_const.EVENT_HOMEASSISTANT_STOP = "homeassistant_stop"  # type: ignore[attr-defined]
    sys.modules["homeassistant.const"] = ha_const
    ha.const = ha_const  # type: ignore[attr-defined]

    # homeassistant.exceptions
    ha_exc = types.ModuleType("homeassistant.exceptions")

    class ConfigEntryNotReady(Exception):
        pass

    class AbortFlow(Exception):
        def __init__(self, reason: str) -> None:
            super().__init__(reason)
            self.reason = reason

    ha_exc.ConfigEntryNotReady = ConfigEntryNotReady  # type: ignore[attr-defined]
    ha_exc.AbortFlow = AbortFlow  # type: ignore[attr-defined]
    sys.modules["homeassistant.exceptions"] = ha_exc

    # homeassistant.core
    ha_core = types.ModuleType("homeassistant.core")

    def callback(func: Callable[..., Any]) -> Callable[..., Any]:
        return func

    class Event:
        def __init__(self, event_type: str, data: dict[str, Any] | None = None) -> None:
            self.event_type = event_type
            self.data = data or {}

    class EventBus:
        def __init__(self) -> None:
            self._listeners: dict[str, list[Callable[[Event], Any]]] = {}

        def async_listen_once(
            self,
            event_type: str,
            listener: Callable[[Event], Any],
        ) -> Callable[[], None]:
            bucket = self._listeners.setdefault(event_type, [])
            bucket.append(listener)

            def _unsub() -> None:
                if listener in bucket:
                    bucket.remove(listener)

            return _unsub

        async def async_fire(self, event_type: str) -> None:
            listeners = list(self._listeners.pop(event_type, []))
            for fn in listeners:
                res = fn(Event(event_type))
                if asyncio.iscoroutine(res):
                    await res

    class ConfigEntriesManager:
        def __init__(self, hass: HomeAssistant) -> None:
            self._hass = hass
            self._entries: dict[str, Any] = {}
            self.forwarded: list[tuple[str, list[Any]]] = []
            self.unloaded: list[tuple[str, list[Any]]] = []
            self.reloaded: list[str] = []

        def add_entry(self, entry: Any) -> None:
            self._entries[entry.entry_id] = entry

        def async_entries(self, domain: str | None = None) -> list[Any]:
            entries = list(self._entries.values())
            if domain is None:
                return entries
            return [e for e in entries if e.domain == domain]

        async def async_forward_entry_setups(self, entry: Any, platforms: list[Any]) -> None:
            self.forwarded.append((entry.entry_id, list(platforms)))

        async def async_unload_platforms(self, entry: Any, platforms: list[Any]) -> bool:
            self.unloaded.append((entry.entry_id, list(platforms)))
            return True

        async def async_reload(self, entry_id: str) -> None:
            self.reloaded.append(entry_id)

    class HomeAssistant:
        def __init__(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
            self.loop = loop or asyncio.get_event_loop()
            self.data: dict[str, Any] = {}
            self.bus = EventBus()
            self.config_entries = ConfigEntriesManager(self)
            self._tasks: set[asyncio.Task[Any]] = set()

        def async_create_task(self, coro: Any) -> asyncio.Task[Any]:
            task = self.loop.create_task(coro)
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
            return task

    ha_core.HomeAssistant = HomeAssistant  # type: ignore[attr-defined]
    ha_core.Event = Event  # type: ignore[attr-defined]
    ha_core.callback = callback  # type: ignore[attr-defined]
    sys.modules["homeassistant.core"] = ha_core

    # homeassistant.config_entries
    ha_ce = types.ModuleType("homeassistant.config_entries")

    class ConfigEntry:
        def __init__(
            self,
            *,
            entry_id: str = "entry_1",
            domain: str = "lokalterm",
            title: str = "LokalTerm",
            data: dict[str, Any] | None = None,
            options: dict[str, Any] | None = None,
            unique_id: str | None = None,
        ) -> None:
            self.entry_id = entry_id
            self.domain = domain
            self.title = title
            self.data = dict(data or {})
            self.options = dict(options or {})
            self.unique_id = unique_id
            self._unload_callbacks: list[Callable[[], None]] = []
            self._update_listeners: list[Callable[[HomeAssistant, ConfigEntry], Any]] = []

        def async_on_unload(self, func: Callable[[], None]) -> None:
            self._unload_callbacks.append(func)

        def add_update_listener(
            self,
            listener: Callable[[HomeAssistant, ConfigEntry], Any],
        ) -> Callable[[], None]:
            self._update_listeners.append(listener)

            def _unsub() -> None:
                if listener in self._update_listeners:
                    self._update_listeners.remove(listener)

            return _unsub

    class ConfigFlow:
        def __init_subclass__(cls, domain: str | None = None, **kwargs: Any) -> None:
            super().__init_subclass__(**kwargs)
            cls._domain = domain

        def __init__(self) -> None:
            self.hass: HomeAssistant | None = None
            self._unique_id: str | None = None

        async def async_set_unique_id(self, unique_id: str) -> None:
            self._unique_id = unique_id

        def _abort_if_unique_id_configured(self) -> None:
            if self.hass is None or self._unique_id is None:
                return
            for entry in self.hass.config_entries.async_entries(getattr(self, "_domain", None)):
                if entry.unique_id == self._unique_id:
                    raise AbortFlow("already_configured")

        def async_show_form(
            self,
            *,
            step_id: str,
            data_schema: Any = None,
            errors: dict[str, str] | None = None,
        ) -> dict[str, Any]:
            return {
                "type": "form",
                "step_id": step_id,
                "data_schema": data_schema,
                "errors": errors or {},
            }

        def async_create_entry(self, *, title: str, data: dict[str, Any]) -> dict[str, Any]:
            return {
                "type": "create_entry",
                "title": title,
                "data": data,
                "unique_id": self._unique_id,
            }

    class OptionsFlow:
        _config_entry: ConfigEntry | None = None

        @property
        def config_entry(self) -> ConfigEntry:
            if self._config_entry is None:
                raise RuntimeError("config_entry is not attached")
            return self._config_entry

        def async_show_form(
            self,
            *,
            step_id: str,
            data_schema: Any = None,
            errors: dict[str, str] | None = None,
        ) -> dict[str, Any]:
            return {
                "type": "form",
                "step_id": step_id,
                "data_schema": data_schema,
                "errors": errors or {},
            }

        def async_create_entry(self, *, title: str, data: dict[str, Any]) -> dict[str, Any]:
            return {
                "type": "create_entry",
                "title": title,
                "data": data,
            }

    ha_ce.ConfigEntry = ConfigEntry  # type: ignore[attr-defined]
    ha_ce.ConfigFlow = ConfigFlow  # type: ignore[attr-defined]
    ha_ce.OptionsFlow = OptionsFlow  # type: ignore[attr-defined]
    sys.modules["homeassistant.config_entries"] = ha_ce
    ha.config_entries = ha_ce  # type: ignore[attr-defined]

    # homeassistant.helpers.*
    ha_helpers = types.ModuleType("homeassistant.helpers")
    sys.modules["homeassistant.helpers"] = ha_helpers

    ha_devreg = types.ModuleType("homeassistant.helpers.device_registry")

    class DeviceInfo(dict):
        pass

    ha_devreg.DeviceInfo = DeviceInfo  # type: ignore[attr-defined]
    sys.modules["homeassistant.helpers.device_registry"] = ha_devreg

    ha_ep = types.ModuleType("homeassistant.helpers.entity_platform")
    ha_ep.AddEntitiesCallback = Callable[[list[Any]], None]  # type: ignore[attr-defined]
    sys.modules["homeassistant.helpers.entity_platform"] = ha_ep

    ha_sel = types.ModuleType("homeassistant.helpers.selector")

    class TextSelectorType(StrEnum):
        TEXT = "text"
        PASSWORD = "password"

    @dataclass
    class TextSelectorConfig:
        type: TextSelectorType = TextSelectorType.TEXT

    class TextSelector:
        def __init__(self, config: TextSelectorConfig | None = None) -> None:
            self.config = config or TextSelectorConfig()

    class NumberSelectorMode(StrEnum):
        BOX = "box"
        SLIDER = "slider"

    @dataclass
    class NumberSelectorConfig:
        min: float | None = None
        max: float | None = None
        step: float | None = None
        mode: NumberSelectorMode = NumberSelectorMode.BOX

    class NumberSelector:
        def __init__(self, config: NumberSelectorConfig | None = None) -> None:
            self.config = config or NumberSelectorConfig()

    ha_sel.TextSelector = TextSelector  # type: ignore[attr-defined]
    ha_sel.TextSelectorConfig = TextSelectorConfig  # type: ignore[attr-defined]
    ha_sel.TextSelectorType = TextSelectorType  # type: ignore[attr-defined]
    ha_sel.NumberSelector = NumberSelector  # type: ignore[attr-defined]
    ha_sel.NumberSelectorConfig = NumberSelectorConfig  # type: ignore[attr-defined]
    ha_sel.NumberSelectorMode = NumberSelectorMode  # type: ignore[attr-defined]
    sys.modules["homeassistant.helpers.selector"] = ha_sel

    ha_uc = types.ModuleType("homeassistant.helpers.update_coordinator")

    class DataUpdateCoordinator:
        def __class_getitem__(cls, _item: Any) -> type[DataUpdateCoordinator]:
            return cls

        def __init__(
            self,
            hass: HomeAssistant,
            logger: Any,
            *,
            name: str,
            config_entry: Any = None,
            update_method: Any = None,
            update_interval: Any = None,
        ) -> None:
            self.hass = hass
            self.logger = logger
            self.name = name
            self.config_entry = config_entry
            self.data: Any = None
            self.last_update_success = True
            self._listeners: list[Callable[[], None]] = []

        def async_add_listener(self, update_callback: Callable[[], None]) -> Callable[[], None]:
            self._listeners.append(update_callback)

            def _remove() -> None:
                if update_callback in self._listeners:
                    self._listeners.remove(update_callback)

            return _remove

        def async_set_updated_data(self, data: Any) -> None:
            self.data = data
            self.last_update_success = True
            for listener in list(self._listeners):
                listener()

    class CoordinatorEntity:
        def __class_getitem__(cls, _item: Any) -> type[CoordinatorEntity]:
            return cls

        def __init__(self, coordinator: DataUpdateCoordinator) -> None:
            self.coordinator = coordinator

        @property
        def available(self) -> bool:
            return self.coordinator.last_update_success

    ha_uc.DataUpdateCoordinator = DataUpdateCoordinator  # type: ignore[attr-defined]
    ha_uc.CoordinatorEntity = CoordinatorEntity  # type: ignore[attr-defined]
    sys.modules["homeassistant.helpers.update_coordinator"] = ha_uc

    # homeassistant.components.*
    ha_comp = types.ModuleType("homeassistant.components")
    sys.modules["homeassistant.components"] = ha_comp

    @dataclass(frozen=True, kw_only=True)
    class EntityDescription:
        key: str
        name: str | None = None
        icon: str | None = None

    # climate
    ha_climate = types.ModuleType("homeassistant.components.climate")

    class HVACMode(StrEnum):
        OFF = "off"
        HEAT = "heat"

    class ClimateEntityFeature(IntFlag):
        TARGET_TEMPERATURE = 1
        PRESET_MODE = 16
        TURN_OFF = 128
        TURN_ON = 256

    class ClimateEntity:
        _attr_native_temperature_unit: str | None = None
        _attr_native_current_temperature: float | None = None
        _attr_native_target_temperature: float | None = None

        @property
        def native_temperature_unit(self) -> str | None:
            return self._attr_native_temperature_unit

        @property
        def native_current_temperature(self) -> float | None:
            return self._attr_native_current_temperature

        @property
        def native_target_temperature(self) -> float | None:
            return self._attr_native_target_temperature

    ha_climate.ATTR_HVAC_MODE = "hvac_mode"  # type: ignore[attr-defined]
    ha_climate.HVACMode = HVACMode  # type: ignore[attr-defined]
    ha_climate.ClimateEntityFeature = ClimateEntityFeature  # type: ignore[attr-defined]
    ha_climate.ClimateEntity = ClimateEntity  # type: ignore[attr-defined]
    sys.modules["homeassistant.components.climate"] = ha_climate

    # number
    ha_number = types.ModuleType("homeassistant.components.number")

    class NumberDeviceClass(StrEnum):
        TEMPERATURE = "temperature"

    class NumberMode(StrEnum):
        AUTO = "auto"
        BOX = "box"
        SLIDER = "slider"

    @dataclass(frozen=True, kw_only=True)
    class NumberEntityDescription(EntityDescription):
        device_class: NumberDeviceClass | None = None
        native_unit_of_measurement: str | None = None
        native_min_value: float = 0.0
        native_max_value: float = 100.0
        native_step: float = 1.0
        mode: NumberMode = NumberMode.AUTO

    class NumberEntity:
        pass

    ha_number.NumberDeviceClass = NumberDeviceClass  # type: ignore[attr-defined]
    ha_number.NumberMode = NumberMode  # type: ignore[attr-defined]
    ha_number.NumberEntityDescription = NumberEntityDescription  # type: ignore[attr-defined]
    ha_number.NumberEntity = NumberEntity  # type: ignore[attr-defined]
    sys.modules["homeassistant.components.number"] = ha_number

    # select
    ha_select = types.ModuleType("homeassistant.components.select")

    @dataclass(frozen=True, kw_only=True)
    class SelectEntityDescription(EntityDescription):
        options: list[str] | None = None

    class SelectEntity:
        pass

    ha_select.SelectEntityDescription = SelectEntityDescription  # type: ignore[attr-defined]
    ha_select.SelectEntity = SelectEntity  # type: ignore[attr-defined]
    sys.modules["homeassistant.components.select"] = ha_select

    # sensor
    ha_sensor = types.ModuleType("homeassistant.components.sensor")

    class SensorDeviceClass(StrEnum):
        TEMPERATURE = "temperature"
        ENERGY = "energy"

    class SensorStateClass(StrEnum):
        MEASUREMENT = "measurement"
        TOTAL_INCREASING = "total_increasing"

    @dataclass(frozen=True, kw_only=True)
    class SensorEntityDescription(EntityDescription):
        device_class: SensorDeviceClass | None = None
        state_class: SensorStateClass | None = None
        native_unit_of_measurement: str | None = None
        suggested_display_precision: int | None = None

    class SensorEntity:
        pass

    ha_sensor.SensorDeviceClass = SensorDeviceClass  # type: ignore[attr-defined]
    ha_sensor.SensorStateClass = SensorStateClass  # type: ignore[attr-defined]
    ha_sensor.SensorEntityDescription = SensorEntityDescription  # type: ignore[attr-defined]
    ha_sensor.SensorEntity = SensorEntity  # type: ignore[attr-defined]
    sys.modules["homeassistant.components.sensor"] = ha_sensor

    # switch
    ha_switch = types.ModuleType("homeassistant.components.switch")

    @dataclass(frozen=True, kw_only=True)
    class SwitchEntityDescription(EntityDescription):
        pass

    class SwitchEntity:
        pass

    ha_switch.SwitchEntityDescription = SwitchEntityDescription  # type: ignore[attr-defined]
    ha_switch.SwitchEntity = SwitchEntity  # type: ignore[attr-defined]
    sys.modules["homeassistant.components.switch"] = ha_switch


_install_voluptuous_shim()
_install_homeassistant_shims()
