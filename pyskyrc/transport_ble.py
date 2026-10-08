"""
BLE-транспорт через bleak.
Синхронный API: write / read / drain / close.
"""

from __future__ import annotations

import asyncio
import logging
import queue
import threading
import time
from pathlib import Path

try:
    from bleak import BleakClient, BleakScanner
except ImportError as exc:
    BleakClient = None  # type: ignore[assignment]
    _BLEAK_IMPORT_ERROR = exc
else:
    _BLEAK_IMPORT_ERROR = None

from .exceptions import DeviceIOError, DeviceNotFoundError

log = logging.getLogger(__name__)

CHAR_NOTIFY_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"

# ---- таймауты ----
SCAN_TIMEOUT = 30.0
PROBE_TIMEOUT = 15.0
DIRECT_TIMEOUT = 20.0
CONNECT_TIMEOUT = 90.0

# ---- кеш ----
CACHE_DIR = Path.home() / ".cache" / "pyskyrc"
CACHE_FILE = CACHE_DIR / "last_ble_mac"


def _read_cached_mac() -> str | None:
    try:
        return CACHE_FILE.read_text().strip() or None
    except OSError:
        return None


def _write_cached_mac(address: str) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(address)
    except OSError:
        pass


class BLEDevice:
    def __init__(
        self,
        address: str = "",
        *,
        name_match: str = "Charger",
        char_uuid: str = CHAR_NOTIFY_UUID,
        use_cache: bool = True,
    ) -> None:
        if _BLEAK_IMPORT_ERROR is not None:
            raise ImportError(
                "bleak is required for BLE transport: pip install bleak"
            ) from _BLEAK_IMPORT_ERROR

        self.address = address or ""
        self.name_match = name_match or "Charger"
        self.char_uuid = char_uuid
        self.use_cache = use_cache

        self.debug = False
        self.mac_bytes: bytes | None = None

        self._client: BleakClient | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._rx: queue.Queue[bytes] = queue.Queue()
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._error: BaseException | None = None

    # ---- lifecycle ----

    def open(self) -> None:
        self._thread = threading.Thread(
            target=self._run, name="pyskyrc-ble", daemon=True
        )
        self._thread.start()
        try:
            if not self._ready.wait(timeout=CONNECT_TIMEOUT):
                raise DeviceIOError(
                    f"BLE connect timeout ({CONNECT_TIMEOUT}s). "
                    f"Charger not found or busy."
                )
        except KeyboardInterrupt:
            self._stop.set()
            raise
        if self._error is not None:
            raise self._error

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    def __enter__(self) -> BLEDevice:
        self.open()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # ---- write/read ----

    def write(self, packet: bytes) -> int:
        if self._client is None or self._loop is None:
            raise DeviceIOError("BLE device is not open")
        if self.debug:
            print(f"  [BLE TX] {packet.hex(' ')}")
        fut = asyncio.run_coroutine_threadsafe(
            self._client.write_gatt_char(self.char_uuid, packet, response=False),
            self._loop,
        )
        fut.result(timeout=2.0)
        return len(packet)

    def read(self, timeout: float = 0.05) -> bytes | None:
        try:
            return self._rx.get(timeout=timeout)
        except queue.Empty:
            return None

    def drain(self, timeout: float = 0.0) -> list[bytes]:
        out: list[bytes] = []
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                while True:
                    try:
                        out.append(self._rx.get_nowait())
                    except queue.Empty:
                        break
                break
            pkt = self.read(timeout=remaining)
            if pkt is None:
                break
            out.append(pkt)
        return out

    # ---- background ----

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._main())
        except BaseException as exc:
            self._error = exc
            self._ready.set()
        finally:
            self._loop.close()

    async def _main(self) -> None:
        # ------ Stage 1: cached MAC → direct connect ------
        mac = None
        if self.address:
            mac = self.address
        elif self.use_cache:
            mac = _read_cached_mac()

        if mac:
            log.info("BLE: trying cached/known MAC %s", mac)
            client = await self._connect_and_verify(mac)
            if client is not None:
                log.info("BLE: %s — CHARGER (cached)", mac)
                await self._finish_connect(client, mac)
                return
            log.info("BLE: cached MAC didn't work, scanning")

        # ------ Stage 2: scan with callback, connect INSIDE ------
        log.info("BLE: scanning (timeout=%.0fs) ...", SCAN_TIMEOUT)

        discovered: dict = {}
        found_event = asyncio.Event()

        def on_detect(dev, adv):
            name = (dev.name or "").strip()
            if not name and getattr(adv, "local_name", None):
                name = adv.local_name.strip()
            rssi = adv.rssi if adv.rssi is not None else -999
            log.debug("  adv: %s name=%r rssi=%s", dev.address, name, rssi)

            if self.name_match.lower() in name.lower():
                if dev.address not in discovered:
                    log.info("BLE: detected %s %s", dev.address, name)
                    discovered[dev.address] = (dev, name, rssi)
                    found_event.set()

        try:
            async with BleakScanner(detection_callback=on_detect):
                try:
                    await asyncio.wait_for(found_event.wait(), timeout=SCAN_TIMEOUT)
                except asyncio.TimeoutError:
                    pass
        except Exception as exc:
            self._error = DeviceIOError(f"BLE scan failed: {type(exc).__name__}: {exc}")
            self._ready.set()
            return

        if not discovered:
            self._error = DeviceNotFoundError(
                f"BLE charger not found (name~{self.name_match!r})"
            )
            self._ready.set()
            return

        # берём сильнейший
        addr, (dev, name, rssi) = max(discovered.items(), key=lambda kv: kv[1][2])
        log.info("BLE: best candidate: %s %s (rssi=%d)", addr, name, rssi)

        # ------ Stage 3: connect к device object ------
        client = await self._connect_device(dev)
        if client is None:
            self._error = DeviceIOError(f"BLE connect failed to {addr}")
            self._ready.set()
            return

        if not await self._is_charger_gatt(client):
            try:
                await client.disconnect()
            except Exception:
                pass
            self._error = DeviceNotFoundError(f"{addr} has no Nordic UART service")
            self._ready.set()
            return

        await self._finish_connect(client, addr)

    # ------ helpers ------

    async def _connect_and_verify(self, mac: str):
        """Direct connect по MAC (строке). Возвращает client если это зарядник."""
        client = BleakClient(mac)
        try:
            async with asyncio.timeout(PROBE_TIMEOUT):
                await client.connect()
        except (TimeoutError, asyncio.TimeoutError):
            log.debug("BLE: %s connect timeout", mac)
            return None
        except Exception as exc:
            log.debug(
                "BLE: %s connect error: %s: %s",
                mac,
                type(exc).__name__,
                exc or "(no message)",
            )
            return None

        if not await self._is_charger_gatt(client):
            try:
                await client.disconnect()
            except Exception:
                pass
            return None
        return client

    async def _connect_device(self, device):
        """Connect по device object (из callback скана)."""
        client = BleakClient(device)
        try:
            async with asyncio.timeout(PROBE_TIMEOUT):
                await client.connect()
        except (TimeoutError, asyncio.TimeoutError):
            log.debug("BLE: connect timeout to %s", device.address)
            return None
        except Exception as exc:
            log.debug(
                "BLE: connect error to %s: %s: %s",
                device.address,
                type(exc).__name__,
                exc or "(no message)",
            )
            return None
        return client

    async def _is_charger_gatt(self, client) -> bool:
        """Проверить, что в GATT есть Nordic UART (0xFFE0 + 0xFFE1)."""
        try:
            services = list(client.services)
        except Exception as exc:
            log.debug("BLE: service discovery failed: %s", exc)
            return False

        log.debug("BLE: %s — %d service(s)", client.address, len(services))
        for svc in services:
            u = str(svc.uuid).lower()
            log.debug("  svc=%s", u)
            if not u.startswith("0000ffe0"):
                continue
            for ch in svc.characteristics:
                cu = str(ch.uuid).lower()
                log.debug("    char=%s props=%s", cu, ch.properties)
                if cu.startswith("0000ffe1"):
                    return True
        return False

    async def _finish_connect(self, client, mac: str) -> None:
        self._client = client
        try:
            self.mac_bytes = bytes.fromhex(mac.replace(":", "").replace("-", ""))
        except (ValueError, AttributeError):
            self.mac_bytes = None

        if self.use_cache:
            _write_cached_mac(mac)
            log.info("BLE: cached MAC %s", mac)

        try:
            await client.start_notify(self.char_uuid, self._on_notify)
        except Exception as exc:
            self._error = DeviceIOError(
                f"BLE start_notify failed: {type(exc).__name__}: {exc}"
            )
            self._ready.set()
            try:
                await client.disconnect()
            except Exception:
                pass
            self._client = None
            return

        self._ready.set()
        log.info("BLE: notify enabled, ready")

        try:
            while not self._stop.is_set():
                await asyncio.sleep(0.1)
        finally:
            try:
                await client.stop_notify(self.char_uuid)
            except Exception:
                pass
            try:
                await client.disconnect()
            except Exception:
                pass
            self._client = None

    def _on_notify(self, _sender: object, data: bytearray) -> None:
        if self.debug:
            print(f"  [BLE RX] {bytes(data).hex(' ')}")
        self._rx.put(bytes(data))
