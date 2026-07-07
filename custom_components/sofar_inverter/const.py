"""Constants and register/sensor maps for the Sofar Inverter Modbus TCP integration.

The register definitions, scaling and control protocols are ported directly from
the Sofar2mqtt ESP firmware (https://github.com/cmcgerty/Sofar2MQTT), but driven
over Modbus TCP instead of RS485/MQTT.

Three inverter families are supported, exactly as in the firmware:
  * ME3000      -> Sofar ME3000SP
  * HYD-ES      -> Sofar HYD-xx00-ES / -EP (the firmware's "HYBRID")
  * HYD-EP/KTL  -> Sofar HYD-xx00-EP / -KTL three phase (the firmware's "HYDV2")
"""
from __future__ import annotations

from collections import namedtuple

DOMAIN = "sofar_inverter"

# ---- Config keys -----------------------------------------------------------
CONF_NAME = "name"
CONF_MODEL = "model"
CONF_SLAVE = "slave"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_ENABLE_CONTROL = "enable_control"
CONF_MAX_POWER = "max_power"

# ---- Defaults --------------------------------------------------------------
DEFAULT_PORT = 502
DEFAULT_SLAVE = 1
DEFAULT_SCAN_INTERVAL = 10
DEFAULT_MAX_POWER = 3000

# ---- Model keys ------------------------------------------------------------
MODEL_ME3000 = "me3000"
MODEL_HYD_ES = "hyd_es"
MODEL_HYD_EP_KTL = "hyd_ep_ktl"

MODEL_LABELS = {
    MODEL_ME3000: "Sofar ME3000SP",
    MODEL_HYD_ES: "Sofar HYD-ES / HYD-EP (single phase hybrid)",
    MODEL_HYD_EP_KTL: "Sofar HYD-EP / HYD-KTL (three phase hybrid)",
}

# ---- Control protocols -----------------------------------------------------
# ME3000 / HYD-ES use the proprietary Sofar "passive mode" function code 0x42.
# HYD-EP/KTL use a standard write-multiple-registers to the passive control reg.
PROTO_PASSIVE_FN42 = "passive_fn42"
PROTO_PASSIVE_REG = "passive_reg"

# Passive mode function-code 0x42 commands (ME3000 / HYD-ES)
SOFAR_FN_STANDBY = 0x0100
SOFAR_FN_DISCHARGE = 0x0101
SOFAR_FN_CHARGE = 0x0102
SOFAR_FN_AUTO = 0x0103
SOFAR_PARAM_STANDBY = 0x5555

# HYD-EP/KTL passive control register (writes 6x 16-bit regs = desired32, min32, max32)
SOFAR2_REG_PASSIVECONTROL = 0x1187

# ---- Control modes (exposed via the "Battery Mode" select) -----------------
MODE_NONE = "no_override"
MODE_STANDBY = "standby"
MODE_AUTO = "auto"
MODE_BATTERY_SAVE = "battery_save"
MODE_CHARGE = "charge"
MODE_DISCHARGE = "discharge"

# ---- Run-state text maps (from firmware runStateME3000 / runStateHYBRID) ----
RUNSTATE_ME3000 = {
    0: "Standby",
    1: "Check",
    2: "Charging",
    3: "Check Discharge",
    4: "Discharging",
    5: "EPS Check",
    6: "EPS State",
    7: "Fault",
}

# HYD-ES and HYD-EP/KTL share the same run-state map
RUNSTATE_HYBRID = {
    0: "Standby",
    1: "Check",
    2: "Normal",
    3: "EPS State",
    4: "Fault",
    5: "Permanent Fault",
    6: "Upgrading",
    7: "Self Charging",
}

# ---- Scaling helpers (mirror the firmware calculator enum) -----------------
NOCALC = 1.0
DIV10 = 0.1
DIV100 = 0.01
MUL10 = 10.0
MUL100 = 100.0
COMBINE = 1.0  # 32-bit value, no extra scaling

# A single sensor register definition.
#   key      : stable identifier (matches the Sofar2mqtt MQTT field name)
#   register : starting Modbus holding-register address
#   count    : number of 16-bit registers (1 = 16-bit, 2 = 32-bit)
#   signed   : whether the value is two's-complement signed
#   scale    : multiplier applied to the raw value
#   is_state : True for the running_state register (decoded to text)
SofarSensor = namedtuple(
    "SofarSensor", ["key", "register", "count", "signed", "scale", "is_state"]
)


def _s(key, register, count, signed, scale, is_state=False):
    return SofarSensor(key, register, count, signed, scale, is_state)


