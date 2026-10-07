"""Поиск BLE-зарядников SkyRC."""

from __future__ import annotations

import asyncio
import logging
import subprocess
from dataclasses import dataclass

try:
    from bleak import BleakScanner
except ImportError:
    BleakScanner = None  # type: ignore


log = logging.getLogger(__name__)

DEFAULT_SCAN_TIMEOUT = 20.0
DEFAULT_NAME_HINT = "Charger"


@dataclass(frozen=True, slots=True)
class ChargerCandidate:
    address: str
    name: str
    rssi: int

    def __str__(self) -> str:
        return f"{self.name or '(unnamed)'} ({self.address}, RSSI={self.rssi})"


async def scan_chargers(
    *,
    timeout: float = DEFAULT_SCAN_TIMEOUT,
    name_hint: str = DEFAULT_NAME_HINT,
    early_exit: bool = True,
) -> list[ChargerCandidate]:
    """
    Слушает advertisement-пакеты через callback.
    Возвращает все найденные зарядники (фильтр по name_hint).

    early_exit=True → выходит из ожидания после первой находки.
    """
    if BleakScanner is None:
        raise ImportError("bleak is required: pip install bleak")

    log.debug("BLE scan start, timeout=%.1fs, hint=%r", timeout, name_hint)

    found: dict[str, ChargerCandidate] = {}
    done = asyncio.Event()

    def on_detect(dev, adv):
        name = (dev.name or "").strip()
        if not name and getattr(adv, "local_name", None):
            name = adv.local_name.strip()
        rssi = adv.rssi if adv.rssi is not None else -999

        is_match = not name_hint or name_hint.lower() in name.lower()
        log.debug(
            "  adv: %s name=%r rssi=%s match=%s", dev.address, name, rssi, is_match
        )

        if is_match:
            found[dev.address] = ChargerCandidate(
                address=dev.address,
                name=name or "(unknown)",
                rssi=rssi,
            )
            if early_exit and not done.is_set():
                done.set()

    async with BleakScanner(detection_callback=on_detect):
        try:
            await asyncio.wait_for(done.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            log.debug("BLE scan timeout")

    result = sorted(found.values(), key=lambda c: c.rssi, reverse=True)
    log.debug("BLE scan found %d charger(s)", len(result))
    return result


def scan_chargers_sync(**kwargs) -> list[ChargerCandidate]:
    return asyncio.run(scan_chargers(**kwargs))


def list_paired_devices() -> list[tuple[str, str]]:
    """Список paired MAC-ов. Возвращает [(mac, name), ...]."""
    try:
        out = subprocess.check_output(
            ["bluetoothctl", "devices", "Paired"],
            stderr=subprocess.DEVNULL,
            timeout=3.0,
        ).decode("utf-8", errors="replace")
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return []

    result: list[tuple[str, str]] = []
    for line in out.splitlines():
        parts = line.strip().split(" ", 2)
        if len(parts) < 3 or parts[0] != "Device":
            continue
        result.append((parts[1], parts[2]))
    return result


def list_all_known_devices() -> list[tuple[str, str]]:
    """Все устройства, известные BlueZ (paired + discovered)."""
    try:
        out = subprocess.check_output(
            ["bluetoothctl", "devices"],
            stderr=subprocess.DEVNULL,
            timeout=3.0,
        ).decode("utf-8", errors="replace")
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return []

    result: list[tuple[str, str]] = []
    for line in out.splitlines():
        parts = line.strip().split(" ", 2)
        if len(parts) < 3 or parts[0] != "Device":
            continue
        result.append((parts[1], parts[2]))
    return result
