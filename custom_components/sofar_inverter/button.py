"""Button platform for Sofar Inverter quick control actions.

The two original mode buttons keep their unique_ids (``btn_auto`` /
``btn_standby``) and names. A clock-sync button is added when clock monitoring is
available.
"""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MODE_AUTO, MODE_STANDBY
from .coordinator import SofarCoordinator
from .device import build_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sofar control buttons."""
    coordinator: SofarCoordinator = hass.data[DOMAIN][entry.entry_id]
    device_info = build_device_info(entry, coordinator)

    entities: list[ButtonEntity] = []

    if coordinator.enable_control:
        entities += [
            SofarModeButton(
                coordinator, entry.entry_id, device_info,
                "Set Auto Mode", MODE_AUTO, "auto", "mdi:autorenew",
            ),
            SofarModeButton(
                coordinator, entry.entry_id, device_info,
                "Set Standby", MODE_STANDBY, "standby", "mdi:power-standby",
            ),
        ]

    if coordinator.supports_clock:
        entities.append(SofarSyncClockButton(coordinator, entry.entry_id, device_info))

    async_add_entities(entities)


class SofarModeButton(ButtonEntity):
    """A button that applies a fixed control mode to the inverter."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SofarCoordinator,
        entry_id: str,
        device_info,
        label: str,
        mode: str,
        key: str,
        icon: str,
    ) -> None:
        self._coordinator = coordinator
        self._mode = mode
        self._attr_name = label
        self._attr_unique_id = f"{entry_id}_btn_{key}"
        self._attr_icon = icon
        self._attr_device_info = device_info

    async def async_press(self) -> None:
        """Apply the configured mode."""
        success = await self._coordinator.async_set_mode(self._mode)
        if not success:
            _LOGGER.error(
                "Failed to apply Sofar mode '%s': %s",
                self._mode, self._coordinator.last_command_result,
            )


class SofarSyncClockButton(ButtonEntity):
    """Broadcast Home Assistant's clock to the inverter.

    The protocol only defines clock setting as a broadcast to address 0x88, so
    this updates every Sofar inverter on the same RS485 bus, not only this one.
    """

    _attr_has_entity_name = True
    _attr_icon = "mdi:clock-check"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: SofarCoordinator,
        entry_id: str,
        device_info,
    ) -> None:
        self._coordinator = coordinator
        self._attr_name = "Sync Inverter Clock"
        self._attr_unique_id = f"{entry_id}_btn_sync_clock"
        self._attr_device_info = device_info

    async def async_press(self) -> None:
        """Send the broadcast time-set frame."""
        if not await self._coordinator.async_sync_clock():
            _LOGGER.error("Failed to sync the inverter clock")
