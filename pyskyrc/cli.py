"""pyskyrc командная строка."""

from __future__ import annotations

import argparse
import logging
import sys

from . import __version__, protocol
from .charger import ChargeParameters, SkyRCCharger
from .enums import Chemistry, LiMode, NiMode, PbMode, Port
from .exceptions import SkyRCError


# ============================================================
#  helpers
# ============================================================
def _make_charger(args: argparse.Namespace) -> SkyRCCharger:
    if args.transport == "ble":
        return SkyRCCharger(
            transport="ble",
            ble_address=args.ble_address,
            ble_name=args.ble_name or "Charger",
        )
    return SkyRCCharger(
        transport="usb",
        path=args.hid,
    )


def _default_mode(chem: Chemistry) -> int:
    if chem in (Chemistry.LiPo, Chemistry.LiIo,
                Chemistry.LiFe, Chemistry.LiHV):
        return int(LiMode.BALANCE_CHARGE)
    if chem in (Chemistry.NiMH, Chemistry.NiCd):
        return int(NiMode.CHARGE)
    return int(PbMode.NORMAL)


def _print_status_row(port: Port, info) -> None:
    if info is None or not info.has_battery:
        print(f"  {port.name}: --")
        return
    cells = " ".join(f"{v:.3f}" for v in info.cells_v)
    print(
        f"  {port.name}: {info.state.name.lower():8s} "
        f"{info.total_v:6.3f}V  Δ{info.delta_mv:4d}mV  "
        f"T={info.temperature_c:>2}°C  [{cells}]"
    )


# ============================================================
#  commands
# ============================================================
def cmd_scan(args: argparse.Namespace) -> int:
    from .discovery import scan_chargers_sync

    candidates = scan_chargers_sync(timeout=args.scan_timeout)
    if not candidates:
        print("no SkyRC BLE chargers found")
        return 1

    print(f"found {len(candidates)} charger(s):")
    print()
    for i, c in enumerate(candidates, 1):
        print(f"  {i}. {c.name}")
        print(f"     MAC:  {c.address}")
        print(f"     RSSI: {c.rssi} dBm")
        print()
    return 0

def cmd_info(args: argparse.Namespace) -> int:
    try:
        with _make_charger(args) as charger:
            info = charger.get_info()
            if info is None:
                print("no reply from device")
                return 1
            print(f"Serial:  {info.serial}")
            print(f"Version: {info.version}")
    except SkyRCError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    try:
        with _make_charger(args) as charger:
            data = charger.read_telemetry(timeout=1.0)
            print()
            for port in Port:
                _print_status_row(port, data.get(port))
            print()
    except SkyRCError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


def cmd_monitor(args: argparse.Namespace) -> int:
    try:
        with _make_charger(args) as charger:
            print("monitor — Ctrl+C to stop")
            try:
                charger.monitor(
                    lambda info: _print_status_row(info.port, info),
                    interval=args.interval,
                )
            except KeyboardInterrupt:
                pass
    except SkyRCError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    chem = Chemistry[args.chem]
    mode = args.mode if args.mode is not None else _default_mode(chem)

    params = ChargeParameters(
        chemistry=chem,
        cells=args.cells,
        mode=mode,
        charge_current_a=args.current,
        discharge_current_a=args.discharge,
        charge_cutoff_mv=args.chg_cut,
        discharge_cutoff_mv=args.dch_cut,
        trickle_ma=args.trickle,
        repeat_count=args.repeat,
        cycle_count=args.cycles,
    )

    try:
        with _make_charger(args) as charger:
            ok = charger.start_charge(Port[args.port.upper()], params)
            print("OK" if ok else "FAIL: no ACK")
            return 0 if ok else 1
    except SkyRCError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def cmd_stop(args: argparse.Namespace) -> int:
    try:
        with _make_charger(args) as charger:
            ok = charger.stop_charge(Port[args.port.upper()])
            print("OK" if ok else "FAIL: no ACK")
            return 0 if ok else 1
    except SkyRCError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
# ============================================================
#  Interactive shell
# ============================================================

def cmd_shell(args: argparse.Namespace) -> int:
    """
    Интерактивная сессия: одно соединение, много команд.

    Команды:
        status                — снимок всех портов
        info                  — serial + версия
        start <port> [opts]   — запустить заряд
        stop <port>           — остановить заряд
        monitor               — непрерывный поток (Ctrl+C для выхода)
        cells <port>          — показать ячейки одного порта
        help                  — эта справка
        exit | quit | q       — выйти
    """
    try:
        with _make_charger(args) as charger:
            _shell_loop(charger, args)
    except SkyRCError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


