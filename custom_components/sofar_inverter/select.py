"""Select platform for the Sofar Inverter.

Two selects:

  * Battery Mode — the original passive-mode override. Its unique_id, name and
    option strings are unchanged, because option strings are recorded in history
    as entity states.
  * Working Mode — writes register 0x1200 to switch the inverter between Auto,
    Time of Use, Timing and Passive, verified by read-back.

Schedule parameters are written to the inverter as soon as they are changed, so
they are always already in place before the working mode is switched to Timing or
Time of Use.
"""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    MODE_LABELS,
    MODE_NONE,
    WORKING_MODE_MAP,
    WORKING_MODE_PASSIVE,
    WORKING_MODE_REVERSE,
)
from .coordinator import SofarCoordinator
from .device import build_device_info

_LOGGER = logging.getLogger(__name__)

# Friendly label -> internal mode. Derived from MODE_LABELS so the strings exist
# in exactly one place; insertion order is preserved.
MODE_OPTIONS: dict[str, str] = {label: mode for mode, label in MODE_LABELS.items()}
MODE_TO_LABEL = dict(MODE_LABELS)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Sofar select entities."""
    coordinator: SofarCoordinator = hass.data[DOMAIN][entry.entry_id]
    device_info = build_device_info(entry, coordinator)

    entities: list[SelectEntity] = []

    if coordinator.enable_control:
        entities.append(SofarModeSelect(coordinator, entry.entry_id, device_info))

    if coordinator.supports_working_mode_write and (
        coordinator.enable_control or coordinator.supports_schedule
    ):
        entities.append(SofarWorkingModeSelect(coordinator, entry.entry_id, device_info))

    async_add_entities(entities)


class SofarModeSelect(CoordinatorEntity, SelectEntity):
    """Battery control mode selector.

    WARNING: Charge/Discharge/Standby require the inverter to be in Passive
    Mode. Forcing these modes overrides the inverter's own energy management.
    """

    _attr_icon = "mdi:battery-charging"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SofarCoordinator,
        entry_id: str,
        device_info,
    ) -> None:
        super().__init__(coordinator)
        self._attr_name = "Battery Mode"
        self._attr_unique_id = f"{entry_id}_battery_mode"
        self._attr_options = list(MODE_OPTIONS.keys())
        self._attr_device_info = device_info

    @property
    def current_option(self) -> str:
        """Return the currently selected mode label."""
        return MODE_TO_LABEL.get(self.coordinator.active_mode, "No Override")

    @property
    def extra_state_attributes(self) -> dict | None:
        """Show what the inverter actually did with the request."""
        attributes: dict = {
            "effective_mode": MODE_TO_LABEL.get(
                self.coordinator.effective_mode, self.coordinator.effective_mode
            ),
        }
        if self.coordinator.last_command_result:
            attributes["last_command_result"] = self.coordinator.last_command_result
        if self.coordinator.last_command_at:
            attributes["last_command_at"] = self.coordinator.last_command_at.isoformat()
        return attributes

    async def async_select_option(self, option: str) -> None:
        """Apply the chosen mode."""
        mode = MODE_OPTIONS.get(option, MODE_NONE)
        power = self.coordinator.active_power
        success = await self.coordinator.async_set_mode(mode, power)
        if not success:
            _LOGGER.error(
                "Failed to set Sofar battery mode to %s: %s",
                option, self.coordinator.last_command_result,
            )
        self.async_write_ha_state()


class SofarWorkingModeSelect(CoordinatorEntity, SelectEntity):
    """Inverter working mode (register 0x1200).

    Passive Mode is what makes the Battery Mode overrides effective; Timing and
    Time of Use hand control back to the inverter's own scheduler.
    """

    _attr_icon = "mdi:cog-transfer"
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: SofarCoordinator,
        entry_id: str,
        device_info,
    ) -> None:
        super().__init__(coordinator)
        self._attr_name = "Working Mode"
        self._attr_unique_id = f"{entry_id}_working_mode_select"
        self._attr_options = list(WORKING_MODE_MAP.values())
        self._attr_device_info = device_info

    @property
    def current_option(self) -> str | None:
        if self.coordinator.data is None:
            return None
        value = self.coordinator.data.get("working_mode")
        return None if value is None else WORKING_MODE_MAP.get(int(value))

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self.coordinator.data.get("working_mode") is not None
        )

    async def async_select_option(self, option: str) -> None:
        """Write the working mode, verifying that it actually changed."""
        value = WORKING_MODE_REVERSE.get(option)
        if value is None:
            _LOGGER.error("Unknown working mode '%s'", option)
            return

        if value == WORKING_MODE_PASSIVE:
            _LOGGER.info(
                "Switching %s into Passive Mode: the inverter's own energy "
                "management is suspended and it will fall back to standby if the "
                "heartbeat stops for 60s",
                self.coordinator.host,
            )

        if not await self.coordinator.async_set_working_mode(value):
            _LOGGER.error("Failed to set the working mode to %s", option)
        self.async_write_ha_state()
