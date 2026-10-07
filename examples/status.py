#!/usr/bin/env python3
"""
Read status of all 4 ports.

Usage:
    python examples/status.py            # USB (default: /dev/hidraw4)
    python examples/status.py --ble      # BLE
"""

import argparse

from pyskyrc import Port, SkyRCCharger


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--ble", action="store_true", help="use BLE transport instead of USB HID"
    )
    p.add_argument(
        "--address", default="", help="BLE MAC address (empty = auto-discover)"
    )
    args = p.parse_args()

    kwargs = {"transport": "ble"} if args.ble else {"transport": "usb"}
    if args.ble and args.address:
        kwargs["ble_address"] = args.address

    with SkyRCCharger(**kwargs) as charger:
        data = charger.read_telemetry(timeout=1.0)
        print()
        for port in Port:
            info = data.get(port)
            if info is None or not info.has_battery:
                print(f"  {port.name}: --")
                continue
            cells = " ".join(f"{v:.3f}" for v in info.cells_v)
            print(
                f"  {port.name}: {info.state.name.lower():8s} "
                f"{info.total_v:6.3f}V  Δ{info.delta_mv:4d}mV  "
                f"T={info.temperature_c:>2}°C  [{cells}]"
            )
        print()


if __name__ == "__main__":
    main()
