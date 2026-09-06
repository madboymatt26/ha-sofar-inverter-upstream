# Sofar Inverter Modbus TCP

Home Assistant integration for Sofar hybrid and battery-storage inverters over
Modbus TCP (direct, or via an RS485→TCP gateway).

Register maps and scaling are ported from the
[Sofar2mqtt](https://github.com/cmcgerty/Sofar2MQTT) ESP firmware. Fault
decoding, schedules, clock handling and command verification follow the official
Sofar *ModBus-RTU Protocol* document for HYD / ME3000SP (2020-11-23).

## Supported models

| Selection | Inverter family | Firmware equivalent | Control protocol |
|-----------|-----------------|---------------------|------------------|
| `Sofar ME3000SP` | ME3000SP | `ME3000` | Passive mode, function code `0x42` |
| `Sofar HYD-ES / HYD-EP (single phase hybrid)` | HYD-xx00-ES/EP | `HYBRID` | Passive mode, function code `0x42` |
| `Sofar HYD-EP / HYD-KTL (three phase hybrid)` | HYD-xx00-EP/KTL | `HYDV2` | Passive control register `0x1187` |

The protocol document covers the ME3000SP and HYD-ES `0x02xx` / `0x12xx`
register maps. Features that depend on those maps — fault decoding, EPS
telemetry, PV string detail, Timing/Time-of-Use schedules and clock handling —
are therefore available on those two families only. The HYD-EP/KTL equivalents
live in an undocumented `0x04xx` / `0x11xx` range and are deliberately not
guessed at.

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
| Enable battery control | Adds the battery control entities (see warning below) |
| Maximum charge/discharge power | Upper limit applied to charge/discharge (W) |
| Enable Timing / Time-of-Use entities | Adds the schedule entities (ME3000SP / HYD-ES) |
| Monitor the inverter clock | Reads the inverter RTC hourly and reports drift |

Everything except the connection details and the inverter model can be changed
afterwards via **Configure** on the integration entry; the entry reloads itself
when you save. Changing the connection details or model would change the entry's
identity, so those still require removing and re-adding the integration.

## Sensors

All status fields from Sofar2mqtt are exposed, including running state, grid
voltage/current/frequency/power, battery power/voltage/current/SOC/SOH/
temperature/cycles, PV power (and per-string values where available),
inverter/heatsink temperatures, consumption, and daily/total energy counters. On
HYD-EP/KTL a second battery's sensors are added automatically when one is
detected.

Scaling, signedness and the running-state text map are ported directly from the
firmware so values match Sofar2mqtt.

### Faults, alarms and EPS (ME3000SP / HYD-ES)

- **Problem** (binary sensor) — on when a fault or BMS fault is active, or the
  inverter is in a fault run state. The full decoded list is in its attributes.
- **Active Faults**, **Active Alarms**, **Battery Faults** — readable text with
  the Sofar fault IDs (`ID01 Grid over voltage`), matching what the inverter
  shows on its own screen. Alarms are derates and warnings, and deliberately do
  not raise **Problem**.
- **Last Event** — the newest entry from the inverter's own event log, which
  survives Home Assistant downtime.
- **EPS Output Voltage / Power** and **EPS Active** — backup-output monitoring.
- Full PV string telemetry: **PV1/PV2 Voltage** and **PV1/PV2 Current**.

Bits that the protocol document marks reserved are reported as
`Undocumented bit set (...)` rather than being dropped, so a fault on newer
firmware is still visible.

### Diagnostics

Bus/LLC voltages, buck current, DCI, insulation resistances, generation time,
grid code, battery configuration parameters, the raw fault words, control status
and clock drift are all registered as **diagnostic entities disabled by
default**. Enable the ones you need from the device page.

## Control (optional)

> ⚠️ **The inverter must be in Passive Mode for charge/discharge/standby to take
> effect.** Forcing these modes overrides the inverter's own energy management.
> Use at your own risk.

With *Enable battery control* ticked you get four entities:

- **Battery Mode** (select): `No Override`, `Auto (Self Use)`, `Battery Save`,
  `Charge`, `Discharge`, `Standby`.
- **Battery Power Setpoint** (number): watts used for Charge / Discharge.
- **Set Auto Mode** and **Set Standby** (buttons): quick actions.

Plus **Working Mode** (select) to move the inverter between `Auto`,
`Time of Use`, `Timing` and `Passive`, verified by reading the register back.

`Battery Save` is the firmware's hybrid mode — it charges from excess solar but
never discharges, switching between Auto and Standby based on grid power. The
selected mode is re-applied on every poll so passive-mode setpoints stay latched.

Commands are now **verified**: the `0x42` status word is decoded, so a command
rejected because the inverter is not in Passive Mode, is busy, or has a full or
empty battery is reported as a failure instead of a success. The reason appears
in **Control Last Result** and in the log.

### Behaviour on restart

Home Assistant starts in `No Override`. The inverter, however, keeps whatever
passive setpoint it was last given, so a forced charge could otherwise stay
latched across a restart. On the first poll after startup, if the inverter is in
Passive Mode and no override is selected, a single `Auto` command is sent to
release it. A previously forced charge/discharge is never restored automatically.

Standby is avoided as a fail-safe on purpose: leaving standby is rate-limited by
the grid-code power ramp, so dropping into it costs minutes of reduced output.

### Power limits

Charge/discharge commands are clamped to the configured maximum. If the inverter's
rated power can be decoded from its barcode (`0x2000`-`0x2007`) and is *lower*
than the configured maximum, the lower figure is used and a warning is logged. A
detected rating never raises your configured limit, and an undetected rating never
lowers it — so a correctly configured 6 kW hybrid is not restricted to the 3 kW
figure the protocol document quotes for the smallest model in the family.

## Timing and Time-of-Use schedules (ME3000SP / HYD-ES)

Enable *Timing / Time-of-Use entities* to expose the inverter's own scheduler:

- **Timing**: charge and discharge start/end times plus charge and discharge
  power (`0x1201`-`0x1206`).
- **Time of Use**: rule number, forced-charge window, target SOC, charge power,
  weekday switches and a rule enable flag (`0x1207`-`0x120F`).

Each entity shows the inverter's actual register content. Changing one rewrites
its whole register block in a single transaction and then reads the block back to
confirm it took; a mismatch is logged and the entity reverts. The Time-of-Use rule
number is always written before the other TOU parameters, as the protocol
requires. A block is never written while any of its registers is still unknown,
so a value is never overwritten with a default.

> **Time-of-Use charge power of 0 W does not disable charging.** Per the
> protocol, `0x120B = 0` means charge the battery from whatever grid power is
> available.

### The inverter clock

Timing and Time-of-Use windows are evaluated against the **inverter's own
real-time clock**, not Home Assistant's. A drifting RTC silently shifts your
off-peak window with no other indication, and the protocol defines an RTC fault
(ID96). With clock monitoring enabled the RTC is read hourly and exposed as
**Inverter Clock**, **Clock Drift** and **Clock Out Of Sync** (diagnostics), with
a warning logged when drift exceeds two minutes.

**Sync Inverter Clock** (button) writes the current time. The protocol only
defines clock setting as a broadcast to address `0x88`, so this sets the time on
**every Sofar inverter on the same RS485 bus**, not just the configured one.

## Deprecated entities

| Entity | Reason | Replacement |
|--------|--------|-------------|
| `Solar PV Current` (`solar_pv_amps`) | Register `0x0236` is documented as **reserved**; the value is not trustworthy. | `PV1 Current` (`0x0251`) and `PV2 Current` (`0x0254`) |

The deprecated entity is **kept in place** and its unique_id, name, unit and
device class are unchanged, so existing dashboards, automations and long-term
statistics keep working. It is registered disabled-by-default, which only affects
newly created installations. It will not be removed without a major release and a
migration note.

## Implementation notes

- **Batched reads.** Contiguous and near-contiguous registers are fetched in one
  transaction. This cuts a ME3000SP/HYD-ES poll from 80-86 Modbus transactions to
  4, and a HYD-EP/KTL poll from 45 to 10 — which matters because the RS485 bus
  behind the gateway runs at 9600 baud. A block the inverter refuses falls back to
  per-register reads, so one bad address cannot blank its block-mates; after three
  consecutive failures that block stays in per-register mode. If function code
  `0x03` is refused for a range, `0x04` is tried.
- **One connection per gateway.** All coordinators sharing a `host:port` share a
  single pymodbus client and a single lock, so polls, commands and heartbeats from
  different slave IDs are serialised onto the one RS485 bus. The client and
  heartbeat are reference-counted and torn down when the last entry unloads.
- **Heartbeat.** The passive-mode heartbeat (FC `0x49`) payload is the four bytes
  `22 01 22 02`, which the protocol document's own example frame
  (`01 49 22 01 22 02 1E DD`) confirms via its CRC. One frame is sent per
  registered slave every 9 seconds, and a failed send is retried within seconds
  rather than waiting a full interval — losing the heartbeat for 60 seconds drops
  the inverter to standby.
- **Auto command.** Sent as `0x0103` with parameter `0x5555`, as the protocol
  document specifies.
- **Custom function codes.** The proprietary `0x42` (passive mode), `0x49`
  (heartbeat), `0x21` (production info) and `0x50` (event log) are implemented as
  custom pymodbus PDUs. Sofar also reuses `0x10` — normally Write Multiple
  Registers — to *read* the clock; that read is issued on a temporary dedicated
  connection so its decoder cannot shadow the standard write path used for
  schedules and HYD-EP/KTL passive control.
- **Firmware gating.** The battery charge/discharge energy counters
  (`0x0224`-`0x0229`) require ARM firmware V1.20 or later. On older firmware they
  report unavailable instead of a misleading zero. If the firmware version cannot
  be read, no gating is applied.
- **Battery configuration parameters** (`0x10B0`-`0x10BC`, including DOD and
  on-grid shallow DOD) are **read-only**. The document's read table (§2.3.2) and
  write table (§2.4.2) disagree by two registers from `0x10B4` onward, so writing
  them is unsafe until verified by read-back on real hardware.
- Requires `pymodbus >= 3.11.2` (bundled with recent Home Assistant releases).

## Not implemented

Deliberately left out pending verification on real hardware:

- **EPS enable** (FC `0x41`) — changes backup-power behaviour.
- **Active power derating, power factor and reactive power** (`0x1040`-`0x1074`)
  — grid-compliance settings.
- **Battery parameter writes** — see the read/write table discrepancy above.
- **`0x1215` grid-power target.** This would let the inverter hold grid power at
  a setpoint itself, which is a better `Battery Save` than switching between Auto
  and Standby from Home Assistant and would avoid the standby ramp-rate penalty.
  Worth adopting once tested.
- **Clear energy / clear event list / factory reset** (`0x30`-`0x34`) —
  destructive, with no undo.

## Development

`custom_components/sofar_inverter/const.py` deliberately contains no Home
Assistant imports, so the entity inventory can be verified without a Home
Assistant install:

```bash
# Confirm no existing entity was renamed, re-keyed or re-united
python3 scripts/entity_inventory.py --check scripts/entity_baseline.json
```

Every `key` in the sensor maps is part of an entity's unique_id and is therefore
a permanent API. Corrections are made by **adding** a new key alongside the old
one, never by re-keying: renaming orphans dashboards and automations, and changing
a unit, device class or state class corrupts recorder long-term statistics.

```bash
python3 -m pytest tests/          # requires homeassistant + pymodbus
```
