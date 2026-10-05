"""Высокоуровневый API."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable

from . import protocol, telemetry
from .device import HIDDevice, DEFAULT_PATH
from .transport_ble import BLEDevice
from .enums import Chemistry, CycleDirection, Port, State
from .exceptions import InvalidParameterError, SkyRCError

log = logging.getLogger(__name__)

ACK_TIMEOUT_USB = 5.0
ACK_TIMEOUT_BLE = 2.0
ACK_SILENCE_USB = 1.8
ACK_SILENCE_BLE = 0.05
POLL_INTERVAL   = 0.25


@dataclass(frozen=True, slots=True)
class ChargeParameters:
    chemistry: Chemistry
    cells: int
    mode: int
    charge_current_a: float = 1.0
    discharge_current_a: float = 0.5
    charge_cutoff_mv: int | None = None
    discharge_cutoff_mv: int | None = None
    trickle_ma: int = 49
    repeat_count: int = 0
    cycle_count: int = 0
    cycle_direction: CycleDirection = CycleDirection.CHARGE_DISCHARGE

    def __post_init__(self) -> None:
        if not (1 <= self.cells <= 15):
            raise InvalidParameterError(
                f"cells must be 1..15, got {self.cells}"
            )
        if not (0 < self.charge_current_a <= 30):
            raise InvalidParameterError(
                f"charge_current_a must be in (0, 30], got {self.charge_current_a}"
            )
        if not (0 < self.discharge_current_a <= 30):
            raise InvalidParameterError(
                f"discharge_current_a must be in (0, 30], got {self.discharge_current_a}"
            )


@dataclass
class _Stats:
    packets_sent: int = 0
    packets_received: int = 0
    acks: int = 0
    started_at: float = field(default_factory=time.monotonic)


class SkyRCCharger:
    """High-level interface to SkyRC Q200neo / T1000."""

    def __init__(
        self,
        path: str = DEFAULT_PATH,
        *,
        transport: str = "usb",
        ble_address: str = "",
        ble_name: str = "Charger",
        poll_ports: tuple[Port, ...] = (Port.A, Port.B, Port.C, Port.D),
    ) -> None:
        if transport == "usb":
            self._device = HIDDevice(path)
        elif transport == "ble":
            self._device = BLEDevice(
                address=ble_address,
                name_match=ble_name or "Charger",
            )
        else:
            raise ValueError(f"unknown transport: {transport!r}")

        self._transport = transport
        self._poll_ports = poll_ports
        self._stats = _Stats()

    # ---- lifecycle ----

    def open(self) -> "SkyRCCharger":
        self._device.open()
        return self

    def close(self) -> None:
        self._device.close()

    def __enter__(self) -> "SkyRCCharger":
        return self.open()

    def __exit__(self, *args: object) -> None:
        self.close()

    @property
    def stats(self) -> _Stats:
        return self._stats

    # ---- device info ----

    def get_info(self, timeout: float = 1.0) -> protocol.DeviceInfo | None:
        if self._transport == "ble":
            pkt = protocol.frame_query_serial_ble(int(Port.A))
        else:
            pkt = protocol.frame_query_serial(int(Port.A))
        self._device.write(pkt)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            pkt_in = self._device.read(timeout=0.1)
            if pkt_in is None:
                continue
            info = protocol.parse_device_info(pkt_in)
            if info is not None:
                return info
        return None

    # ---- polling ----

    def _poll_once(self) -> list[bytes]:
        for port in self._poll_ports:
            if self._transport == "ble":
                pkt = protocol.frame_per_port_ble(int(port))
            else:
                pkt = protocol.frame_per_port(int(port))
            self._device.write(pkt)
            self._stats.packets_sent += 1
            time.sleep(0.004 if self._transport == "usb" else 0.01)
        return self._device.drain(
            timeout=0.02 if self._transport == "usb" else 0.05
        )

    def poll(self, duration: float = 0.5) -> dict[Port, telemetry.PortTelemetry]:
        deadline = time.monotonic() + duration
        result: dict[Port, telemetry.PortTelemetry] = {}
        while time.monotonic() < deadline:
            for pkt in self._poll_once():
                self._stats.packets_received += 1
                info = telemetry.parse_telemetry(pkt)
                if info is None:
                    continue
                result[info.port] = info
        return result

    def read_telemetry(
        self, timeout: float = 0.5
    ) -> dict[Port, telemetry.PortTelemetry]:
        return self.poll(duration=timeout)

    def monitor(
        self,
        callback: Callable[[telemetry.PortTelemetry], None],
        *,
        interval: float = POLL_INTERVAL,
        only_changes: bool = True,
    ) -> None:
        last: dict[Port, tuple] = {}
        while True:
            for pkt in self._poll_once():
                info = telemetry.parse_telemetry(pkt)
                if info is None:
                    continue
                if only_changes:
                    key = (info.state, info.temperature_c, info.cells_mv)
                    if last.get(info.port) == key:
                        continue
                    last[info.port] = key
                callback(info)
            time.sleep(interval)

    # ---- control ----

    def start_charge(
        self,
        port: Port,
        params: ChargeParameters,
        *,
        wait_ack: bool = True,
        timeout: float | None = None,
    ) -> bool:
        if self._transport == "ble":
            pkt = protocol.build_start_packet_ble(
                port=port,
                chemistry=params.chemistry,
                cells=params.cells,
                mode=params.mode,
                charge_current_a=params.charge_current_a,
                discharge_current_a=params.discharge_current_a,
                charge_cutoff_mv=params.charge_cutoff_mv,
                discharge_cutoff_mv=params.discharge_cutoff_mv,
            )
            if timeout is None:
                timeout = ACK_TIMEOUT_BLE
            silence = ACK_SILENCE_BLE
        else:
            pkt = protocol.build_start_packet(
                port=port,
                chemistry=params.chemistry,
                cells=params.cells,
                mode=params.mode,
                charge_current_a=params.charge_current_a,
                discharge_current_a=params.discharge_current_a,
                charge_cutoff_mv=params.charge_cutoff_mv,
                discharge_cutoff_mv=params.discharge_cutoff_mv,
                trickle_ma=params.trickle_ma,
                repeat_count=params.repeat_count,
                cycle_count=params.cycle_count,
                cycle_direction=params.cycle_direction,
            )
            if timeout is None:
                timeout = ACK_TIMEOUT_USB
            silence = ACK_SILENCE_USB

        return self._send_and_wait(
            pkt,
            expected_cmd=0x05,
            wait_ack=wait_ack,
            timeout=timeout,
            ack_silence=silence,
        )

    def stop_charge(
        self,
        port: Port,
        *,
        wait_ack: bool = True,
        timeout: float | None = None,
    ) -> bool:
        if self._transport == "ble":
            pkt = protocol.build_stop_packet_ble(port)
            if timeout is None:
                timeout = ACK_TIMEOUT_BLE
            silence = ACK_SILENCE_BLE
        else:
            pkt = protocol.build_stop_packet(port)
            if timeout is None:
                timeout = ACK_TIMEOUT_USB
            silence = ACK_SILENCE_USB

        return self._send_and_wait(
            pkt,
            expected_cmd=0xFE,
            wait_ack=wait_ack,
            timeout=timeout,
            ack_silence=silence,
        )

    # ---- internals ----

    def _send_and_wait(
        self,
        packet: bytes,
        *,
        expected_cmd: int,
        wait_ack: bool,
        timeout: float,
        ack_silence: float,
    ) -> bool:
        self._device.drain(timeout=0.02)
        self._device.write(packet)
        self._stats.packets_sent += 1

        if not wait_ack:
            return True

        t0 = time.monotonic()
        deadline = t0 + timeout
        got_ack = False

        while time.monotonic() < deadline:
            # ────── USB: нужен polling для keep-alive
            # ────── BLE: ACK приходит сам, polling может съесть его
            if self._transport == "usb" and (time.monotonic() - t0 > ack_silence):
                for port in self._poll_ports:
                    self._device.write(protocol.frame_per_port(int(port)))
                time.sleep(0.05)

            pkt = self._device.read(timeout=0.005)
            if pkt is None:
                continue
            self._stats.packets_received += 1

            event = telemetry.parse_event(pkt)
            if event is None:
                continue

            if (
                (expected_cmd == 0x05 and event.kind is telemetry.EventKind.START)
                or (expected_cmd == 0xFE and event.kind is telemetry.EventKind.STOP)
            ):
                got_ack = True
                self._stats.acks += 1
                break

        return got_ack