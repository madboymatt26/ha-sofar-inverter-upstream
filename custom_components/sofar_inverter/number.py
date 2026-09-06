"""Number platform for the Sofar Inverter.

Provides the original charge/discharge power setpoint plus, when schedule support
is enabled, the numeric Timing and Time-of-Use parameters. The existing
"Battery Power Setpoint" entity keeps its unique_id, name, unit, step and range
unchanged.
"""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    MODE_CHARGE,
    MODE_DISCHARGE,
    SCHEDULE_NUMBER_ENTITIES,
)
from .coordinator import SofarCoordinator
from .device import build_device_info

_LOGGER = logging.getLogger(__name__)

# Register 0x120B: zero is not "no charging", it means charge the battery from
# whatever grid power is available.
TOU_POWER_ZERO_MEANING = (
    "0 W does not disable charging: it charges the battery from the available "
    "grid power instead of a fixed limit."
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Sofar number entities."""
    coordinator: SofarCoordinator = hass.data[DOMAIN][entry.entry_id]
    device_info = build_device_info(entry, coordinator)

    entities: list[NumberEntity] = []

    if coordinator.enable_control:
        entities.append(SofarPowerSetpoint(coordinator, entry.entry_id, device_info))

    if coordinator.supports_schedule:
        for key, label, unit, minimum, maximum, step, icon in SCHEDULE_NUMBER_ENTITIES:
            entities.append(
                SofarScheduleNumber(
                    coordinator, entry.entry_id, device_info,
                    key, label, unit, minimum, maximum, step, icon,
                )
            )

    async_add_entities(entities)


class SofarPowerSetpoint(CoordinatorEntity, NumberEntity):
    """Charge/discharge power setpoint (watts) used by the Battery Mode select."""

    _attr_icon = "mdi:flash"
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_native_step = 100
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: SofarCoordinator,
        entry_id: str,
        device_info,
    ) -> None:
        super().__init__(coordinator)
        self._attr_name = "Battery Power Setpoint"
        self._attr_unique_id = f"{entry_id}_power_setpoint"
        self._attr_native_min_value = 0
        # Deliberately the configured maximum, not the detected rating: the range
        # of an existing entity should not shift once the barcode is decoded.
        # Commands are clamped to the effective limit by the coordinator.
        self._attr_native_max_value = float(coordinator.max_power)
        self._attr_device_info = device_info

    @property
    def native_value(self) -> float:
        """Return the current setpoint."""
        return float(self.coordinator.active_power)

    @property
    def extra_state_attributes(self) -> dict | None:
        """Surface the clamp actually applied to commands."""
        effective = self.coordinator.effective_max_power
        if effective >= self.coordinator.max_power:
            return None
        return {
            "effective_max_power": effective,
            "clamped_because": (
                "the inverter's detected rating is lower than the configured maximum"
            ),
        }

    async def async_set_native_value(self, value: float) -> None:
        """Store the new setpoint and re-apply if charging/discharging."""
        power = int(value)
        self.coordinator.set_active_mode(self.coordinator.active_mode, power)
        # If we are actively charging/discharging, push the new level now.
        if self.coordinator.active_mode in (MODE_CHARGE, MODE_DISCHARGE):
            await self.coordinator.async_set_mode(self.coordinator.active_mode, power)
        self.async_write_ha_state()


class SofarScheduleNumber(CoordinatorEntity, NumberEntity):
    """A numeric Timing / Time-of-Use register on the inverter.

    The value shown is the inverter's own register content. Setting it rewrites
    the whole register block atomically and verifies the result by read-back.
    """

    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: SofarCoordinator,
        entry_id: str,
        device_info,
        key: str,
        label: str,
        unit: str | None,
        minimum: int,
        maximum: int,
        step: int,
        icon: str,
    ) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_name = label
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_native_min_value = float(minimum)
        self._attr_native_max_value = float(maximum)
        self._attr_native_step = float(step)
        self._attr_icon = icon
        self._attr_device_info = device_info

    @property
    def native_value(self) -> float | None:
        """Return the inverter's current value for this register."""
        value = self.coordinator.schedule_value(self._key)
        return None if value is None else float(value)

    @property
    def extra_state_attributes(self) -> dict | None:
        if self._key == "tou_power":
            return {"zero_means": TOU_POWER_ZERO_MEANING}
        return None

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator.schedule_value(self._key) is not None
        )

    async def async_set_native_value(self, value: float) -> None:
        """Write the new value and let the coordinator verify it."""
        if not await self.coordinator.async_set_schedule_value(self._key, int(value)):
            _LOGGER.error(
                "The inverter did not accept %s = %s; check the log for the "
                "read-back mismatch",
                self._key, int(value),
            )
        self.async_write_ha_state()
