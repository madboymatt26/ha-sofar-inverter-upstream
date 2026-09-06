"""Sofar Inverter Modbus TCP integration for Home Assistant."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ENABLE_CLOCK_MONITOR,
    CONF_ENABLE_CONTROL,
    CONF_ENABLE_SCHEDULE,
    CONF_MAX_POWER,
    CONF_MODEL,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    DEFAULT_ENABLE_CLOCK_MONITOR,
    DEFAULT_ENABLE_SCHEDULE,
    DEFAULT_MAX_POWER,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE,
    DOMAIN,
    OPTION_KEYS,
)
from .coordinator import SofarCoordinator

_LOGGER = logging.getLogger(__name__)

CURRENT_VERSION = 2


def get_setting(entry: ConfigEntry, key: str, default):
    """Read a tunable with options taking precedence over the original data.

    Entries created before the options flow existed keep their values in
    ``data``; nothing is rewritten there, so downgrading stays possible.
    """
    if key in entry.options:
        return entry.options[key]
    return entry.data.get(key, default)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate an existing config entry in place.

    Version 1 -> 2 introduces the options flow. The tunable values are copied
    from ``data`` into ``options`` so the options form opens pre-filled with what
    the entry is actually using. No entity, device or entry unique_id is touched,
    so existing entities keep their identity.
    """
    if entry.version >= CURRENT_VERSION:
        return True

    _LOGGER.debug(
        "Migrating Sofar config entry %s from version %s to %s",
        entry.entry_id, entry.version, CURRENT_VERSION,
    )

    options = dict(entry.options)
    defaults = {
        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        CONF_ENABLE_CONTROL: False,
        CONF_MAX_POWER: DEFAULT_MAX_POWER,
        CONF_ENABLE_SCHEDULE: DEFAULT_ENABLE_SCHEDULE,
        CONF_ENABLE_CLOCK_MONITOR: DEFAULT_ENABLE_CLOCK_MONITOR,
    }
    for key in OPTION_KEYS:
        if key not in options:
            options[key] = entry.data.get(key, defaults[key])

    try:
        hass.config_entries.async_update_entry(
            entry, options=options, version=CURRENT_VERSION
        )
    except TypeError:
        # Older cores do not accept the version keyword.
        entry.version = CURRENT_VERSION
        hass.config_entries.async_update_entry(entry, options=options)

    return True


def _platforms_for(coordinator: SofarCoordinator) -> list[Platform]:
    """Platforms to forward, matching the gating inside each platform module."""
    platforms: list[Platform] = [Platform.SENSOR]

    if coordinator.binary_sensor_keys:
        platforms.append(Platform.BINARY_SENSOR)

    if coordinator.enable_control or coordinator.supports_schedule:
        platforms.append(Platform.NUMBER)

    if coordinator.enable_control or (
        coordinator.supports_working_mode_write and coordinator.supports_schedule
    ):
        platforms.append(Platform.SELECT)

    if coordinator.enable_control or coordinator.supports_clock:
        platforms.append(Platform.BUTTON)

    if coordinator.supports_schedule:
        platforms += [Platform.TIME, Platform.SWITCH]

    return platforms


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sofar Inverter from a config entry."""
    host: str = entry.data[CONF_HOST]
    port: int = entry.data[CONF_PORT]
    slave: int = entry.data.get(CONF_SLAVE, DEFAULT_SLAVE)
    model: str = entry.data[CONF_MODEL]

    max_power: int = int(get_setting(entry, CONF_MAX_POWER, DEFAULT_MAX_POWER))
    scan_interval: int = int(
        get_setting(entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )
    enable_control: bool = bool(get_setting(entry, CONF_ENABLE_CONTROL, False))
    enable_schedule: bool = bool(
        get_setting(entry, CONF_ENABLE_SCHEDULE, DEFAULT_ENABLE_SCHEDULE)
    )
    enable_clock_monitor: bool = bool(
        get_setting(entry, CONF_ENABLE_CLOCK_MONITOR, DEFAULT_ENABLE_CLOCK_MONITOR)
    )

    coordinator = SofarCoordinator(
        hass=hass,
        host=host,
        port=port,
        slave=slave,
        model=model,
        max_power=max_power,
        update_interval=timedelta(seconds=scan_interval),
        enable_control=enable_control,
        enable_schedule=enable_schedule,
        enable_clock_monitor=enable_clock_monitor,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    platforms = _platforms_for(coordinator)

    # Stash the active platform list so unload mirrors it.
    hass.data[DOMAIN].setdefault("_platforms", {})[entry.entry_id] = platforms

    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    # Reload when the options change so the new interval / feature set applies.
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry after its options were updated."""
    await hass.config_entries.async_reload(entry.entry_id)


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
