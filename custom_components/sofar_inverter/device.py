"""Shared device-registry information for the Sofar Inverter integration.

Every platform used to build this dict itself, which risked the copies drifting
apart. The identity-bearing fields are frozen:

  * ``identifiers`` keys the device in the device registry — changing it would
    create a second device and detach every existing entity.
  * ``name`` feeds the friendly name and, with ``has_entity_name``, the
    generated entity_id of every entity on the device.
  * ``model`` stays the static family label rather than the detected product
    code, so the device page does not change on existing installs.

``sw_version``, ``hw_version`` and ``serial_number`` are purely additive: they
populate previously empty fields once the inverter has been queried.
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.device_registry import DeviceInfo

from .const import CONF_MODEL, CONF_NAME, CONF_SLAVE, DEFAULT_SLAVE, DOMAIN, MODEL_LABELS


def build_device_info(entry: ConfigEntry, coordinator=None) -> DeviceInfo:
    """Return the DeviceInfo for this config entry."""
    host: str = entry.data[CONF_HOST]
    port: int = entry.data[CONF_PORT]
    slave: int = entry.data.get(CONF_SLAVE, DEFAULT_SLAVE)
    model: str = entry.data[CONF_MODEL]
    inverter_name: str = entry.data[CONF_NAME]

    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{host}_{port}_{slave}")},
        name=inverter_name,
        manufacturer="Sofar Solar",
        model=MODEL_LABELS.get(model, model),
        configuration_url=f"http://{host}",
    )

    if coordinator is not None:
        if getattr(coordinator, "arm_version", None):
            device_info["sw_version"] = coordinator.arm_version
        if getattr(coordinator, "hardware_version", None):
            device_info["hw_version"] = coordinator.hardware_version
        if getattr(coordinator, "serial_number", None):
            device_info["serial_number"] = coordinator.serial_number

    return device_info
