#!/usr/bin/env python3
"""
Scan for SkyRC chargers over BLE.

Usage:
    python examples/ble_scan.py
"""

from pyskyrc.discovery import scan_chargers_sync


def main() -> None:
    print("scanning for BLE chargers ...")
    candidates = scan_chargers_sync(timeout=15.0)

    if not candidates:
        print("no chargers found")
        return

    print(f"\nfound {len(candidates)} charger(s):\n")
    for i, c in enumerate(candidates, 1):
        print(f"  {i}. {c.name}")
        print(f"     MAC:  {c.address}")
        print(f"     RSSI: {c.rssi} dBm")
        print()


if __name__ == "__main__":
    main()
