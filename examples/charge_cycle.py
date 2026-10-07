#!/usr/bin/env python3
"""
Full charge cycle on port B: START -> monitor 30s -> STOP.

WARNING: sends real current. Only run with a battery that matches
the configured chemistry and cell count.

Usage:
    python examples/charge_cycle.py            # USB
    python examples/charge_cycle.py --ble      # BLE
"""

import argparse
import time

from pyskyrc import (
    ChargeParameters,
    Chemistry,
    LiMode,
    Port,
    SkyRCCharger,
)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--ble", action="store_true", help="use BLE transport instead of USB HID"
    )
    p.add_argument(
        "--address", default="", help="BLE MAC address (empty = auto-discover)"
    )
    p.add_argument(
        "--port", default="B", choices=list("ABCD"), help="target port (default: B)"
    )
    p.add_argument("--cells", type=int, default=6, help="cell count (default: 6)")
    p.add_argument(
        "--current", type=float, default=1.0, help="charge current in A (default: 1.0)"
    )
    p.add_argument(
        "--seconds",
        type=float,
        default=30.0,
        help="monitor duration before STOP (default: 30)",
    )
    args = p.parse_args()

    kwargs = {"transport": "ble"} if args.ble else {"transport": "usb"}
    if args.ble and args.address:
        kwargs["ble_address"] = args.address

    params = ChargeParameters(
        chemistry=Chemistry.LiPo,
        cells=args.cells,
        mode=LiMode.BALANCE_CHARGE,
        charge_current_a=args.current,
        discharge_current_a=0.5,
        charge_cutoff_mv=4200,
        discharge_cutoff_mv=3000,
    )
    port = Port[args.port.upper()]

    with SkyRCCharger(**kwargs) as charger:
        info = charger.get_info()
        if info:
            print(f"device: {info.serial}  fw {info.version}")

        print(f"START {port.name}: LiPo {args.cells}S BAL.CHG {args.current}A")
        if not charger.start_charge(port, params):
            print("FAIL: no ACK")
            return

        print(f"monitoring {args.seconds:.0f}s ...")
        t_end = time.monotonic() + args.seconds
        while time.monotonic() < t_end:
            data = charger.read_telemetry(timeout=0.5)
            target = data.get(port)
            if target and target.has_battery:
                cells = " ".join(f"{v:.3f}" for v in target.cells_v)
                print(
                    f"  {target.state.name.lower():8s} "
                    f"{target.total_v:6.3f}V  Δ{target.delta_mv:4d}mV  "
                    f"T={target.temperature_c:>2}°C  [{cells}]"
                )

        print(f"STOP {port.name}")
        if not charger.stop_charge(port):
            print("FAIL: no ACK")


if __name__ == "__main__":
    main()
