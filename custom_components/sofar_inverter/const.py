"""Constants and register/sensor maps for the Sofar Inverter Modbus TCP integration.

The register definitions, scaling and control protocols are ported directly from
the Sofar2mqtt ESP firmware (https://github.com/cmcgerty/Sofar2MQTT), driven over
Modbus TCP instead of RS485/MQTT, and extended from the official Sofar
"ModBus-RTU Protocol" document for HYD / ME3000SP (2020-11-23, 66 pages).

Three inverter families are supported, exactly as in the firmware:
  * ME3000      -> Sofar ME3000SP
  * HYD-ES      -> Sofar HYD-xx00-ES / -EP (the firmware's "HYBRID")
  * HYD-EP/KTL  -> Sofar HYD-xx00-EP / -KTL three phase (the firmware's "HYDV2")

IMPORTANT — entity identity
---------------------------
Every ``key`` in the sensor maps below becomes part of an entity's unique_id
(``<entry_id>_<key>``), so keys are a permanent API. Existing keys, and the
``SENSOR_META`` label / unit / device_class / state_class for those keys, must
never change: renaming a key orphans dashboards and automations, and changing a
unit or state_class corrupts or resets recorder long-term statistics. Corrections
are made by adding a new key alongside the old one, never by re-keying.

IMPORTANT — no Home Assistant imports
-------------------------------------
This module must stay free of Home Assistant imports so that
``scripts/entity_inventory.py`` can import it standalone to verify entity
identity without a Home Assistant install. Presentation values are plain strings
and are mapped to HA enums in the platform modules.
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
# Added in config-entry version 2.
CONF_ENABLE_SCHEDULE = "enable_schedule"
CONF_ENABLE_CLOCK_MONITOR = "enable_clock_monitor"

# Tunables that the options flow may override. Anything listed here is read
# with "options first, then data" precedence so that pre-options-flow entries
# keep working untouched.
OPTION_KEYS = (
    CONF_SCAN_INTERVAL,
    CONF_ENABLE_CONTROL,
    CONF_MAX_POWER,
    CONF_ENABLE_SCHEDULE,
    CONF_ENABLE_CLOCK_MONITOR,
)

# ---- Defaults --------------------------------------------------------------
DEFAULT_PORT = 502
DEFAULT_SLAVE = 1
DEFAULT_SCAN_INTERVAL = 10
DEFAULT_MAX_POWER = 3000
DEFAULT_ENABLE_SCHEDULE = False
DEFAULT_ENABLE_CLOCK_MONITOR = True

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
# Protocol doc p.62 lists Auto (0x0103) with default/range value 0x5555, the same
# sentinel as Standby. The firmware this integration was ported from sent 0x0000.
SOFAR_PARAM_AUTO = 0x5555

# HYD-EP/KTL passive control register (writes 6x 16-bit regs = desired32, min32, max32)
SOFAR2_REG_PASSIVECONTROL = 0x1187

# ---- Modbus / Sofar function codes -----------------------------------------
FN_READ_HOLDING = 0x03           # standard: read holding registers
FN_READ_INPUT = 0x04             # standard: read input registers (0x1000+ range)
FN_WRITE_REGISTERS = 0x10        # standard write-multiple; also Sofar "read time"
FN_BROADCAST_SET_TIME = 0x02     # broadcast auto-timing (doc 2.1.1)
FN_READ_DEVICE_INFO_EXT = 0x21   # ext code for 0x2000-0x20FF (doc table 1.4)
FN_READ_EEPROM = 0x50            # history energy / event list (doc 2.8)

# Broadcast slave address: accepted but never answered (doc 2.1 / 2.23).
SOFAR_BROADCAST_ADDRESS = 0x88

# ---- Register addresses used for non-sensor operations ---------------------
REG_WORKING_MODE = 0x1200        # ME3000 / HYD-ES working mode (R/W)
REG_WORKING_MODE_HYDV2 = 0x1110  # HYD-EP/KTL working mode (read only here)
REG_TIMING_BLOCK = 0x1201        # 0x1201-0x1206, written as one 6-register block
REG_TOU_RULE_NUMBER = 0x1207     # must be written before other TOU registers
REG_TOU_BLOCK = 0x1208           # 0x1208-0x120F, written as one 8-register block
REG_BATTERY_PARAMS = 0x10B0      # 0x10B0-0x10BC, read only in this integration
REG_SYSTEM_TIME = 0x8000         # read via FN_WRITE_REGISTERS (doc 2.11)
REG_SET_TIME = 0x5000            # broadcast write via FN_BROADCAST_SET_TIME
REG_DEVICE_INFO = 0x2000         # 0x2000-0x200F product/serial/versions
REG_EVENT_RECORD = 0x6005        # recent Nth event record (doc 2.8.2)

# ---- Working modes (register 0x1200) ---------------------------------------
WORKING_MODE_AUTO = 0
WORKING_MODE_TOU = 1
WORKING_MODE_TIMING = 2
WORKING_MODE_PASSIVE = 3

WORKING_MODE_MAP = {
    WORKING_MODE_AUTO: "Auto",
    WORKING_MODE_TOU: "Time of Use",
    WORKING_MODE_TIMING: "Timing",
    WORKING_MODE_PASSIVE: "Passive",
}
WORKING_MODE_REVERSE = {v: k for k, v in WORKING_MODE_MAP.items()}

# ---- Control modes (exposed via the "Battery Mode" select) -----------------
MODE_NONE = "no_override"
MODE_STANDBY = "standby"
MODE_AUTO = "auto"
MODE_BATTERY_SAVE = "battery_save"
MODE_CHARGE = "charge"
MODE_DISCHARGE = "discharge"

# Friendly labels for the Battery Mode select. These strings are recorded in
# Home Assistant history as entity states, so they must not be reworded.
# Insertion order defines the order shown in the UI.
MODE_LABELS: dict[str, str] = {
    MODE_NONE: "No Override",
    MODE_AUTO: "Auto (Self Use)",
    MODE_BATTERY_SAVE: "Battery Save",
    MODE_CHARGE: "Charge",
    MODE_DISCHARGE: "Discharge",
    MODE_STANDBY: "Standby",
}

# ---- Passive-mode command status (doc p.62) --------------------------------
# Low byte of the 0x42 response register: acceptance / rejection reason.
PASSIVE_STATUS_MAP = {
    0: "Accepted",
    1: "Rejected: invalid mode (inverter is not in Passive Mode)",
    2: "Rejected: CRC failed",
    3: "Rejected: inverter busy",
    4: "Rejected: invalid data",
}
PASSIVE_STATUS_ACCEPTED = 0

# High byte of the 0x42 response register: battery readiness flags.
PASSIVE_FLAG_CHARGE_READY = 0
PASSIVE_FLAG_DISCHARGE_READY = 1
PASSIVE_FLAG_BATTERY_FULL = 2
PASSIVE_FLAG_BATTERY_EMPTY = 3

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

# Run-state values that mean the inverter is running on its EPS/backup output.
EPS_RUNSTATES = {
    MODEL_ME3000: {5, 6},
    MODEL_HYD_ES: {3},
    MODEL_HYD_EP_KTL: {3},
}

# ---- Battery types (register 0x10B0) ---------------------------------------
BATTERY_TYPE_MAP = {
    0x0000: "DARFON",
    0x0001: "PYLON",
    0x0002: "SOLTARO",
    0x0003: "ALPHA.ESS",
    0x0004: "GENERAL",
    0x0100: "DEFAULT",
}

# ---- Country / grid code (register 0x023A) ---------------------------------
COUNTRY_CODE_MAP = {
    0: "Germany VDE4105", 1: "CEI0-21 Internal", 2: "Australia",
    3: "Spain RD1699", 4: "Turkey", 5: "Denmark", 6: "Greece Continent",
    7: "Netherlands", 8: "Belgium", 9: "UK-G59", 10: "China", 11: "France",
    12: "Poland", 13: "Germany BDEW", 14: "Germany VDE0126",
    15: "Italy CEI0-16", 16: "UK G83", 17: "Greece Island", 18: "EU EN50438",
    19: "EU EN61727", 20: "Korea", 21: "Sweden", 22: "Europe General",
    23: "CEI0-21 External", 24: "Cyprus", 25: "India", 26: "Philippines",
    27: "New Zealand", 28: "Reserve", 29: "Slovakia VSD", 30: "Slovakia SSE",
    31: "Slovakia ZSD", 32: "CEI0-21 In Areti", 33: "Ukraine",
}

# ---- Rated power detection from the barcode (doc 2.3.4) --------------------
# Barcode layout: digit 1 = brand, digits 2-3 = family, digit 4 = region,
# digits 5-6 = configuration, digits 7-8 = power. Only the battery-storage and
# single-phase-hybrid families are decoded here; everything else returns None so
# that the configured maximum power is used unchanged.
BARCODE_FAMILY_ME3000 = "E1"   # 3KW/5KW energy storage system inverter
BARCODE_FAMILY_HYBRID = "M1"   # 3-6KW single-phase hybrid inverter

RATED_POWER_BY_FAMILY: dict[str, dict[str, int]] = {
    BARCODE_FAMILY_ME3000: {
        "30": 3000,   # ME3000SP
        "50": 5000,   # ME5000SP
    },
    BARCODE_FAMILY_HYBRID: {
        "30": 3000,
        "36": 3680,
        "40": 4000,
        "46": 4600,
        "50": 5000,
        "60": 6000,
    },
}

# Passive charge/discharge range documented for the smallest model in this PDF.
# Used only as a fallback when the rating cannot be determined AND the user has
# not configured a higher limit; never used to reduce a working configuration.
DOC_PASSIVE_POWER_LIMIT = 3000

# Firmware version (as an integer, "V120" -> 120) from which the battery
# charge/discharge energy counters at 0x0224-0x0229 are populated.
FW_BATTERY_ENERGY_COUNTERS = 120

# ---- Read batching ---------------------------------------------------------
# One RS485 hop at 9600 baud costs roughly 2ms per register of payload but tens
# of ms of fixed per-transaction overhead, so merging across small gaps is a net
# win while very large gaps are not.
MAX_BLOCK_REGISTERS = 64
MAX_BLOCK_GAP = 12

# How often to re-read the inverter RTC, and the drift that triggers a warning.
CLOCK_POLL_INTERVAL = 3600  # seconds
CLOCK_DRIFT_WARN_SECONDS = 120

# ---- Scaling helpers (mirror the firmware calculator enum) -----------------
NOCALC = 1.0
DIV10 = 0.1
DIV100 = 0.01
MUL10 = 10.0
MUL100 = 100.0
COMBINE = 1.0  # 32-bit value, no extra scaling

# A single sensor register definition.
#   key      : stable identifier (matches the Sofar2mqtt MQTT field name).
#              This becomes part of the entity unique_id — never change it.
#   register : starting Modbus holding-register address
#   count    : number of 16-bit registers (1 = 16-bit, 2 = 32-bit)
#   signed   : whether the value is two's-complement signed
#   scale    : multiplier applied to the raw value
#   is_state : True for the running_state register (decoded to text)
#   min_fw   : minimum ARM firmware version ("V120" -> 120) that populates this
#              register; below it the value is reported unavailable, not zero
SofarSensor = namedtuple(
    "SofarSensor",
    ["key", "register", "count", "signed", "scale", "is_state", "min_fw"],
    defaults=(False, None),
)


def _s(key, register, count, signed, scale, is_state=False, min_fw=None):
    return SofarSensor(key, register, count, signed, scale, is_state, min_fw)


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
    _s("today_charged",      0x0224, 1, False, DIV100, min_fw=FW_BATTERY_ENERGY_COUNTERS),
    _s("today_discharged",   0x0225, 1, False, DIV100, min_fw=FW_BATTERY_ENERGY_COUNTERS),
    _s("total_exported",     0x021E, 2, False, COMBINE),
    _s("total_purchase",     0x0220, 2, False, COMBINE),
    _s("total_generation",   0x021C, 2, False, COMBINE),
    _s("total_consumption",  0x0222, 2, False, COMBINE),
    _s("total_charged",      0x0226, 2, False, COMBINE, min_fw=FW_BATTERY_ENERGY_COUNTERS),
    _s("total_discharged",   0x0228, 2, False, COMBINE, min_fw=FW_BATTERY_ENERGY_COUNTERS),
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
    _s("today_charged",      0x0224, 1, False, DIV100, min_fw=FW_BATTERY_ENERGY_COUNTERS),
    _s("today_discharged",   0x0225, 1, False, DIV100, min_fw=FW_BATTERY_ENERGY_COUNTERS),
    _s("total_generation",   0x021C, 2, False, COMBINE),
    _s("total_consumption",  0x0222, 2, False, COMBINE),
    _s("total_exported",     0x021E, 2, False, COMBINE),
    _s("total_purchase",     0x0220, 2, False, COMBINE),
    _s("total_charged",      0x0226, 2, False, COMBINE, min_fw=FW_BATTERY_ENERGY_COUNTERS),
    _s("total_discharged",   0x0228, 2, False, COMBINE, min_fw=FW_BATTERY_ENERGY_COUNTERS),
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

# ===========================================================================
# NEW registers, ME3000 / HYD-ES only (the 0x02xx map this PDF documents).
# The HYD-EP/KTL equivalents live in the undocumented 0x04xx range and are
# deliberately not guessed at.
# ===========================================================================

# Raw fault/alarm bitfields. Decoded into readable text by the coordinator; the
# raw words are also exposed as disabled-by-default diagnostics so that a user
# can report an undecoded value.
SENSORS_FAULTS: list[SofarSensor] = [
    _s("fault_word_1",        0x0201, 1, False, NOCALC),
    _s("fault_word_2",        0x0202, 1, False, NOCALC),
    _s("fault_word_3",        0x0203, 1, False, NOCALC),
    _s("fault_word_4",        0x0204, 1, False, NOCALC),
    _s("fault_word_5",        0x0205, 1, False, NOCALC),
    _s("alarm_word",          0x022B, 1, False, NOCALC),
    _s("battery_fault_word_1", 0x023D, 1, False, NOCALC),
    _s("comm_board_word",     0x0242, 1, False, NOCALC),
]

# EPS / backup output.
SENSORS_EPS: list[SofarSensor] = [
    _s("eps_voltage",         0x0216, 1, False, DIV10),
    _s("eps_power",           0x0217, 1, False, MUL10),
]

# Full PV string telemetry (HYD-ES only; the ME3000SP has no PV input).
SENSORS_PV_STRINGS: list[SofarSensor] = [
    _s("pv1_voltage",         0x0250, 1, False, DIV10),
    _s("pv1_current",         0x0251, 1, False, DIV100),
    _s("pv2_voltage",         0x0253, 1, False, DIV10),
    _s("pv2_current",         0x0254, 1, False, DIV100),
]

# Additional diagnostics from the same contiguous sweep.
SENSORS_DIAGNOSTIC: list[SofarSensor] = [
    _s("countdown_time",      0x022A, 1, False, NOCALC),
    _s("bus_voltage",         0x022D, 1, False, DIV10),
    _s("llc_bus_voltage",     0x022E, 1, False, DIV10),
    _s("buck_current",        0x022F, 1, False, DIV100),
    _s("country_code",        0x023A, 1, False, NOCALC),
    _s("dci_current",         0x023B, 1, True,  NOCALC),
    _s("dci_voltage",         0x023C, 1, True,  DIV10),
    _s("today_generation_time", 0x0243, 1, False, NOCALC),
    _s("total_generation_time", 0x0244, 2, False, COMBINE),
    _s("pv1_insulation_resistance", 0x0246, 1, False, NOCALC),
    _s("pv2_insulation_resistance", 0x0247, 1, False, NOCALC),
    _s("pv_negative_insulation_resistance", 0x0248, 1, False, NOCALC),
]

# Battery configuration parameters (doc 2.3.2, read table). Exposed read-only:
# the read table (2.3.2) and the write table (2.4.2) disagree by two registers
# from 0x10B4 onward, so these must not be written until verified by read-back
# against real hardware.
SENSORS_BATTERY_PARAMS: list[SofarSensor] = [
    _s("battery_type",                  0x10B0, 1, False, NOCALC),
    _s("battery_capacity",              0x10B1, 1, False, NOCALC),
    _s("battery_max_charge_voltage",    0x10B3, 1, False, DIV10),
    _s("battery_max_charge_current",    0x10B4, 1, False, DIV100),
    _s("battery_overvoltage_protection", 0x10B5, 1, False, DIV10),
    _s("battery_min_discharge_voltage", 0x10B6, 1, False, DIV10),
    _s("battery_max_discharge_current", 0x10B7, 1, False, DIV100),
    _s("battery_undervoltage_protection", 0x10B8, 1, False, DIV10),
    _s("battery_dod",                   0x10B9, 1, False, NOCALC),
    _s("battery_shallow_dod",           0x10BA, 1, False, NOCALC),
    _s("battery_empty_voltage",         0x10BB, 1, False, DIV100),
    _s("battery_full_voltage",          0x10BC, 1, False, DIV100),
]

# Timing / Time-of-Use configuration registers. These are read into the
# coordinator so the schedule control entities can show the inverter's real
# values, but they are NOT turned into sensor entities (the control entities
# already display them). Write-only registers 0x1210-0x1215 are never read.
SCHEDULE_REGISTERS: list[SofarSensor] = [
    _s("sched_charge_start",     0x1201, 1, False, NOCALC),
    _s("sched_charge_end",       0x1202, 1, False, NOCALC),
    _s("sched_discharge_start",  0x1203, 1, False, NOCALC),
    _s("sched_discharge_end",    0x1204, 1, False, NOCALC),
    _s("sched_charge_power",     0x1205, 1, False, NOCALC),
    _s("sched_discharge_power",  0x1206, 1, False, NOCALC),
    _s("tou_rule_number",        0x1207, 1, False, NOCALC),
    _s("tou_charge_start",       0x1208, 1, False, NOCALC),
    _s("tou_charge_end",         0x1209, 1, False, NOCALC),
    _s("tou_soc",                0x120A, 1, False, NOCALC),
    _s("tou_power",              0x120B, 1, False, NOCALC),
    _s("tou_start_date",         0x120C, 1, False, NOCALC),
    _s("tou_end_date",           0x120D, 1, False, NOCALC),
    _s("tou_weekdays",           0x120E, 1, False, NOCALC),
    _s("tou_enabled",            0x120F, 1, False, NOCALC),
]

# Map model -> (sensors, control protocol, run-state map, extras)
MODEL_CONFIG = {
    MODEL_ME3000: {
        "sensors": (
            SENSORS_ME3000 + SENSORS_FAULTS + SENSORS_EPS
            + SENSORS_DIAGNOSTIC + SENSORS_BATTERY_PARAMS
        ),
        "protocol": PROTO_PASSIVE_FN42,
        "runstate": RUNSTATE_ME3000,
        "faults": True,
        "schedule": True,
        "clock": True,
        "working_mode_register": REG_WORKING_MODE,
    },
    MODEL_HYD_ES: {
        "sensors": (
            SENSORS_HYD_ES + SENSORS_FAULTS + SENSORS_EPS + SENSORS_PV_STRINGS
            + SENSORS_DIAGNOSTIC + SENSORS_BATTERY_PARAMS
        ),
        "protocol": PROTO_PASSIVE_FN42,
        "runstate": RUNSTATE_HYBRID,
        "faults": True,
        "schedule": True,
        "clock": True,
        "working_mode_register": REG_WORKING_MODE,
    },
    MODEL_HYD_EP_KTL: {
        "sensors": SENSORS_HYD_EP_KTL,
        "protocol": PROTO_PASSIVE_REG,
        "runstate": RUNSTATE_HYBRID,
        "faults": False,
        "schedule": False,
        "clock": False,
        "working_mode_register": REG_WORKING_MODE_HYDV2,
    },
}


# ===========================================================================
# Derived (computed) sensors. These have no register of their own — the
# coordinator calculates them from register values it already read, so they cost
# no extra bus traffic.
# ===========================================================================
DerivedSensor = namedtuple("DerivedSensor", ["key", "requires"])


def _d(key, requires=None):
    return DerivedSensor(key, requires or ())


# Available on models with a decoded fault map.
DERIVED_FAULTS: list[DerivedSensor] = [
    _d("active_faults", ("faults",)),
    _d("active_alarms", ("faults",)),
    _d("battery_faults", ("faults",)),
    _d("comm_board_faults", ("faults",)),
]

# Available on every model.
DERIVED_COMMON: list[DerivedSensor] = [
    _d("operating_mode"),
    _d("control_requested_mode"),
    _d("control_effective_mode"),
    _d("control_last_result"),
    _d("control_last_command_at"),
]

# Only when the model has a documented country/battery-parameter map.
DERIVED_EXTRA: list[DerivedSensor] = [
    _d("grid_code"),
    _d("battery_type_text"),
]

# Only when clock monitoring is available and enabled.
DERIVED_CLOCK: list[DerivedSensor] = [
    _d("inverter_clock"),
    _d("clock_drift"),
]

# Device identification, populated best-effort from 0x2000-0x200F.
DERIVED_DEVICE: list[DerivedSensor] = [
    _d("rated_power"),
    _d("arm_firmware_version"),
]

# Most recent entry from the inverter's own event log (function code 0x50).
DERIVED_EVENT: list[DerivedSensor] = [
    _d("last_event"),
]

# ---- Binary sensors --------------------------------------------------------
# key -> (label, device_class, icon)
BINARY_SENSOR_META: dict[str, tuple] = {
    "inverter_problem": ("Problem", "problem", None),
    "eps_active": ("EPS Active", None, "mdi:home-lightning-bolt"),
    "battery_charge_ready": ("Battery Charge Ready", None, "mdi:battery-arrow-up"),
    "battery_discharge_ready": ("Battery Discharge Ready", None, "mdi:battery-arrow-down"),
    "battery_full": ("Battery Full (charge prohibited)", None, "mdi:battery-alert"),
    "battery_empty": ("Battery Empty (discharge prohibited)", None, "mdi:battery-alert-variant"),
    "clock_out_of_sync": ("Clock Out Of Sync", "problem", "mdi:clock-alert"),
}

BINARY_SENSORS_FAULTS = ("inverter_problem",)
BINARY_SENSORS_EPS = ("eps_active",)
BINARY_SENSORS_PASSIVE_FLAGS = (
    "battery_charge_ready",
    "battery_discharge_ready",
    "battery_full",
    "battery_empty",
)
BINARY_SENSORS_CLOCK = ("clock_out_of_sync",)

# ---- Sensor presentation metadata ------------------------------------------
# key -> (label, unit, device_class, state_class, precision, icon)
# device_class / state_class strings are mapped to HA enums in sensor.py.
#
# The entries down to "battery2_cycles" are the original, shipped set. Their
# label, unit, device_class and state_class are frozen: changing a label changes
# the generated entity_id, and changing a unit or state_class corrupts recorder
# long-term statistics.
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
    # ---------------- new entities from here on ----------------
    # Fault / alarm reporting
    "active_faults":     ("Active Faults", None, None, None, None, "mdi:alert-circle"),
    "active_alarms":     ("Active Alarms", None, None, None, None, "mdi:alert"),
    "battery_faults":    ("Battery Faults", None, None, None, None, "mdi:battery-alert"),
    "comm_board_faults": ("Communication Board Faults", None, None, None, None, "mdi:chip"),
    "fault_word_1":      ("Fault Word 1", None, None, None, None, "mdi:numeric"),
    "fault_word_2":      ("Fault Word 2", None, None, None, None, "mdi:numeric"),
    "fault_word_3":      ("Fault Word 3", None, None, None, None, "mdi:numeric"),
    "fault_word_4":      ("Fault Word 4", None, None, None, None, "mdi:numeric"),
    "fault_word_5":      ("Fault Word 5", None, None, None, None, "mdi:numeric"),
    "alarm_word":        ("Alarm Word", None, None, None, None, "mdi:numeric"),
    "battery_fault_word_1": ("Battery Fault Word 1", None, None, None, None, "mdi:numeric"),
    "comm_board_word":   ("Communication Board Word", None, None, None, None, "mdi:numeric"),
    "last_event":        ("Last Event", None, None, None, None, "mdi:history"),
    # EPS / backup output
    "eps_voltage":       ("EPS Output Voltage", "V", "voltage", "measurement", 1, None),
    "eps_power":         ("EPS Output Power", "W", "power", "measurement", 0, None),
    # Full PV string telemetry (replaces the ambiguous solar_pv_amps)
    "pv1_voltage":       ("PV1 Voltage", "V", "voltage", "measurement", 1, None),
    "pv1_current":       ("PV1 Current", "A", "current", "measurement", 2, None),
    "pv2_voltage":       ("PV2 Voltage", "V", "voltage", "measurement", 1, None),
    "pv2_current":       ("PV2 Current", "A", "current", "measurement", 2, None),
    # Operating mode / control status
    "operating_mode":    ("Operating Mode", None, None, None, None, "mdi:cog-outline"),
    "control_requested_mode":  ("Control Requested Mode", None, None, None, None, "mdi:gesture-tap-button"),
    "control_effective_mode":  ("Control Effective Mode", None, None, None, None, "mdi:cog-play"),
    "control_last_result":     ("Control Last Result", None, None, None, None, "mdi:check-decagram"),
    "control_last_command_at": ("Control Last Command", None, "timestamp", None, None, "mdi:clock-outline"),
    # Clock
    "inverter_clock":    ("Inverter Clock", None, "timestamp", None, None, "mdi:clock"),
    "clock_drift":       ("Clock Drift", "s", "duration", "measurement", 0, "mdi:clock-alert-outline"),
    # Device identification
    "rated_power":       ("Rated Power", "W", "power", None, 0, "mdi:transmission-tower"),
    "arm_firmware_version": ("ARM Firmware Version", None, None, None, None, "mdi:chip"),
    # Additional diagnostics
    "countdown_time":    ("Countdown Time", "s", "duration", "measurement", 0, "mdi:timer-outline"),
    "bus_voltage":       ("Inverter Bus Voltage", "V", "voltage", "measurement", 1, None),
    "llc_bus_voltage":   ("LLC Bus Voltage", "V", "voltage", "measurement", 1, None),
    "buck_current":      ("Buck Current", "A", "current", "measurement", 2, None),
    "country_code":      ("Country Code", None, None, None, None, "mdi:earth"),
    "grid_code":         ("Grid Code", None, None, None, None, "mdi:earth"),
    "dci_current":       ("DCI Current", "mA", "current", "measurement", 0, None),
    "dci_voltage":       ("DCI Voltage", "V", "voltage", "measurement", 1, None),
    "today_generation_time":  ("Today Generation Time", "min", "duration", "total_increasing", 0, "mdi:timer-sand"),
    "total_generation_time":  ("Total Generation Time", "h", "duration", "total_increasing", 0, "mdi:timer-sand"),
    "pv1_insulation_resistance": ("PV1 Insulation Resistance", None, None, "measurement", 0, "mdi:omega"),
    "pv2_insulation_resistance": ("PV2 Insulation Resistance", None, None, "measurement", 0, "mdi:omega"),
    "pv_negative_insulation_resistance": ("PV- Insulation Resistance", None, None, "measurement", 0, "mdi:omega"),
    # Battery configuration parameters (read-only)
    "battery_type":       ("Battery Type Code", None, None, None, None, "mdi:battery-unknown"),
    "battery_type_text":  ("Battery Type", None, None, None, None, "mdi:battery-unknown"),
    "battery_capacity":   ("Battery Capacity", "Ah", None, None, 0, "mdi:battery-high"),
    "battery_max_charge_voltage":    ("Battery Max Charge Voltage", "V", "voltage", None, 1, None),
    "battery_max_charge_current":    ("Battery Max Charge Current", "A", "current", None, 2, None),
    "battery_overvoltage_protection": ("Battery Overvoltage Protection", "V", "voltage", None, 1, None),
    "battery_min_discharge_voltage": ("Battery Min Discharge Voltage", "V", "voltage", None, 1, None),
    "battery_max_discharge_current": ("Battery Max Discharge Current", "A", "current", None, 2, None),
    "battery_undervoltage_protection": ("Battery Undervoltage Protection", "V", "voltage", None, 1, None),
    "battery_dod":         ("Battery DOD", "%", None, None, 0, "mdi:battery-arrow-down"),
    "battery_shallow_dod": ("Battery Shallow DOD (on-grid)", "%", None, None, 0, "mdi:battery-arrow-down-outline"),
    "battery_empty_voltage": ("Battery Empty Voltage", "V", "voltage", None, 2, None),
    "battery_full_voltage":  ("Battery Full Voltage", "V", "voltage", None, 2, None),
}

# ---- Entity category / default-enabled policy -------------------------------
# Diagnostic entities are registered disabled by default so that adding them
# does not clutter existing installations. Note that
# entity_registry_enabled_default only applies the first time an entity is
# registered, so listing an already-shipped entity here never disables it on an
# existing install.
DIAGNOSTIC_SENSORS: frozenset[str] = frozenset({
    "fault_word_1", "fault_word_2", "fault_word_3", "fault_word_4", "fault_word_5",
    "alarm_word", "battery_fault_word_1", "comm_board_word", "comm_board_faults",
    "control_requested_mode", "control_effective_mode", "control_last_result",
    "control_last_command_at",
    "inverter_clock", "clock_drift",
    "rated_power", "arm_firmware_version",
    "countdown_time", "bus_voltage", "llc_bus_voltage", "buck_current",
    "country_code", "grid_code", "dci_current", "dci_voltage",
    "today_generation_time", "total_generation_time",
    "pv1_insulation_resistance", "pv2_insulation_resistance",
    "pv_negative_insulation_resistance",
    "battery_type", "battery_type_text", "battery_capacity",
    "battery_max_charge_voltage", "battery_max_charge_current",
    "battery_overvoltage_protection", "battery_min_discharge_voltage",
    "battery_max_discharge_current", "battery_undervoltage_protection",
    "battery_dod", "battery_shallow_dod",
    "battery_empty_voltage", "battery_full_voltage",
    "last_event",
})

# Entities registered disabled by default. This is a superset of the diagnostic
# set: a deprecated entity is hidden from new installs without being given an
# entity_category it did not previously have, which would move it out of the
# device's main entity list on installs that already have it.
DISABLED_BY_DEFAULT_SENSORS: frozenset[str] = DIAGNOSTIC_SENSORS | frozenset({
    # Deprecated: register 0x0236 is documented as reserved. Kept in place for
    # existing installs; new installs get it disabled and should use
    # pv1_current / pv2_current instead. See README.
    "solar_pv_amps",
})

DIAGNOSTIC_BINARY_SENSORS: frozenset[str] = frozenset({
    "battery_charge_ready", "battery_discharge_ready",
    "battery_full", "battery_empty",
    "clock_out_of_sync",
})

# Entities that are deprecated but deliberately retained so that existing
# dashboards, automations and statistics keep working.
DEPRECATED_SENSORS: dict[str, str] = {
    "solar_pv_amps": (
        "Register 0x0236 is documented as reserved; use pv1_current and "
        "pv2_current instead. Retained for backwards compatibility."
    ),
}


# ===========================================================================
# Fault / alarm bit tables (protocol document 2.2.2, pages 8-12).
#   source_key : the sensor key holding the raw 16-bit word
#   byte       : 0 = low byte, 1 = high byte
#   bit        : bit within that byte
#   fault_id   : the ID Sofar prints on the inverter screen and in its manual
#   code       : the short symbol from the protocol document
# Bits documented as "reserved" are omitted; an undecoded bit that is set is
# reported generically as "Unknown (byteN bitM)" so nothing is silently dropped.
# ===========================================================================
FaultBit = namedtuple(
    "FaultBit", ["source_key", "byte", "bit", "fault_id", "code", "description"]
)


def _f(source_key, byte, bit, fault_id, code, description):
    return FaultBit(source_key, byte, bit, fault_id, code, description)


FAULT_BITS: tuple[FaultBit, ...] = (
    # 0x0201 low byte (byte0)
    _f("fault_word_1", 0, 0, 1, "GridOVP", "Grid over voltage"),
    _f("fault_word_1", 0, 1, 2, "GridUVP", "Grid under voltage"),
    _f("fault_word_1", 0, 2, 3, "GridOFP", "Grid over frequency"),
    _f("fault_word_1", 0, 3, 4, "GridUFP", "Grid under frequency"),
    _f("fault_word_1", 0, 4, 5, "BatOVP", "Battery over voltage"),
    _f("fault_word_1", 0, 6, 7, "GridLVRT", "LVRT fault"),
    _f("fault_word_1", 0, 7, 8, "PV_OVP", "PV over voltage"),
    # 0x0201 high byte (byte1)
    _f("fault_word_1", 1, 0, 9, "HW_LLCBus_OVP", "LLC bus over voltage (hardware)"),
    _f("fault_word_1", 1, 1, 10, "HW_Boost_OVP", "Bus over voltage (hardware)"),
    _f("fault_word_1", 1, 2, 11, "HwBuckBoostOCP", "Buck/boost over current (hardware)"),
    _f("fault_word_1", 1, 3, 12, "HwBatOCP", "Battery over current (hardware)"),
    _f("fault_word_1", 1, 4, 13, "GFCI_Fault", "Residual current fault"),
    _f("fault_word_1", 1, 5, 14, "HwPVOCP", "PV over current (hardware)"),
    _f("fault_word_1", 1, 6, 15, "HwAcOCP", "AC output over current (hardware)"),
    _f("fault_word_1", 1, 7, 16, "IpvUnbalance", "PV current unbalance"),
    # 0x0202 low byte (byte2)
    _f("fault_word_2", 0, 0, 17, "HwADFaultIGrid", "Grid current sampling error"),
    _f("fault_word_2", 0, 1, 18, "HwADFaultDCI", "DCI current sampling error"),
    _f("fault_word_2", 0, 2, 19, "HwADFaultVGrid", "Grid voltage sampling error"),
    _f("fault_word_2", 0, 3, 20, "GFCIDeviceFault", "Residual current sampling error"),
    _f("fault_word_2", 0, 4, 21, "MChip_Fault", "Main DSP fault"),
    _f("fault_word_2", 0, 5, 22, "HwAuxPowerFault", "Auxiliary power fault"),
    # 0x0202 high byte (byte3)
    _f("fault_word_2", 1, 0, 25, "LLCBusOVP", "LLC bus over voltage"),
    _f("fault_word_2", 1, 1, 26, "SwBusOVP", "Boost bus over voltage (software)"),
    _f("fault_word_2", 1, 2, 27, "BatOCP", "Battery over current"),
    _f("fault_word_2", 1, 3, 28, "DciOCP", "DCI over current"),
    _f("fault_word_2", 1, 4, 29, "SwOCPInstant", "Output instantaneous over current"),
    _f("fault_word_2", 1, 5, 30, "BuckOCP", "Buck over current"),
    _f("fault_word_2", 1, 6, 31, "AcRmsOCP", "Output RMS over current"),
    _f("fault_word_2", 1, 7, 32, "SwPvOCPInstant", "Input over current (software)"),
    # 0x0203 low byte (byte4)
    _f("fault_word_3", 0, 0, 33, "PvConfigSetWrong", "Input mode error"),
    # 0x0203 high byte (byte5)
    _f("fault_word_3", 1, 7, 48, "ConsistentFault_GFCI", "Residual current consistency error"),
    # 0x0204 low byte (byte6)
    _f("fault_word_4", 0, 0, 49, "ConsistentFault_VGrid", "Grid voltage consistency error"),
    _f("fault_word_4", 0, 1, 50, "ConsistentFault_FGrid", "Grid frequency consistency error"),
    _f("fault_word_4", 0, 2, 51, "ConsistentFault_DCI", "DCI current consistency error"),
    _f("fault_word_4", 0, 3, 52, "BatCommunicatonFlag", "Battery communication fault"),
    _f("fault_word_4", 0, 4, 53, "SpiCommLose", "SPI communication error"),
    _f("fault_word_4", 0, 5, 54, "SciCommLose", "SCI communication error"),
    _f("fault_word_4", 0, 6, 55, "RecoverRelayFail", "Relay detection error"),
    _f("fault_word_4", 0, 7, 56, "PvIsoFault", "Isolation resistance low"),
    # 0x0204 high byte (byte7)
    _f("fault_word_4", 1, 0, 57, "OverTempFault_BAT", "Battery temperature protection"),
    _f("fault_word_4", 1, 1, 58, "OverTempFault_HeatSink", "Heatsink over temperature protection"),
    _f("fault_word_4", 1, 2, 59, "OverTempFault_Env", "Ambient temperature protection"),
    _f("fault_word_4", 1, 3, 60, "PEConnectFault", "PE connection error"),
    # 0x0205 low byte (byte8) — permanent faults
    _f("fault_word_5", 0, 0, 65, "unrecoverHwAcOCP", "Output over current permanent fault"),
    _f("fault_word_5", 0, 1, 66, "unrecoverBusOVP", "Bus over voltage permanent fault"),
    _f("fault_word_5", 0, 2, 67, "EPSunrecoverBatOCP", "EPS battery over current permanent fault"),
    _f("fault_word_5", 0, 3, 68, "unrecoverIpvUnbalance", "PV current unbalance permanent fault"),
    _f("fault_word_5", 0, 5, 70, "unrecoverOCPInstant", "Output instantaneous over current permanent fault"),
    # 0x0205 high byte (byte9) — permanent faults
    _f("fault_word_5", 1, 0, 73, "unrecoverPvConfigSetWrong", "Input mode setting permanent fault"),
    _f("fault_word_5", 1, 1, 74, "unrecoverIPVInstant", "Input over current permanent fault"),
    _f("fault_word_5", 1, 2, 75, "unrecoverEEPROM_W", "EEPROM write permanent fault"),
    _f("fault_word_5", 1, 3, 76, "unrecoverEEPROM_R", "EEPROM read permanent fault"),
    _f("fault_word_5", 1, 4, 77, "unrecoverRelayFail", "Relay permanent fault"),
)

# Inverter alarm information (0x022B). These are derates/warnings, not faults.
ALARM_BITS: tuple[FaultBit, ...] = (
    _f("alarm_word", 0, 0, 81, "OverTempAlarmLoadShedding", "Over temperature derating"),
    _f("alarm_word", 0, 1, 82, "OverFreqAlarmLoadShedding", "Over frequency derating"),
    _f("alarm_word", 0, 2, 83, "bitlongdistLoadShedding", "Remote derating"),
    _f("alarm_word", 0, 3, 84, "bitlongdistOFF", "Remote off"),
    _f("alarm_word", 0, 7, 85, "batLowVoltageAlarm", "Battery low voltage alarm"),
    _f("alarm_word", 1, 0, 86, "BatVoltageLowShut", "Battery low voltage shutdown"),
)

# Lithium battery / BMS fault information (0x023D low byte).
BATTERY_FAULT_BITS: tuple[FaultBit, ...] = (
    _f("battery_fault_word_1", 0, 0, 100, "BatOCD", "Discharge over current protection"),
    _f("battery_fault_word_1", 0, 1, 101, "BatSCD", "Discharge circuit protection"),
    _f("battery_fault_word_1", 0, 2, 102, "BatOV", "Battery over voltage protection"),
    _f("battery_fault_word_1", 0, 3, 103, "BatUV", "Battery under voltage protection"),
    _f("battery_fault_word_1", 0, 4, 104, "BatOTD", "Discharge over temperature protection"),
    _f("battery_fault_word_1", 0, 5, 105, "BatOTC", "Charge over temperature protection"),
    _f("battery_fault_word_1", 0, 6, 106, "BatUTD", "Discharge low temperature protection"),
    _f("battery_fault_word_1", 0, 7, 107, "BatUTC", "Charge low temperature protection"),
)

# Communication board internal information (0x0242).
COMM_BOARD_BITS: tuple[FaultBit, ...] = (
    _f("comm_board_word", 0, 3, 94, "SoftVersionMismatch", "Software version consistency error"),
    _f("comm_board_word", 0, 4, 95, "CommEEPROMFault", "Communication board EEPROM error"),
    _f("comm_board_word", 0, 5, 96, "RTCFault", "RTC clock fault"),
    _f("comm_board_word", 0, 7, 98, "SDFault", "SD card fault"),
    _f("comm_board_word", 1, 1, None, "WifiFault", "WiFi fault"),
)

# Fault groups that raise the "Problem" binary sensor. Alarms are derates and
# are reported separately so a routine temperature derate is not shown as a fault.
PROBLEM_FAULT_GROUPS = ("faults", "battery_faults")

# ---- Timing / Time-of-Use limits (protocol document 2.24.2) ----------------
SCHEDULE_POWER_MIN = 0
SCHEDULE_POWER_MAX = 3000
TOU_RULE_MIN = 0
TOU_RULE_MAX = 3
TOU_SOC_MIN = 30
TOU_SOC_MAX = 100

# TOU weekday bitmask (0x120E): b0 = Monday .. b6 = Sunday.
TOU_WEEKDAYS = (
    ("monday", "Monday", 0),
    ("tuesday", "Tuesday", 1),
    ("wednesday", "Wednesday", 2),
    ("thursday", "Thursday", 3),
    ("friday", "Friday", 4),
    ("saturday", "Saturday", 5),
    ("sunday", "Sunday", 6),
)

# ---- Schedule control entity metadata --------------------------------------
# Time entities: key -> (label, register, icon)
SCHEDULE_TIME_ENTITIES: tuple[tuple[str, str, int, str], ...] = (
    ("sched_charge_start", "Timing Charge Start", 0x1201, "mdi:clock-start"),
    ("sched_charge_end", "Timing Charge End", 0x1202, "mdi:clock-end"),
    ("sched_discharge_start", "Timing Discharge Start", 0x1203, "mdi:clock-start"),
    ("sched_discharge_end", "Timing Discharge End", 0x1204, "mdi:clock-end"),
    ("tou_charge_start", "TOU Forced Charge Start", 0x1208, "mdi:clock-start"),
    ("tou_charge_end", "TOU Forced Charge End", 0x1209, "mdi:clock-end"),
)

# Number entities: key -> (label, unit, min, max, step, icon)
SCHEDULE_NUMBER_ENTITIES: tuple[tuple[str, str, str | None, int, int, int, str], ...] = (
    ("sched_charge_power", "Timing Charge Power", "W",
     SCHEDULE_POWER_MIN, SCHEDULE_POWER_MAX, 100, "mdi:battery-arrow-up"),
    ("sched_discharge_power", "Timing Discharge Power", "W",
     SCHEDULE_POWER_MIN, SCHEDULE_POWER_MAX, 100, "mdi:battery-arrow-down"),
    ("tou_rule_number", "TOU Rule Number", None,
     TOU_RULE_MIN, TOU_RULE_MAX, 1, "mdi:format-list-numbered"),
    ("tou_soc", "TOU Forced Charge Target SOC", "%",
     TOU_SOC_MIN, TOU_SOC_MAX, 1, "mdi:battery-charging-80"),
    ("tou_power", "TOU Forced Charge Power", "W",
     SCHEDULE_POWER_MIN, SCHEDULE_POWER_MAX, 100, "mdi:battery-arrow-up"),
)