# ===========================================================================
# ME3000 register map (0x0200 base) — ported from Sofar2mqtt mqtt_status_reads
# ===========================================================================
SENSORS_ME3000: list[SofarSensor] = [
    _s("running_state",      0x0200, 1, False, NOCALC, is_state=True),
    _s("grid_voltage",       0x0206, 1, False, DIV10),
    _s("grid_current",       0x0207, 1, True,  DIV100),
    _s("grid_freq",          0x020C, 1, False, DIV100),
    _s("grid_power",         0x0212, 1, True,  MUL10),
    _s("battery_power",      0x020D, 1, True,  MUL10),
    _s("battery_voltage",    0x020E, 1, False, DIV100),
    _s("battery_current",    0x020F, 1, True,  DIV100),
    _s("inverter_power",     0x0214, 1, True,  MUL10),
    _s("battery_soc",        0x0210, 1, False, NOCALC),
    _s("battery_soh",        0x0237, 1, False, NOCALC),
    _s("battery_temp",       0x0211, 1, True,  NOCALC),
    _s("battery_cycles",     0x022C, 1, False, NOCALC),
    _s("consumption",        0x0213, 1, True,  MUL10),
    _s("solar_pv",           0x0215, 1, False, MUL10),
    _s("solar_pv_amps",      0x0236, 1, False, NOCALC),
    _s("today_exported",     0x0219, 1, False, DIV100),
    _s("today_purchase",     0x021A, 1, False, DIV100),
    _s("today_generation",   0x0218, 1, False, DIV100),
    _s("today_consumption",  0x021B, 1, False, DIV100),
    _s("today_charged",      0x0224, 1, False, DIV100),
    _s("today_discharged",   0x0225, 1, False, DIV100),
    _s("total_exported",     0x021E, 2, False, COMBINE),
    _s("total_purchase",     0x0220, 2, False, COMBINE),
    _s("total_generation",   0x021C, 2, False, COMBINE),
    _s("total_consumption",  0x0222, 2, False, COMBINE),
    _s("total_charged",      0x0226, 2, False, COMBINE),
    _s("total_discharged",   0x0228, 2, False, COMBINE),
    _s("inverter_temp",      0x0238, 1, True,  NOCALC),
    _s("inverter_hs_temp",   0x0239, 1, True,  NOCALC),
    _s("working_mode",       0x1200, 1, False, NOCALC),
]

# ===========================================================================
# HYD-ES register map (0x0200 base) — firmware "HYBRID"
# ===========================================================================
SENSORS_HYD_ES: list[SofarSensor] = [
    _s("running_state",      0x0200, 1, False, NOCALC, is_state=True),
    _s("grid_voltage",       0x0206, 1, False, DIV10),
    _s("grid_current",       0x0207, 1, True,  DIV100),
    _s("grid_freq",          0x020C, 1, False, DIV100),
    _s("grid_power",         0x0212, 1, True,  MUL10),
    _s("battery_power",      0x020D, 1, True,  MUL10),
    _s("battery_voltage",    0x020E, 1, False, DIV10),
    _s("battery_current",    0x020F, 1, True,  DIV100),
    _s("inverter_power",     0x0214, 1, True,  MUL10),
    _s("battery_soc",        0x0210, 1, False, NOCALC),
    _s("battery_soh",        0x0237, 1, False, NOCALC),
    _s("battery_temp",       0x0211, 1, True,  NOCALC),
    _s("battery_cycles",     0x022C, 1, False, NOCALC),
    _s("consumption",        0x0213, 1, True,  MUL10),
    _s("solar_pv",           0x0215, 1, False, MUL10),
    _s("solar_pv_amps",      0x0236, 1, False, NOCALC),
    _s("solar_pv1",          0x0252, 1, False, MUL10),
    _s("solar_pv2",          0x0255, 1, False, MUL10),
    _s("today_generation",   0x0218, 1, False, DIV100),
    _s("today_consumption",  0x021B, 1, False, DIV100),
    _s("today_exported",     0x0219, 1, False, DIV100),
    _s("today_purchase",     0x021A, 1, False, DIV100),
    _s("today_charged",      0x0224, 1, False, DIV100),
    _s("today_discharged",   0x0225, 1, False, DIV100),
    _s("total_generation",   0x021C, 2, False, COMBINE),
    _s("total_consumption",  0x0222, 2, False, COMBINE),
    _s("total_exported",     0x021E, 2, False, COMBINE),
    _s("total_purchase",     0x0220, 2, False, COMBINE),
    _s("total_charged",      0x0226, 2, False, COMBINE),
    _s("total_discharged",   0x0228, 2, False, COMBINE),
    _s("inverter_temp",      0x0238, 1, True,  NOCALC),
    _s("inverter_hs_temp",   0x0239, 1, True,  NOCALC),
    _s("working_mode",       0x1200, 1, False, NOCALC),
]

