"""Sensor platform for the Sofar Inverter Modbus TCP integration."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_MODEL,
    CONF_NAME,
    CONF_SLAVE,
    DOMAIN,
    MODEL_LABELS,
    SENSOR_META,
)
from .coordinator import SofarCoordinator

_LOGGER = logging.getLogger(__name__)

DEVICE_CLASS_MAP: dict[str, SensorDeviceClass | None] = {
    "voltage": SensorDeviceClass.VOLTAGE,
    "current": SensorDeviceClass.CURRENT,
    "power": SensorDeviceClass.POWER,
    "energy": SensorDeviceClass.ENERGY,
    "frequency": SensorDeviceClass.FREQUENCY,
    "temperature": SensorDeviceClass.TEMPERATURE,
    "battery": SensorDeviceClass.BATTERY,
    None: None,
}

STATE_CLASS_MAP: dict[str, SensorStateClass | None] = {
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
    host: str = entry.data[CONF_HOST]
    port: int = entry.data[CONF_PORT]
    slave: int = entry.data.get(CONF_SLAVE, 1)
    model: str = entry.data[CONF_MODEL]

    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{host}_{port}_{slave}")},
        name=inverter_name,
        manufacturer="Sofar Solar",
        model=MODEL_LABELS.get(model, model),
        configuration_url=f"http://{host}",
    )

    entities: list[SofarSensor] = []
    seen: set[str] = set()
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

    async_add_entities(entities)


class SofarSensor(CoordinatorEntity, SensorEntity):
    """A single value read from a Sofar inverter register."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SofarCoordinator,
        entry_id: str,
        inverter_name: str,
        device_info: DeviceInfo,
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

    @property
    def native_value(self):
        """Return the current value for this register."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._key)

    @property
    def available(self) -> bool:
        """Mark unavailable if the coordinator failed or has no value for this key."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self.coordinator.data.get(self._key) is not None
        )
