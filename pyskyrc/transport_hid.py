"""
Кроссплатформенный HID-транспорт.

Поддерживает два API под именем `hid`:
  · apmorton/hid    (Linux, macOS)  — hid.Device(path=...), write требует b"\\x00" + packet
  · cython-hidapi   (Windows)        — hid.device(), open_path(), write тоже с b"\\x00"
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

from .exceptions import DeviceNotFoundError, DeviceIOError


log = logging.getLogger(__name__)

REPORT_SIZE = 64
SKYRC_MANUFACTURER = "SkyRC"
SKYRC_PRODUCT_HINTS = ("T1000", "Q200neo", "Q200", "Charger")
REPORT_ID_BYTE = b"\x00"

# Определяем API по наличию символа
_USE_NEW_API = hid is not None and hasattr(hid, "Device")   # apmorton
_USE_OLD_API = hid is not None and not _USE_NEW_API and hasattr(hid, "device")  # cython-hidapi


class HIDAPIDevice:
    """
    Кроссплатформенный HID-транспорт с автоопределением API.
    """

    def __init__(self, path: str = "", *, auto_discover: bool = True) -> None:
        if _HID_IMPORT_ERROR is not None:
            raise ImportError(
                "hid is required for USB transport: "
                "pip install hid    (or: pip install hidapi on Windows)"
            ) from _HID_IMPORT_ERROR

        if not (_USE_NEW_API or _USE_OLD_API):
            raise ImportError(
                "unsupported 'hid' package. Install either "
                "'hid' (apmorton) or 'hidapi' (cython-hidapi)."
            )

        self._path = path
        self._auto_discover = auto_discover
        self._dev = None

    @property
    def path(self) -> str:
        return self._path

    @property
    def is_open(self) -> bool:
        return self._dev is not None

    # ---- lifecycle ----

    def open(self) -> None:
        if self._dev is not None:
            return

        target = self._find_device()
        if target is None:
            raise DeviceNotFoundError(
                "SkyRC charger not found over USB HID."
            )

        try:
            if _USE_NEW_API:
                self._dev = hid.Device(path=target["path"])
            else:
                self._dev = hid.device()
                self._dev.open_path(target["path"])
        except OSError as exc:
            raise DeviceIOError(
                f"failed to open HID device {target['path']}: {exc}"
            ) from exc

        p = target.get("path")
        self._path = p.decode(errors="replace") if isinstance(p, bytes) else str(p or "")
        log.info(
            "USB HID opened: %s %s",
            target.get("manufacturer_string"),
            target.get("product_string"),
        )

    def _find_device(self) -> dict | None:
        if self._path:
            for d in hid.enumerate():
                p = d.get("path")
                p_str = p.decode(errors="replace") if isinstance(p, bytes) else str(p)
                if p_str == self._path:
                    return d
            return None

        if not self._auto_discover:
            return None

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
        if self._dev is None:
            return
        try:
            self._dev.close()
        except Exception:
            pass
        self._dev = None

    def __enter__(self) -> "HIDAPIDevice":
        self.open()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # ---- I/O ----

    def write(self, packet: bytes) -> int:
        if self._dev is None:
            raise DeviceIOError("HID device is not open")
        if len(packet) != REPORT_SIZE:
            raise DeviceIOError(
                f"packet must be {REPORT_SIZE} bytes, got {len(packet)}"
            )
        try:
            n = self._dev.write(REPORT_ID_BYTE + packet)
        except Exception as exc:
            raise DeviceIOError(f"write failed: {exc}") from exc
        # apmorton возвращает число записанных байт (65),
        # cython-hidapi может вернуть -1 или число (зависит от версии)
        return n if n > 0 else REPORT_SIZE

    def read(self, timeout: float = 0.05) -> bytes | None:
        if self._dev is None:
            raise DeviceIOError("HID device is not open")

        timeout_ms = max(1, int(timeout * 1000))
        try:
            if _USE_NEW_API:
                data = self._dev.read(REPORT_SIZE, timeout=timeout_ms)
            else:
                data = self._dev.read(REPORT_SIZE, timeout_ms)
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