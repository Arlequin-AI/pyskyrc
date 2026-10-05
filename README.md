[![PyPI](https://img.shields.io/pypi/v/pyskyrc.svg)](https://pypi.org/project/pyskyrc/)
[![Python](https://img.shields.io/pypi/pyversions/pyskyrc.svg)](https://pypi.org/project/pyskyrc/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/Arlequin-AI/pyskyrc/blob/main/LICENSE)
[![Tests](https://github.com/Arlequin-AI/pyskyrc/actions/workflows/test.yml/badge.svg)](https://github.com/Arlequin-AI/pyskyrc/actions/workflows/test.yml)

# pyskyrc

Pure-Python control and telemetry for **SkyRC Q200neo** / **T1000**
chargers via **USB HID** and **Bluetooth LE**.

Reverse-engineered from the official Charge Master 1.55.E207
protocol. **No Charge Master or SkyRC app required.**

## Features

- **Two transports** — USB HID and BLE with the same Python API.
- **4 ports** — A / B / C / D, each with independent telemetry.
- **Live cells** — 6 × cell voltage, temperature, total V, delta.
- **Full control** — START / STOP charge with full parameter set.
- **All chemistries** — LiPo, LiIo, LiFe, LiHV, NiMH, NiCd, Pb.
- **Auto-discovery** (BLE) — finds the charger by service UUID.
- **MAC cache** — fast reconnect after first successful session.
- **Interactive shell** — one connection, many commands.
- **Pure Python** — only `bleak` needed for BLE; USB has no deps.

## Install

    pip install pyskyrc
    pip install pyskyrc[ble]
    pip install pyskyrc[ble,dev]

## CLI

### USB

    pyskyrc info
    pyskyrc status
    pyskyrc monitor
    pyskyrc start B --chem LiPo --cells 6 --current 2.0
    pyskyrc stop B

### BLE

    pyskyrc --transport ble scan
    pyskyrc --transport ble status
    pyskyrc --transport ble start B --chem LiPo --cells 6 --current 2.0
    pyskyrc --transport ble stop B

### Interactive shell

    pyskyrc --transport ble shell

Then inside the shell:

    pyskyrc> status
    pyskyrc> start B --chem LiPo --cells 6 --current 2.0
    pyskyrc> monitor
    pyskyrc> stop B
    pyskyrc> exit

## Python API

    from pyskyrc import (
        SkyRCCharger, ChargeParameters, Port, Chemistry, LiMode,
    )

    with SkyRCCharger(transport="usb") as charger:
        for port, info in charger.read_telemetry().items():
            if info.has_battery:
                print(port.name, info.total_v, info.temperature_c)

        params = ChargeParameters(
            chemistry=Chemistry.LiPo,
            cells=6,
            mode=LiMode.BALANCE_CHARGE,
            charge_current_a=2.0,
        )
        charger.start_charge(Port.B, params)
        charger.stop_charge(Port.B)

For BLE, replace `transport="usb"` with `transport="ble"`.

## Protocol

Full protocol documentation is in `docs/protocol.md`.

## Safety

This library controls a real charger with real current. You are
responsible for choosing a chemistry and cell count that match your
battery, choosing safe currents, and not leaving charging unattended.

## License

MIT License — Copyright (c) 2026 Andreev Ivan.

See [LICENSE](https://github.com/Arlequin-AI/pyskyrc/blob/main/LICENSE) for full text.

## Author

Andreev Ivan — 2026
