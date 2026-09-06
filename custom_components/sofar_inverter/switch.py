"""Switch platform for the Sofar Inverter Time-of-Use rule.

Two kinds of switch, both new entities:

  * the rule enable flag (register 0x120F)
  * one switch per weekday, which together form the bitmask in register 0x120E

The weekday switches share a register, so each toggle recomputes the whole mask
and rewrites the TOU block atomically rather than writing a partial value.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, TOU_WEEKDAYS
from .coordinator import SofarCoordinator
from .device import build_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Sofar Time-of-Use switches."""
    coordinator: SofarCoordinator = hass.data[DOMAIN][entry.entry_id]
    if not coordinator.supports_schedule:
        return

    device_info = build_device_info(entry, coordinator)

    entities: list[SwitchEntity] = [
        SofarTouEnableSwitch(coordinator, entry.entry_id, device_info)
    ]
    entities.extend(
        SofarTouWeekdaySwitch(coordinator, entry.entry_id, device_info, key, label, bit)
        for key, label, bit in TOU_WEEKDAYS
    )
    async_add_entities(entities)


class SofarTouEnableSwitch(CoordinatorEntity, SwitchEntity):
    """Enable or disable the currently selected Time-of-Use rule (0x120F)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:calendar-check"

    def __init__(
        self,
        coordinator: SofarCoordinator,
        entry_id: str,
        device_info,
    ) -> None:
        super().__init__(coordinator)
        self._attr_name = "TOU Rule Enabled"
        self._attr_unique_id = f"{entry_id}_tou_enabled"
        self._attr_device_info = device_info

    @property
    def is_on(self) -> bool | None:
        raw = self.coordinator.schedule_value("tou_enabled")
        return None if raw is None else bool(raw)

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator.schedule_value("tou_enabled") is not None
        )

    async def _write(self, value: int) -> None:
        if not await self.coordinator.async_set_schedule_value("tou_enabled", value):
            _LOGGER.error("The inverter did not accept tou_enabled = %s", value)
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._write(1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._write(0)


class SofarTouWeekdaySwitch(CoordinatorEntity, SwitchEntity):
    """One weekday bit of the Time-of-Use rule mask (0x120E)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:calendar-week"

    def __init__(
        self,
        coordinator: SofarCoordinator,
        entry_id: str,
        device_info,
        key: str,
        label: str,
        bit: int,
    ) -> None:
        super().__init__(coordinator)
        self._bit = bit
        self._attr_name = f"TOU {label}"
        self._attr_unique_id = f"{entry_id}_tou_weekday_{key}"
        self._attr_device_info = device_info

    @property
    def is_on(self) -> bool | None:
        raw = self.coordinator.schedule_value("tou_weekdays")
        return None if raw is None else bool(int(raw) & (1 << self._bit))

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator.schedule_value("tou_weekdays") is not None
        )

    async def _set_bit(self, enabled: bool) -> None:
        raw = self.coordinator.schedule_value("tou_weekdays")
        if raw is None:
            _LOGGER.error(
                "Cannot change the TOU weekday mask before it has been read "
                "from the inverter"
            )
            return
        mask = int(raw)
        mask = mask | (1 << self._bit) if enabled else mask & ~(1 << self._bit)
        if not await self.coordinator.async_set_schedule_value("tou_weekdays", mask):
            _LOGGER.error("The inverter did not accept the TOU weekday mask %s", mask)
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set_bit(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set_bit(False)
