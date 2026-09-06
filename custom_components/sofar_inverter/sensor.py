"""Sensor platform for the Sofar Inverter Modbus TCP integration.

Existing entity identity is load-bearing here: the unique_id is
``<entry_id>_<key>`` and the friendly name comes straight from
``SENSOR_META``, so neither may change for an already-shipped key. New entities
are added by adding new keys.
"""
from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_NAME,
    DEPRECATED_SENSORS,
    DIAGNOSTIC_SENSORS,
    DISABLED_BY_DEFAULT_SENSORS,
    DOMAIN,
    SENSOR_META,
)
from .coordinator import SofarCoordinator
from .device import build_device_info

_LOGGER = logging.getLogger(__name__)

DEVICE_CLASS_MAP: dict[str | None, SensorDeviceClass | None] = {
    "voltage": SensorDeviceClass.VOLTAGE,
    "current": SensorDeviceClass.CURRENT,
    "power": SensorDeviceClass.POWER,
    "energy": SensorDeviceClass.ENERGY,
    "frequency": SensorDeviceClass.FREQUENCY,
    "temperature": SensorDeviceClass.TEMPERATURE,
    "battery": SensorDeviceClass.BATTERY,
    "duration": SensorDeviceClass.DURATION,
    "timestamp": SensorDeviceClass.TIMESTAMP,
    None: None,
}

STATE_CLASS_MAP: dict[str | None, SensorStateClass | None] = {
    "measurement": SensorStateClass.MEASUREMENT,
    "total_increasing": SensorStateClass.TOTAL_INCREASING,
    "total": SensorStateClass.TOTAL,
    None: None,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sofar sensors from a config entry."""
    coordinator: SofarCoordinator = hass.data[DOMAIN][entry.entry_id]
    inverter_name: str = entry.data[CONF_NAME]
    device_info = build_device_info(entry, coordinator)

    entities: list[SofarSensor] = []
    seen: set[str] = set()

    # Register-backed sensors.
    for sensor in coordinator.sensors:
        if sensor.key in seen:
            continue
        seen.add(sensor.key)
        entities.append(
            SofarSensor(
                coordinator=coordinator,
                entry_id=entry.entry_id,
                inverter_name=inverter_name,
                device_info=device_info,
                key=sensor.key,
            )
        )

    # Derived sensors, computed from registers that were already read.
    for key in coordinator.derived_keys:
        if key in seen:
            continue
        seen.add(key)
        entities.append(
            SofarSensor(
                coordinator=coordinator,
                entry_id=entry.entry_id,
                inverter_name=inverter_name,
                device_info=device_info,
                key=key,
            )
        )

    async_add_entities(entities)


class SofarSensor(CoordinatorEntity, SensorEntity):
    """A single value read from, or derived from, a Sofar inverter register."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SofarCoordinator,
        entry_id: str,
        inverter_name: str,
        device_info,
        key: str,
    ) -> None:
        super().__init__(coordinator)

        self._key = key
        meta = SENSOR_META.get(
            key, (key.replace("_", " ").title(), None, None, "measurement", None, None)
        )
        label, unit, device_class_str, state_class_str, precision, icon = meta

        # has_entity_name=True: HA composes "<device name> <label>" for the
        # friendly name and entity_id, so the entity name is just the label.
        self._attr_name = label
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = DEVICE_CLASS_MAP.get(device_class_str)
        self._attr_state_class = STATE_CLASS_MAP.get(state_class_str)
        if precision is not None:
            self._attr_suggested_display_precision = precision
        if icon is not None:
            self._attr_icon = icon
        self._attr_device_info = device_info

        if key in DIAGNOSTIC_SENSORS:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        if key in DISABLED_BY_DEFAULT_SENSORS:
            # Only affects the first registration of an entity, so entities that
            # already exist keep whatever enabled state the user has.
            self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self):
        """Return the current value for this register."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._key)

    @property
    def extra_state_attributes(self) -> dict | None:
        """Expose the detail behind a summarised value.

        Fault sensors keep the full decoded list here, because the state itself
        is capped at Home Assistant's 255-character limit.
        """
        attributes: dict = {}
        if self.coordinator.data is not None:
            extra = self.coordinator.data.get(f"{self._key}_attrs")
            if isinstance(extra, dict):
                attributes.update(extra)
        deprecation = DEPRECATED_SENSORS.get(self._key)
        if deprecation:
            attributes["deprecated"] = deprecation
        return attributes or None

    @property
    def available(self) -> bool:
        """Mark unavailable if the coordinator failed or has no value for this key."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self.coordinator.data.get(self._key) is not None
        )
