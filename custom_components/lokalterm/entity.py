from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation
from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    BU_MODUL_TO_PERCENT,
    DOMAIN,
)


def to_temp_celsius(value: Any) -> float | None:
    """Konwertuje wartość protokołu SKZP (setne części °C) na float w °C."""
    if value is None or isinstance(value, bool):
        return None
    try:
        raw = float(str(value).strip()) if isinstance(value, str) else float(value)
    except (ValueError, TypeError):
        return None
    if not math.isfinite(raw):
        return None
    return round(raw / 100.0, 2)


def temp_to_wire(value_c: float, *, min_val: float | None = None, max_val: float | None = None) -> str:
    """Waliduje i konwertuje temperaturę w °C na format ramki SKZP."""
    val = float(value_c)
    if not math.isfinite(val):
        raise ValueError(f"Nieprawidłowa wartość liczbowa: {value_c!r}")
    if min_val is not None and val < min_val:
        val = min_val
    if max_val is not None and val > max_val:
        val = max_val
    return str(round(val * 100))


def to_energy_kwh(value: Any) -> float | None:
    """Bezpiecznie parsuje licznik energii (kWh), odrzucając NaN/Inf i wartości ujemne."""
    if value is None or isinstance(value, bool):
        return None
    try:
        raw = float(str(value).strip()) if isinstance(value, str) else float(value)
    except (ValueError, TypeError):
        return None
    if not math.isfinite(raw) or raw < 0.0:
        return None
    return round(raw, 2)


def status_power_percent(data: dict[str, Any]) -> int | None:
    """Oblicza bieżące wysterowanie mocy kotła w procentach."""
    ds = data.get("DevStatus")
    if isinstance(ds, str) and len(ds) >= 6 and ds[3:6].isdigit():
        return min(100, max(0, int(ds[3:6])))

    ch_mode = data.get("CH1Mode")
    dhw_mode = data.get("DHWMode")
    if ch_mode == "Stop" and dhw_mode in (None, "Stop"):
        return 0

    step = data.get("BuModulMax")
    if step is None or isinstance(step, bool):
        return None
    try:
        step_i = int(str(step).strip())
    except (ValueError, TypeError):
        return None

    return BU_MODUL_TO_PERCENT.get(step_i)


def values_match(actual: Any, expected: Any) -> bool:
    """Porównuje pole z ramki pieca z wartością oczekiwaną (obsługuje zera wiodące)."""
    if actual is None or expected is None:
        return False
    actual_s = str(actual).strip()
    expected_s = str(expected).strip()
    if actual_s == expected_s:
        return True
    if not actual_s or not expected_s:
        return False
    try:
        return Decimal(actual_s) == Decimal(expected_s)
    except InvalidOperation:
        return False


class EltermEntity(CoordinatorEntity[DataUpdateCoordinator[dict[str, Any] | None]]):
    """Wspólna klasa bazowa encji LokalTerm zapewniająca spójne DeviceInfo i dostępność."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, Any] | None],
        devid: str,
        dev_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._devid = devid
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, devid)},
            name=dev_name,
            manufacturer="Elterm",
            model="SKZP (serwer lokalny)",
        )

    @property
    def available(self) -> bool:
        return self.coordinator.data is not None
