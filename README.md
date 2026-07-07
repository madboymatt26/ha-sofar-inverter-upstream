# Sofar Inverter Modbus TCP

[![Validate](https://github.com/LucMathlin/ha-sofar-inverter/actions/workflows/validate.yml/badge.svg)](https://github.com/LucMathlin/ha-sofar-inverter/actions/workflows/validate.yml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

[![Add to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=LucMathlin&repository=ha-sofar-inverter&category=integration)

A Home Assistant custom integration for Sofar Solar inverters via Modbus TCP.

## Supported Devices

- Sofar HYD series (hybrid inverters)
- Sofar KTL series (string inverters)
- Sofar ME series (storage inverters)
- Other Sofar inverters with Modbus TCP support

## Features

- Real-time solar production monitoring (PV power, voltage, current)
- Battery status (SoC, charge/discharge power, voltage)
- Grid import/export power monitoring
- Load consumption tracking
- Number entities for battery charge/discharge limits
- Select entities for inverter operating mode
- Button entities for inverter commands
- Configurable via the Home Assistant UI (config flow)

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots menu → **Custom repositories**
3. Add `https://github.com/LucMathlin/ha-sofar-inverter` with category **Integration**
4. Search for "Sofar Inverter" and install
5. Restart Home Assistant

### Manual

1. Copy `custom_components/sofar_inverter/` to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for "Sofar Inverter"
3. Enter the Modbus TCP host, port, and slave ID of your inverter
4. Configure polling interval as needed

## Requirements

- Modbus TCP connectivity to the inverter (via built-in WiFi module or RS485-to-TCP gateway)
- `pymodbus>=3.11.2` (installed automatically)
