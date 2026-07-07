"""Sofar Inverter Modbus TCP integration for Home Assistant."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ENABLE_CONTROL,
    CONF_MAX_POWER,
    CONF_MODEL,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    DEFAULT_MAX_POWER,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE,
    DOMAIN,
)
from .coordinator import SofarCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sofar Inverter from a config entry."""
    host: str = entry.data[CONF_HOST]
    port: int = entry.data[CONF_PORT]
    slave: int = entry.data.get(CONF_SLAVE, DEFAULT_SLAVE)
    model: str = entry.data[CONF_MODEL]
    max_power: int = entry.data.get(CONF_MAX_POWER, DEFAULT_MAX_POWER)
    scan_interval: int = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    enable_control: bool = entry.data.get(CONF_ENABLE_CONTROL, False)

    coordinator = SofarCoordinator(
        hass=hass,
        host=host,
        port=port,
        slave=slave,
        model=model,
        max_power=max_power,
        update_interval=timedelta(seconds=scan_interval),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    platforms = [Platform.SENSOR]
    if enable_control:
        platforms += [Platform.SELECT, Platform.NUMBER, Platform.BUTTON]

    # Stash the active platform list so unload mirrors it.
    hass.data[DOMAIN].setdefault("_platforms", {})[entry.entry_id] = platforms

    await hass.config_entries.async_forward_entry_setups(entry, platforms)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    platforms = hass.data[DOMAIN].get("_platforms", {}).get(
        entry.entry_id, [Platform.SENSOR]
    )
    unload_ok = await hass.config_entries.async_unload_platforms(entry, platforms)
    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id, None)
        hass.data[DOMAIN].get("_platforms", {}).pop(entry.entry_id, None)
        if coordinator is not None:
            # Releases this entry's hold on the shared gateway connection and
            # tears it down (client + heartbeat) when it was the last user.
            await coordinator.async_shutdown()
    return unload_ok