def _shell_loop(charger: SkyRCCharger, args: argparse.Namespace) -> None:
    from .enums import Port

    print(f"[{args.transport.upper()}] connected")
    print("type 'help' for commands, 'exit' to quit\n")

    while True:
        try:
            line = input("pyskyrc> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            continue

        # разбить на токены
        tokens = line.split()
        cmd = tokens[0].lower()
        rest = tokens[1:]

        if cmd in ("exit", "quit", "q"):
            break

        elif cmd == "help":
            print(
                "commands:\n"
                "  status                — snapshot of all ports\n"
                "  info                  — serial + firmware version\n"
                "  start <port> [opts]   — start charge, e.g. "
                "'start B --chem LiPo --cells 6 --current 2.0'\n"
                "  stop <port>           — stop charge\n"
                "  monitor               — live stream (Ctrl+C to exit)\n"
                "  cells <port>          — show cells of one port\n"
                "  exit | quit | q       — quit\n"
            )

        elif cmd == "info":
            info = charger.get_info(timeout=2.0)
            if info is None:
                print("no reply")
            else:
                print(f"Serial:  {info.serial}")
                print(f"Version: {info.version}")

        elif cmd == "status":
            data = charger.read_telemetry(timeout=1.0)
            print()
            for port in Port:
                _print_status_row(port, data.get(port))
            print()

        elif cmd == "cells":
            if not rest:
                print("usage: cells <port>")
                continue
            try:
                port = Port.from_name(rest[0])
            except ValueError as exc:
                print(f"error: {exc}")
                continue
            data = charger.read_telemetry(timeout=1.0)
            info = data.get(port)
            if info is None or not info.has_battery:
                print(f"  {port.name}: no data")
                continue
            cells = " ".join(f"{v:.3f}" for v in info.cells_v)
            print(
                f"  {port.name}: {info.state.name.lower()} "
                f"{info.total_v:.3f}V  Δ{info.delta_mv}mV  "
                f"T={info.temperature_c}°C\n"
                f"           [{cells}]"
            )

        elif cmd == "start":
            _shell_start(charger, rest)

        elif cmd == "stop":
            _shell_stop(charger, rest)

        elif cmd == "monitor":
            print("monitor — Ctrl+C to return to shell")
            try:
                charger.monitor(
                    lambda info: _print_status_row(info.port, info),
                    interval=0.25,
                )
            except KeyboardInterrupt:
                print()

        else:
            print(f"unknown command: {cmd!r} (try 'help')")


def _shell_start(charger: SkyRCCharger, tokens: list[str]) -> None:
    from .enums import Chemistry, LiMode, NiMode, PbMode, Port

    if not tokens:
        print("usage: start <port> [--chem X] [--cells N] [--current A] ...")
        return

    try:
        port = Port.from_name(tokens[0])
    except ValueError as exc:
        print(f"error: {exc}")
        return

    # разбор опций
    chem_name = "LiPo"
    cells = None
    current = 1.0
    discharge = 0.5
    chg_cut = None
    dch_cut = None
    trickle = 49
    mode_raw = None

    i = 1
    while i < len(tokens):
        t = tokens[i]
        if t in ("--chem", "--chemistry") and i + 1 < len(tokens):
            chem_name = tokens[i + 1]; i += 2
        elif t == "--cells" and i + 1 < len(tokens):
            cells = int(tokens[i + 1]); i += 2
        elif t in ("--current", "--charge") and i + 1 < len(tokens):
            current = float(tokens[i + 1]); i += 2
        elif t == "--discharge" and i + 1 < len(tokens):
            discharge = float(tokens[i + 1]); i += 2
        elif t == "--chg-cut" and i + 1 < len(tokens):
            chg_cut = int(tokens[i + 1]); i += 2
        elif t == "--dch-cut" and i + 1 < len(tokens):
            dch_cut = int(tokens[i + 1]); i += 2
        elif t == "--trickle" and i + 1 < len(tokens):
            trickle = int(tokens[i + 1]); i += 2
        elif t == "--mode" and i + 1 < len(tokens):
            mode_raw = int(tokens[i + 1]); i += 2
        else:
            print(f"unknown option: {t}")
            return

    try:
        chem = Chemistry[chem_name]
    except KeyError:
        print(f"unknown chemistry: {chem_name}")
        return

    if cells is None:
        print("--cells is required")
        return

    if mode_raw is None:
        if chem in (Chemistry.LiPo, Chemistry.LiIo,
                    Chemistry.LiFe, Chemistry.LiHV):
            mode_raw = int(LiMode.BALANCE_CHARGE)
        elif chem in (Chemistry.NiMH, Chemistry.NiCd):
            mode_raw = int(NiMode.CHARGE)
        else:
            mode_raw = int(PbMode.NORMAL)

    params = ChargeParameters(
        chemistry=chem,
        cells=cells,
        mode=mode_raw,
        charge_current_a=current,
        discharge_current_a=discharge,
        charge_cutoff_mv=chg_cut,
        discharge_cutoff_mv=dch_cut,
        trickle_ma=trickle,
    )

    ok = charger.start_charge(port, params)
    print("OK" if ok else "FAIL: no ACK")


def _shell_stop(charger: SkyRCCharger, tokens: list[str]) -> None:
    from .enums import Port

    if not tokens:
        print("usage: stop <port>")
        return
    try:
        port = Port.from_name(tokens[0])
    except ValueError as exc:
        print(f"error: {exc}")
        return

    ok = charger.stop_charge(port)
    print("OK" if ok else "FAIL: no ACK")

# ============================================================
#  main
# ============================================================

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pyskyrc",
        description="SkyRC Q200neo / T1000 control and telemetry",
    )
    p.add_argument("--version", action="version",
                   version=f"%(prog)s {__version__}")

    # --- transport flags (глобальные, до подкоманды) ---
    p.add_argument(
        "--transport", choices=("usb", "ble"), default="usb",
        help="transport to use (default: usb)",
    )
    p.add_argument("--hid", default="",
               help="path to hidraw (Linux only); empty = auto-detect via hidapi")
    p.add_argument(
        "--ble-address", default="",
        help="BLE MAC address (empty = auto-discover by name)",
    )
    p.add_argument(
        "--ble-name", default="Charger",
        help="BLE name substring for auto-discovery (default: Charger)",
    )
    p.add_argument(
        "-v", "--verbose", action="store_true",
        help="enable debug logging",
    )

    sub = p.add_subparsers(dest="cmd", required=True)

    # info
    sub.add_parser("info", help="query serial + firmware version")

    # status
    sub.add_parser("status", help="one-shot snapshot of all ports")

    # monitor
    pm = sub.add_parser("monitor", help="continuous monitoring")
    pm.add_argument("--interval", type=float, default=0.25,
                    help="poll interval in seconds (default: 0.25)")

    # start
    ps = sub.add_parser("start", help="start charge on a port")
    ps.add_argument("port", choices=list("ABCDabcd"))
    ps.add_argument("--chem", default="LiPo",
                    choices=[c.name for c in Chemistry])
    ps.add_argument("--cells", type=int, required=True)
    ps.add_argument("--mode", type=int,
                    help="raw mode byte (default: per chemistry)")
    ps.add_argument("--current", type=float, default=1.0,
                    help="charge current, A (default: 1.0)")
    ps.add_argument("--discharge", type=float, default=0.5,
                    help="discharge current, A (default: 0.5)")
    ps.add_argument("--chg-cut", type=int, metavar="MV",
                    help="charge cutoff, mV (default: per chemistry)")
    ps.add_argument("--dch-cut", type=int, metavar="MV",
                    help="discharge cutoff, mV (default: per chemistry)")
    ps.add_argument("--trickle", type=int,
                    default=protocol.DEFAULT_TRICKLE_MA,
                    help="trickle current, mA (default: 49)")
    ps.add_argument("--repeat", type=int, default=0,
                    help="RE-PEAK repeat count 0..3 (default: 0)")
    ps.add_argument("--cycles", type=int, default=0,
                    help="cycle count 0..3 (default: 0)")

    psc = sub.add_parser("scan", help="scan for BLE chargers")
    psc.add_argument("--scan-timeout", type=float, default=6.0)
    psc.set_defaults(func=cmd_scan)
    # shell
    psh = sub.add_parser("shell", help="interactive session")
    psh.set_defaults(func=cmd_shell)
    # stop
    pt = sub.add_parser("stop", help="stop charge on a port")
    pt.add_argument("port", choices=list("ABCDabcd"))

    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s %(message)s",
    )
    # pyskyrc.transport_ble — INFO, чтобы видеть прогресс
    logging.getLogger("pyskyrc").setLevel(
        logging.DEBUG if args.verbose else logging.INFO
    )

    dispatch = {
        "info": cmd_info,
        "status": cmd_status,
        "monitor": cmd_monitor,
        "start": cmd_start,
        "stop": cmd_stop,
        "scan": cmd_scan,
        "shell": cmd_shell,
    }
    return dispatch[args.cmd](args)

if __name__ == "__main__":
    sys.exit(main())
