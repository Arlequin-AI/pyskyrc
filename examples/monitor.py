#!/usr/bin/env python3
"""
Continuous monitoring of all ports.

Usage:
    python examples/monitor.py            # USB
    python examples/monitor.py --ble      # BLE
"""

import argparse

from pyskyrc import PortTelemetry, SkyRCCharger


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--ble", action="store_true",
                   help="use BLE transport instead of USB HID")
    p.add_argument("--address", default="",
                   help="BLE MAC address (empty = auto-discover)")
    p.add_argument("--interval", type=float, default=0.25,
                   help="poll interval in seconds")
    args = p.parse_args()

    kwargs = {"transport": "ble"} if args.ble else {"transport": "usb"}
    if args.ble and args.address:
        kwargs["ble_address"] = args.address

    def on_update(info: PortTelemetry) -> None:
        if info.has_battery:
            cells = " ".join(f"{v:.3f}" for v in info.cells_v)
            print(
                f"  {info.port.name}: {info.state.name.lower():8s} "
                f"{info.total_v:6.3f}V  Δ{info.delta_mv:4d}mV  "
                f"T={info.temperature_c:>2}°C  [{cells}]"
            )
        else:
            print(f"  {info.port.name}: {info.state.name.lower():8s} --")

    with SkyRCCharger(**kwargs) as charger:
        print("monitor — Ctrl+C to stop")
        try:
            charger.monitor(on_update, interval=args.interval)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
