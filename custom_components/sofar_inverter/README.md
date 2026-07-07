# Sofar Inverter (Modbus TCP)

Home Assistant custom integration for Sofar solar / battery inverters over
**Modbus TCP**. It provides the same sensors and control as the
[Sofar2mqtt](https://github.com/cmcgerty/Sofar2MQTT) ESP firmware, but talks
directly to the inverter (or an RS485↔TCP gateway) instead of going through MQTT.

## Supported models

| Selection | Inverter family | Firmware equivalent | Control protocol |
|-----------|-----------------|---------------------|------------------|
| `Sofar ME3000SP` | ME3000SP | `ME3000` | Passive mode, function code `0x42` |
| `Sofar HYD-ES / HYD-EP (single phase hybrid)` | HYD-xx00-ES/EP | `HYBRID` | Passive mode, function code `0x42` |
| `Sofar HYD-EP / HYD-KTL (three phase hybrid)` | HYD-xx00-EP/KTL | `HYDV2` | Passive control register `0x1187` |

## Installation

1. Copy the `sofar_inverter` folder into your Home Assistant
   `config/custom_components/` directory.
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration** and search for
   **Sofar Inverter Modbus TCP**.

## Configuration

| Field | Description |
|-------|-------------|
| Name | Friendly name / entity prefix |
| IP Address | Inverter or RS485→TCP gateway IP |
| Modbus TCP Port | Usually `502` |
| Slave / Unit ID | Modbus address, usually `1` |
| Inverter Model | Pick the family that matches your inverter |
| Polling Interval | Seconds between reads (default 10) |
| Enable battery control | Adds the control entities (see warning below) |
| Maximum charge/discharge power | Upper limit applied to charge/discharge (W) |

## Sensors

All status fields from Sofar2mqtt are exposed as sensors, including running
state, grid voltage/current/frequency/power, battery power/voltage/current/
SOC/SOH/temperature/cycles, PV power (and per-string values where available),
inverter/heatsink temperatures, consumption, and daily/total energy counters
(generation, consumption, import, export, charged, discharged). On HYD-EP/KTL a
second battery's sensors are added automatically when one is detected.

Scaling, signedness and the running-state text map are ported directly from the
firmware so values match Sofar2mqtt.

## Control (optional)

> ⚠️ **The inverter must be in Passive Mode for charge/discharge/standby to take
> effect.** Forcing these modes overrides the inverter's own energy management.
> Use at your own risk.

When *Enable battery control* is ticked, three control entities are added:

- **Battery Mode** (select): `No Override`, `Auto (Self Use)`, `Battery Save`,
  `Charge`, `Discharge`, `Standby`.
- **Battery Power Setpoint** (number): watts used for Charge / Discharge.
- **Set Auto Mode** / **Set Standby** (buttons): quick actions.

`Battery Save` is the firmware's hybrid mode — it charges from excess solar but
never discharges (it switches between Auto and Standby based on grid power). The
selected mode is re-applied on every poll so passive-mode setpoints stay latched.

## Notes

- A fresh TCP connection is opened per poll/command to avoid transaction-ID
  collisions with any other Modbus client sharing the same gateway.
- The proprietary `0x42` passive-mode command (ME3000 / HYD-ES) is implemented as
  a custom `pymodbus` PDU, since it is not a standard Modbus function.
- Requires `pymodbus >= 3.11.2` (bundled with recent Home Assistant releases).
