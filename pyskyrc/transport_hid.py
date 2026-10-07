"""
Кроссплатформенный HID-транспорт через `hid` (apmorton).

Работает на Linux, macOS, Windows.
Синхронный API: write / read / drain / close.
"""

from __future__ import annotations

import logging
import time

try:
    import hid
except ImportError as exc:
    hid = None  # type: ignore[assignment]
    _HID_IMPORT_ERROR = exc
else:
    _HID_IMPORT_ERROR = None

from .exceptions import DeviceIOError, DeviceNotFoundError

log = logging.getLogger(__name__)

REPORT_SIZE = 64
SKYRC_MANUFACTURER = "SkyRC"
SKYRC_PRODUCT_HINTS = ("T1000", "Q200neo", "Q200", "Charger")
REPORT_ID_BYTE = b"\x00"


class HIDAPIDevice:
    """
    Кроссплатформенный HID-транспорт.

    Скрывает от вызывающего кода:
      · поиск устройства по manufacturer/product (VID:PID = 0x0000:0x0001 неинформативны)
      · ведущий report ID = 0x00 при записи
      · обрезание report ID при чтении
    """

    def __init__(
        self,
        path: str = "",
        *,
        auto_discover: bool = True,
    ) -> None:
        if _HID_IMPORT_ERROR is not None:
            raise ImportError(
                "hid is required for USB transport: pip install hid"
            ) from _HID_IMPORT_ERROR

        self._path = path
        self._auto_discover = auto_discover
        self._device: hid.Device | None = None

    @property
    def path(self) -> str:
        return self._path

    @property
    def is_open(self) -> bool:
        return self._device is not None

    # ---- lifecycle ----

    def open(self) -> None:
        if self._device is not None:
            return

        target = self._find_device()
        if target is None:
            raise DeviceNotFoundError(
                "SkyRC charger not found over USB HID. "
                "Check cable, power, and udev permissions."
            )

        try:
            self._device = hid.Device(path=target["path"])
        except OSError as exc:
            raise DeviceIOError(
                f"failed to open HID device {target['path']}: {exc}"
            ) from exc

        self._path = target["path"].decode() if isinstance(target["path"], bytes) else str(target["path"])
        log.info(
            "USB HID opened: %s %s",
            target.get("manufacturer_string"),
            target.get("product_string"),
        )

    def _find_device(self) -> dict | None:
        # если задан явный path — использовать его
        if self._path:
            for d in hid.enumerate():
                p = d.get("path")
                p_str = p.decode() if isinstance(p, bytes) else str(p)
                if p_str == self._path:
                    return d
            return None

        if not self._auto_discover:
            return None

        # иначе — искать по manufacturer/product
        candidates = []
        for d in hid.enumerate():
            mfg = (d.get("manufacturer_string") or "").strip()
            prod = (d.get("product_string") or "").strip()
            if mfg == SKYRC_MANUFACTURER:
                candidates.append(d)
                continue
            if any(h in prod for h in SKYRC_PRODUCT_HINTS):
                candidates.append(d)

        if not candidates:
            return None
        if len(candidates) > 1:
            log.warning(
                "multiple SkyRC HID devices found (%d); using first: %s",
                len(candidates),
                candidates[0].get("product_string"),
            )
        return candidates[0]

    def close(self) -> None:
        if self._device is None:
            return
        try:
            self._device.close()
        except Exception:
            pass
        self._device = None

    def __enter__(self) -> HIDAPIDevice:
        self.open()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # ---- I/O ----

    def write(self, packet: bytes) -> int:
        if self._device is None:
            raise DeviceIOError("HID device is not open")
        if len(packet) != REPORT_SIZE:
            raise DeviceIOError(
                f"packet must be {REPORT_SIZE} bytes, got {len(packet)}"
            )
        try:
            n = self._device.write(REPORT_ID_BYTE + packet)
        except Exception as exc:
            raise DeviceIOError(f"write failed: {exc}") from exc
        return n - len(REPORT_ID_BYTE)

    def read(self, timeout: float = 0.05) -> bytes | None:
        if self._device is None:
            raise DeviceIOError("HID device is not open")
        timeout_ms = max(1, int(timeout * 1000))
        try:
            data = self._device.read(REPORT_SIZE, timeout=timeout_ms)
        except Exception as exc:
            raise DeviceIOError(f"read failed: {exc}") from exc
        if not data:
            return None
        return bytes(data)

    def drain(self, timeout: float = 0.0) -> list[bytes]:
        packets: list[bytes] = []
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                # мгновенный вычерп
                while True:
                    pkt = self.read(timeout=0.001)
                    if pkt is None:
                        break
                    packets.append(pkt)
                break
            pkt = self.read(timeout=min(remaining, 0.05))
            if pkt is None:
                continue
            packets.append(pkt)
        return packets
