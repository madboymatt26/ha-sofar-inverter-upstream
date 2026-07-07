"""Select platform for Sofar Inverter battery control mode.

Exposes the passive-mode commands from the Sofar2mqtt firmware as a single
selectable mode. Selecting charge/discharge uses the power level configured by
the "Battery Power Setpoint" number entity.
"""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
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
    MODE_AUTO,
    MODE_BATTERY_SAVE,
    MODE_CHARGE,
    MODE_DISCHARGE,
    MODE_NONE,
    MODE_STANDBY,
    MODEL_LABELS,
)
from .coordinator import SofarCoordinator

_LOGGER = logging.getLogger(__name__)

# Friendly label -> internal mode
MODE_OPTIONS: dict[str, str] = {
    "No Override": MODE_NONE,
    "Auto (Self Use)": MODE_AUTO,
    "Battery Save": MODE_BATTERY_SAVE,
    "Charge": MODE_CHARGE,
    "Discharge": MODE_DISCHARGE,
    "Standby": MODE_STANDBY,
}
MODE_TO_LABEL = {v: k for k, v in MODE_OPTIONS.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Sofar battery-mode select entity."""
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
        [SofarModeSelect(coordinator, entry.entry_id, inverter_name, device_info)]
    )


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
        inverter_name: str,
        device_info: DeviceInfo,
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

    async def async_select_option(self, option: str) -> None:
        """Apply the chosen mode."""
        mode = MODE_OPTIONS.get(option, MODE_NONE)
        power = self.coordinator.active_power
        success = await self.coordinator.async_set_mode(mode, power)
        if not success:
            _LOGGER.error("Failed to set Sofar battery mode to %s", option)
        self.async_write_ha_state()
