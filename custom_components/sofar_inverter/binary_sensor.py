"""Binary sensor platform for the Sofar Inverter Modbus TCP integration.

All entities here are new, so there is no existing identity to preserve. The
headline "Problem" and "EPS Active" entities are enabled by default because they
are the ones worth automating on; the passive-command battery flags and the clock
check are diagnostics and start disabled.
"""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BINARY_SENSOR_META, DIAGNOSTIC_BINARY_SENSORS, DOMAIN
from .coordinator import SofarCoordinator
from .device import build_device_info

_LOGGER = logging.getLogger(__name__)

DEVICE_CLASS_MAP: dict[str | None, BinarySensorDeviceClass | None] = {
    "problem": BinarySensorDeviceClass.PROBLEM,
    "power": BinarySensorDeviceClass.POWER,
    None: None,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sofar binary sensors from a config entry."""
    coordinator: SofarCoordinator = hass.data[DOMAIN][entry.entry_id]
    device_info = build_device_info(entry, coordinator)

    async_add_entities(
        SofarBinarySensor(coordinator, entry.entry_id, device_info, key)
        for key in coordinator.binary_sensor_keys
    )


class SofarBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """A boolean condition derived from the inverter's registers."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SofarCoordinator,
        entry_id: str,
        device_info,
        key: str,
    ) -> None:
        super().__init__(coordinator)

        self._key = key
        label, device_class, icon = BINARY_SENSOR_META.get(
            key, (key.replace("_", " ").title(), None, None)
        )

        self._attr_name = label
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_device_class = DEVICE_CLASS_MAP.get(device_class)
        if icon is not None:
            self._attr_icon = icon
        self._attr_device_info = device_info

        if key in DIAGNOSTIC_BINARY_SENSORS:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
            self._attr_entity_registry_enabled_default = False

    @property
    def is_on(self) -> bool | None:
        """Return the current state, or None when it could not be determined."""
        if self.coordinator.data is None:
            return None
        value = self.coordinator.data.get(self._key)
        return None if value is None else bool(value)

    @property
    def extra_state_attributes(self) -> dict | None:
        """Expose the decoded fault detail behind the Problem state."""
        if self.coordinator.data is None:
            return None
        extra = self.coordinator.data.get(f"{self._key}_attrs")
        return dict(extra) if isinstance(extra, dict) else None

    @property
    def available(self) -> bool:
        """Unavailable when the poll failed or this value was not produced."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self.coordinator.data.get(self._key) is not None
        )
