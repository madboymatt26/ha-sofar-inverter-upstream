"""Number platform for the Sofar Inverter charge/discharge power setpoint."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_MODEL,
    CONF_NAME,
    CONF_SLAVE,
    DOMAIN,
    MODE_CHARGE,
    MODE_DISCHARGE,
    MODEL_LABELS,
)
from .coordinator import SofarCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Sofar power-setpoint number entity."""
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

    async_add_entities(
        [SofarPowerSetpoint(coordinator, entry.entry_id, inverter_name, device_info)]
    )


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
        inverter_name: str,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator)
        self._attr_name = "Battery Power Setpoint"
        self._attr_unique_id = f"{entry_id}_power_setpoint"
        self._attr_native_min_value = 0
        self._attr_native_max_value = float(coordinator.max_power)
        self._attr_device_info = device_info

    @property
    def native_value(self) -> float:
        """Return the current setpoint."""
        return float(self.coordinator.active_power)

    async def async_set_native_value(self, value: float) -> None:
        """Store the new setpoint and re-apply if charging/discharging."""
        power = int(value)
        self.coordinator.set_active_mode(self.coordinator.active_mode, power)
        # If we are actively charging/discharging, push the new level now.
        if self.coordinator.active_mode in (MODE_CHARGE, MODE_DISCHARGE):
            await self.coordinator.async_set_mode(self.coordinator.active_mode, power)
        self.async_write_ha_state()
