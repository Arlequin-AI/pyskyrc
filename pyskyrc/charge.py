"""
START/STOP + ожидание ACK + init handshake.

Поддерживает два транспорта:
  · USB HID — кадры фиксированной длины (64 байта)
  · BLE     — кадры переменной длины (0f LEN payload CHK)
"""

from __future__ import annotations

import logging
import time

from . import protocol, telemetry
from .enums import Port

log = logging.getLogger(__name__)


# ---- константы ----
ACK_TIMEOUT_USB = 5.0
ACK_TIMEOUT_BLE = 2.0
ACK_SILENCE_USB = 1.8
ACK_SILENCE_BLE = 0.05


# ============================================================
#  Init handshake
# ============================================================


def init_handshake(dev, verbose: bool = False) -> None:
    """
    Опциональная инициализация: серийник + версия прошивки.
    Не обязательна для polling, но воспроизводит рукопожатие
    официального Charge Master.
    """
    dev.drain(0.05)

    # 1. serial
    dev.write(protocol.frame_query_serial(int(Port.A)))
    time.sleep(0.05)
    reply = dev.read(timeout=0.5)
    if reply and verbose:
        info = protocol.parse_device_info(reply)
        if info:
            print(f"  Serial:  {info.serial}")
            print(f"  Version: {info.version}")

    # 2. firmware
    dev.write(protocol.frame_query_firmware(int(Port.A)))
    time.sleep(0.05)
    reply = dev.read(timeout=0.5)
    if reply and verbose:
        print(f"  Firmware reply: {reply[:16].hex(' ')}")


# ============================================================
#  START / STOP
# ============================================================


def start(
    dev,
    port: Port,
    *,
    transport: str = "usb",
    verbose: bool = False,
    **kwargs,
) -> bool:
    """Отправить START-команду и дождаться ACK."""
    if transport == "ble":
        pkt = protocol.build_start_packet_ble(port, **kwargs)
        timeout = ACK_TIMEOUT_BLE
        silence = ACK_SILENCE_BLE
    else:
        pkt = protocol.build_start_packet(port, **kwargs)
        timeout = ACK_TIMEOUT_USB
        silence = ACK_SILENCE_USB

    return _send_and_wait(
        dev,
        pkt,
        expect_cmd=0x05,
        transport=transport,
        ack_silence=silence,
        timeout=timeout,
        verbose=verbose,
    )


def stop(
    dev,
    port: Port,
    *,
    transport: str = "usb",
    verbose: bool = False,
) -> bool:
    """Отправить STOP-команду и дождаться ACK."""
    if transport == "ble":
        pkt = protocol.build_stop_packet_ble(port)
        timeout = ACK_TIMEOUT_BLE
        silence = ACK_SILENCE_BLE
    else:
        pkt = protocol.build_stop_packet(port)
        timeout = ACK_TIMEOUT_USB
        silence = ACK_SILENCE_USB

    return _send_and_wait(
        dev,
        pkt,
        expect_cmd=0xFE,
        transport=transport,
        ack_silence=silence,
        timeout=timeout,
        verbose=verbose,
    )


# ============================================================
#  Internals
# ============================================================


def _send_and_wait(
    dev,
    pkt: bytes,
    *,
    expect_cmd: int,
    transport: str,
    ack_silence: float,
    timeout: float,
    verbose: bool = False,
) -> bool:
    dev.drain(0.02)
    dev.write(pkt)
    if verbose:
        print(f"  TX: {pkt[:28].hex(' ')}")

    t0 = time.monotonic()
    deadline = t0 + timeout
    ack = False

    while time.monotonic() < deadline:
        # держим polling после паузы на ACK
        if time.monotonic() - t0 > ack_silence:
            for sel in (0x01, 0x02, 0x04, 0x08):
                if transport == "ble":
                    dev.write(protocol.frame_per_port_ble(sel))
                    time.sleep(0.01)
                else:
                    dev.write(protocol.frame_per_port(sel))
                    time.sleep(0.003)
            time.sleep(0.05 if transport == "usb" else 0.01)

        pkt_in = dev.read(timeout=0.02)
        if not pkt_in:
            continue

        event = telemetry.parse_event(pkt_in)
        if event is None:
            continue

        if verbose:
            print(f"  [EVENT] {event.kind.name} {event.port.name}")

        if (expect_cmd == 0x05 and event.kind is telemetry.EventKind.START) or (
            expect_cmd == 0xFE and event.kind is telemetry.EventKind.STOP
        ):
            ack = True
            break

    return ack