# ===========================================================================
# HYD-EP/KTL register map — firmware "HYDV2"
# Registers live in several blocks (0x0400 system, 0x0480 grid, 0x0580 PV,
# 0x0600 battery, 0x0680 power). 32-bit energy values are NOT byte-combined the
# same way; the firmware applies DIV100 (daily) / DIV10 (total) to a 32-bit reg.
# ===========================================================================
SENSORS_HYD_EP_KTL: list[SofarSensor] = [
    _s("running_state",      0x0404, 1, False, NOCALC, is_state=True),
    _s("inverter_temp",      0x0418, 1, True,  NOCALC),
    _s("inverter_hs_temp",   0x041A, 1, True,  NOCALC),
    _s("grid_freq",          0x0484, 1, False, DIV100),
    _s("inverter_power",     0x0485, 1, True,  MUL10),
    _s("grid_power",         0x0488, 1, True,  MUL10),
    _s("grid_voltage",       0x048D, 1, False, DIV10),
    _s("consumption",        0x04AF, 1, True,  MUL10),
    _s("solar_pv1_volt",     0x0584, 1, False, DIV10),
    _s("solar_pv1_current",  0x0585, 1, False, DIV100),
    _s("solar_pv1",          0x0586, 1, False, MUL10),
    _s("solar_pv2_volt",     0x0587, 1, False, DIV10),
    _s("solar_pv2_current",  0x0588, 1, False, DIV100),
    _s("solar_pv2",          0x0589, 1, False, MUL10),
    _s("solar_pv",           0x05C4, 1, False, MUL100),
    _s("battery_voltage",    0x0604, 1, False, DIV10),
    _s("battery_current",    0x0605, 1, True,  DIV100),
    _s("battery_power",      0x0606, 1, True,  MUL10),
    _s("battery_temp",       0x0607, 1, True,  NOCALC),
    _s("battery_soc",        0x0608, 1, False, NOCALC),
    _s("battery_soh",        0x0609, 1, False, NOCALC),
    _s("battery_cycles",     0x060A, 1, False, NOCALC),
    _s("battery_total_power", 0x0667, 1, True, MUL100),
    _s("battery_avg_soc",    0x0668, 1, False, NOCALC),
    _s("battery_avg_soh",    0x0669, 1, False, NOCALC),
    _s("today_generation",   0x0684, 2, False, DIV100),
    _s("total_generation",   0x0686, 2, False, DIV10),
    _s("today_consumption",  0x0688, 2, False, DIV100),
    _s("total_consumption",  0x068A, 2, False, DIV10),
    _s("today_purchase",     0x068C, 2, False, DIV100),
    _s("total_purchase",     0x068E, 2, False, DIV10),
    _s("today_exported",     0x0690, 2, False, DIV100),
    _s("total_exported",     0x0692, 2, False, DIV10),
    _s("today_charged",      0x0694, 2, False, DIV100),
    _s("total_charged",      0x0696, 2, False, DIV10),
    _s("today_discharged",   0x0698, 2, False, DIV100),
    _s("total_discharged",   0x069A, 2, False, DIV10),
    _s("working_mode",       0x1110, 1, False, NOCALC),
]

# Second-battery registers (HYD-EP/KTL only) — only added when a 2nd battery
# is detected (battery2_voltage > 0), matching firmware behaviour.
SENSORS_HYD_EP_KTL_BATTERY2: list[SofarSensor] = [
    _s("battery2_voltage",   0x060B, 1, False, DIV10),
    _s("battery2_current",   0x060C, 1, True,  DIV100),
    _s("battery2_power",     0x060D, 1, True,  MUL10),
    _s("battery2_temp",      0x060E, 1, True,  NOCALC),
    _s("battery2_soc",       0x060F, 1, False, NOCALC),
    _s("battery2_soh",       0x0610, 1, False, NOCALC),
    _s("battery2_cycles",    0x0611, 1, False, NOCALC),
]

# Map model -> (sensors, control protocol, run-state map)
MODEL_CONFIG = {
    MODEL_ME3000: {
        "sensors": SENSORS_ME3000,
        "protocol": PROTO_PASSIVE_FN42,
        "runstate": RUNSTATE_ME3000,
    },
    MODEL_HYD_ES: {
        "sensors": SENSORS_HYD_ES,
        "protocol": PROTO_PASSIVE_FN42,
        "runstate": RUNSTATE_HYBRID,
    },
    MODEL_HYD_EP_KTL: {
        "sensors": SENSORS_HYD_EP_KTL,
        "protocol": PROTO_PASSIVE_REG,
        "runstate": RUNSTATE_HYBRID,
    },
}

