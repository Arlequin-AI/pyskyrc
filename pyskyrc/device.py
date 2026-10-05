"""
Низкоуровневый доступ к USB HID-устройству зарядника.

Класс HIDDevice предоставляет синхронный интерфейс:
    write(packet) / read(timeout) / drain(timeout) / close()
"""

from __future__ import annotations

import os
import select
import time

from .exceptions import DeviceIOError, DeviceNotFoundError


REPORT_SIZE = 64
DEFAULT_PATH = "/dev/hidraw4"


class HIDDevice:
    """Обёртка над файловым дескриптором HID."""

    def __init__(self, path: str = DEFAULT_PATH) -> None:
        self._path = path
        self._fd: int | None = None

    @property
    def path(self) -> str:
        return self._path

    @property
    def is_open(self) -> bool:
        return self._fd is not None

    # ---- lifecycle ----

    def open(self) -> None:
        if self._fd is not None:
            return
        try:
            self._fd = os.open(self._path, os.O_RDWR | os.O_NONBLOCK)
        except FileNotFoundError as exc:
            raise DeviceNotFoundError(
                f"HID device not found: {self._path}"
            ) from exc
        except PermissionError as exc:
            raise DeviceNotFoundError(
                f"Permission denied: {self._path}. "
                f"Try: sudo chmod 666 {self._path}"
            ) from exc
        except OSError as exc:
            raise DeviceIOError(f"failed to open {self._path}: {exc}") from exc

    def close(self) -> None:
        if self._fd is None:
            return
        try:
            os.close(self._fd)
        except OSError:
            pass
        self._fd = None

    def __enter__(self) -> "HIDDevice":
        self.open()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # ---- I/O ----

    def write(self, packet: bytes) -> int:
        if self._fd is None:
            raise DeviceIOError("device is not open")
        if len(packet) != REPORT_SIZE:
            raise DeviceIOError(
                f"packet must be {REPORT_SIZE} bytes, got {len(packet)}"
            )
        try:
            return os.write(self._fd, packet)
        except OSError:
            # некоторые hidraw требуют leading 0x00 (65 байт)
            try:
                return os.write(self._fd, b"\x00" + packet)
            except OSError as exc:
                raise DeviceIOError(f"write failed: {exc}") from exc

    def read(self, timeout: float = 0.05) -> bytes | None:
        if self._fd is None:
            raise DeviceIOError("device is not open")
        r, _, _ = select.select([self._fd], [], [], timeout)
        if not r:
            return None
        try:
            return os.read(self._fd, REPORT_SIZE)
        except BlockingIOError:
            return None
        except OSError as exc:
            raise DeviceIOError(f"read failed: {exc}") from exc

    def drain(self, timeout: float = 0.0) -> list[bytes]:
        """Прочитать всё, что накопилось, за указанное время."""
        packets: list[bytes] = []
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                # забрать всё мгновенно доступное
                while True:
                    r, _, _ = select.select([self._fd], [], [], 0)
                    if not r:
                        break
                    try:
                        pkt = os.read(self._fd, REPORT_SIZE)
                    except BlockingIOError:
                        break
                    if pkt:
                        packets.append(pkt)
                break
            pkt = self.read(timeout=remaining)
            if pkt is None:
                break
            packets.append(pkt)
        return packets