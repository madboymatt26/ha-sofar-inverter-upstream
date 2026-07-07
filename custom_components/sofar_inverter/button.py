"""Button platform for Sofar Inverter quick control actions."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_MODEL,
    CONF_NAME,
    CONF_SLAVE,
    DOMAIN,
    MODE_AUTO,
    MODE_STANDBY,
    MODEL_LABELS,
)
from .coordinator import SofarCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sofar control buttons."""
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
        [
            SofarModeButton(
                coordinator, entry.entry_id, inverter_name, device_info,
                "Set Auto Mode", MODE_AUTO, "auto", "mdi:autorenew",
            ),
            SofarModeButton(
                coordinator, entry.entry_id, inverter_name, device_info,
                "Set Standby", MODE_STANDBY, "standby", "mdi:power-standby",
            ),
        ]
    )


class SofarModeButton(ButtonEntity):
    """A button that applies a fixed control mode to the inverter."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SofarCoordinator,
        entry_id: str,
        inverter_name: str,
        device_info: DeviceInfo,
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
            _LOGGER.error("Failed to apply Sofar mode '%s'", self._mode)