# ---- Sensor presentation metadata ------------------------------------------
# key -> (label, unit, device_class, state_class, precision, icon)
# device_class / state_class strings are mapped to HA enums in sensor.py.
SENSOR_META: dict[str, tuple] = {
    "running_state":     ("Running State", None, None, None, None, "mdi:state-machine"),
    "working_mode":      ("Working Mode", None, None, None, None, "mdi:cog"),
    "grid_voltage":      ("Grid Voltage", "V", "voltage", "measurement", 1, None),
    "grid_current":      ("Grid Current", "A", "current", "measurement", 2, None),
    "grid_freq":         ("Grid Frequency", "Hz", "frequency", "measurement", 2, None),
    "grid_power":        ("Grid Power", "W", "power", "measurement", 0, None),
    "battery_power":     ("Battery Power", "W", "power", "measurement", 0, None),
    "battery_voltage":   ("Battery Voltage", "V", "voltage", "measurement", 2, None),
    "battery_current":   ("Battery Current", "A", "current", "measurement", 2, None),
    "inverter_power":    ("Inverter Power", "W", "power", "measurement", 0, None),
    "battery_soc":       ("Battery SOC", "%", "battery", "measurement", 0, None),
    "battery_soh":       ("Battery SOH", "%", None, "measurement", 0, "mdi:battery-heart-variant"),
    "battery_temp":      ("Battery Temperature", "°C", "temperature", "measurement", 0, None),
    "battery_cycles":    ("Battery Cycles", None, None, "measurement", 0, "mdi:battery-sync"),
    "consumption":       ("Consumption", "W", "power", "measurement", 0, None),
    "solar_pv":          ("Solar PV Power", "W", "power", "measurement", 0, "mdi:solar-power"),
    "solar_pv_amps":     ("Solar PV Current", "A", "current", "measurement", 2, None),
    "solar_pv1":         ("Solar PV1 Power", "W", "power", "measurement", 0, "mdi:solar-power"),
    "solar_pv2":         ("Solar PV2 Power", "W", "power", "measurement", 0, "mdi:solar-power"),
    "solar_pv1_volt":    ("Solar PV1 Voltage", "V", "voltage", "measurement", 1, None),
    "solar_pv2_volt":    ("Solar PV2 Voltage", "V", "voltage", "measurement", 1, None),
    "solar_pv1_current": ("Solar PV1 Current", "A", "current", "measurement", 2, None),
    "solar_pv2_current": ("Solar PV2 Current", "A", "current", "measurement", 2, None),
    "today_generation":  ("Today Generation", "kWh", "energy", "total_increasing", 2, None),
    "today_consumption": ("Today Consumption", "kWh", "energy", "total_increasing", 2, None),
    "today_exported":    ("Today Exported", "kWh", "energy", "total_increasing", 2, None),
    "today_purchase":    ("Today Purchased", "kWh", "energy", "total_increasing", 2, None),
    "today_charged":     ("Today Charged", "kWh", "energy", "total_increasing", 2, None),
    "today_discharged":  ("Today Discharged", "kWh", "energy", "total_increasing", 2, None),
    "total_generation":  ("Total Generation", "kWh", "energy", "total_increasing", 1, None),
    "total_consumption": ("Total Consumption", "kWh", "energy", "total_increasing", 1, None),
    "total_exported":    ("Total Exported", "kWh", "energy", "total_increasing", 1, None),
    "total_purchase":    ("Total Purchased", "kWh", "energy", "total_increasing", 1, None),
    "total_charged":     ("Total Charged", "kWh", "energy", "total_increasing", 1, None),
    "total_discharged":  ("Total Discharged", "kWh", "energy", "total_increasing", 1, None),
    "inverter_temp":     ("Inverter Temperature", "°C", "temperature", "measurement", 0, None),
    "inverter_hs_temp":  ("Inverter Heatsink Temperature", "°C", "temperature", "measurement", 0, None),
    "battery_total_power": ("Battery Total Power", "W", "power", "measurement", 0, None),
    "battery_avg_soc":   ("Battery Average SOC", "%", "battery", "measurement", 0, None),
    "battery_avg_soh":   ("Battery Average SOH", "%", None, "measurement", 0, "mdi:battery-heart-variant"),
    "battery2_voltage":  ("Battery 2 Voltage", "V", "voltage", "measurement", 2, None),
    "battery2_current":  ("Battery 2 Current", "A", "current", "measurement", 2, None),
    "battery2_power":    ("Battery 2 Power", "W", "power", "measurement", 0, None),
    "battery2_temp":     ("Battery 2 Temperature", "°C", "temperature", "measurement", 0, None),
    "battery2_soc":      ("Battery 2 SOC", "%", "battery", "measurement", 0, None),
    "battery2_soh":      ("Battery 2 SOH", "%", None, "measurement", 0, "mdi:battery-heart-variant"),
    "battery2_cycles":   ("Battery 2 Cycles", None, None, "measurement", 0, "mdi:battery-sync"),
}
