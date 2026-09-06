"""Time platform for the Sofar Inverter Timing / Time-of-Use windows.

Each entity maps to one register that packs an hour in its high byte and a
minute in its low byte. Seconds are not representable and are discarded.

These windows are evaluated against the inverter's own real-time clock, not
Home Assistant's, so the clock diagnostics and the "Sync Inverter Clock" button
matter as much as the schedule itself.
"""
from __future__ import annotations

import logging
from datetime import time as dt_time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SCHEDULE_TIME_ENTITIES
from .coordinator import SofarCoordinator
from .device import build_device_info

_LOGGER = logging.getLogger(__name__)


def pack_time(value: dt_time) -> int:
    """Pack an hour/minute pair into one register (high byte hour)."""
    return ((value.hour & 0xFF) << 8) | (value.minute & 0xFF)


def unpack_time(raw: int) -> dt_time | None:
    """Unpack a register into a time, or None if it is not a valid one."""
    hour = (int(raw) >> 8) & 0xFF
    minute = int(raw) & 0xFF
    if hour > 23 or minute > 59:
        return None
    return dt_time(hour=hour, minute=minute)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Sofar schedule time entities."""
    coordinator: SofarCoordinator = hass.data[DOMAIN][entry.entry_id]
    if not coordinator.supports_schedule:
        return

    device_info = build_device_info(entry, coordinator)
    async_add_entities(
        SofarScheduleTime(coordinator, entry.entry_id, device_info, key, label, icon)
        for key, label, _register, icon in SCHEDULE_TIME_ENTITIES
    )


class SofarScheduleTime(CoordinatorEntity, TimeEntity):
    """One hour/minute schedule register on the inverter."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: SofarCoordinator,
        entry_id: str,
        device_info,
        key: str,
        label: str,
        icon: str,
    ) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_name = label
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_icon = icon
        self._attr_device_info = device_info

    @property
    def native_value(self) -> dt_time | None:
        raw = self.coordinator.schedule_value(self._key)
        return None if raw is None else unpack_time(raw)

    @property
    def available(self) -> bool:
        raw = self.coordinator.schedule_value(self._key)
        return (
            self.coordinator.last_update_success
            and raw is not None
            and unpack_time(raw) is not None
        )

    async def async_set_value(self, value: dt_time) -> None:
        """Write the new window boundary and verify it."""
        if not await self.coordinator.async_set_schedule_value(
            self._key, pack_time(value)
        ):
            _LOGGER.error(
                "The inverter did not accept %s = %02d:%02d",
                self._key, value.hour, value.minute,
            )
        self.async_write_ha_state()
