"""
SkyRC Q200neo / T1000 HID protocol.

Поддерживает два формата кадров:

1. USB HID (fixed-length, 64 байта):
      b0-b2   = 0f 16 05 | 0f 03 XX ...
      b23     = checksum = (sum(b3..b22) + 5) & 0xff
      (b3 — селектор порта, входит в сумму)

2. BLE (variable-length):
      [0f] [LEN] [payload...] [CHK]
      LEN = len(payload) + 1
      CHK = sum(payload) & 0xff
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from .enums import Chemistry, CycleDirection, Port

REPORT_SIZE: Final = 64
DEFAULT_TRICKLE_MA: Final = 49


# ============================================================================
#  Device info
# ============================================================================

@dataclass(frozen=True, slots=True)
class DeviceInfo:
    serial: str
    version: str
    raw: bytes


def parse_device_info(packet: bytes) -> DeviceInfo | None:
    """
    Разобрать ответ 0f1457XX (USB) — 64 байта.
    Для BLE ответ короче, но начало совпадает.
    """
    if len(packet) < 20:
        return None
    if packet[0] != 0x0F:
        return None
    # packet[1] — длина кадра: 0x13 для BLE, 0x14 для USB
    if packet[1] not in (0x13, 0x14):
        return None
    if packet[2] != 0x57:
        return None

    serial_bytes = packet[5:11]
    try:
        serial = serial_bytes.decode("ascii")
    except UnicodeDecodeError:
        serial = serial_bytes.hex()

    # BLE-версия короче; для USB version в b16..b19
    if len(packet) >= 20:
        ver = ".".join(str(b) for b in packet[16:20])
    else:
        ver = "unknown"

    return DeviceInfo(serial=serial, version=ver, raw=bytes(packet))


# ============================================================================
#  Checksum (USB)
# ============================================================================

def checksum(packet: bytes) -> int:
    """
    Checksum для USB START-пакетов.

    Формула: (sum(b3..b22) + 5) & 0xff.
    Селектор порта (b3) входит в сумму — единая формула для всех портов.

    Проверено на 60+ payload'ах, firmware 3.57.1.0.
    """
    return (sum(packet[3:23]) + 5) & 0xFF


# ============================================================================
#  USB: START / STOP
# ============================================================================

def _mode_byte(mode) -> int:
    return int(mode) & 0xFF


def build_start_packet(
    port: Port,
    chemistry: Chemistry,
    cells: int,
    mode: int,
    charge_current_a: float,
    discharge_current_a: float = 0.5,
    charge_cutoff_mv: int | None = None,
    discharge_cutoff_mv: int | None = None,
    trickle_ma: int = DEFAULT_TRICKLE_MA,
    repeat_count: int = 0,
    cycle_count: int = 0,
    cycle_direction: CycleDirection = CycleDirection.CHARGE_DISCHARGE,
) -> bytes:
    """Собрать USB START-пакет (64 байта)."""
    from ._defaults import DEFAULTS

    if not (1 <= cells <= 15):
        raise ValueError(f"cells must be 1..15, got {cells}")

    d = DEFAULTS[chemistry]
    if charge_cutoff_mv is None:
        charge_cutoff_mv = d.charge_cutoff_mv
    if discharge_cutoff_mv is None:
        discharge_cutoff_mv = d.discharge_cutoff_mv

    pkt = bytearray(REPORT_SIZE)
    pkt[0] = 0x0F
    pkt[1] = 0x16
    pkt[2] = 0x05
    pkt[3] = int(port)
    pkt[4] = int(chemistry)
    pkt[5] = cells & 0xFF
    pkt[6] = _mode_byte(mode)
    pkt[7] = int(round(charge_current_a * 10)) & 0xFF
    pkt[8] = int(round(discharge_current_a * 10)) & 0xFF
    pkt[9]  = (discharge_cutoff_mv >> 8) & 0xFF
    pkt[10] = discharge_cutoff_mv & 0xFF
    pkt[11] = (charge_cutoff_mv >> 8) & 0xFF
    pkt[12] = charge_cutoff_mv & 0xFF

    from .enums import NiMode
    if chemistry in (Chemistry.NiMH, Chemistry.NiCd) and mode == int(NiMode.CYCLE):
        pkt[13] = int(cycle_direction) & 0xFF
    else:
        pkt[13] = repeat_count & 0xFF

    pkt[14] = cycle_count & 0xFF
    pkt[15] = (trickle_ma >> 8) & 0xFF
    pkt[16] = trickle_ma & 0xFF
    pkt[23] = checksum(pkt)
    return bytes(pkt)


STOP_TEMPLATES: Final[dict[Port, bytes]] = {
    Port.A: bytes.fromhex(
        "0f03fe01ff02000a050ce41068000000"
        "00000000000000000000000000000000"
        "00000000000000000000000000000000"
        "0000000000000000000000000000007f"
    ),
    Port.B: bytes.fromhex(
        "0f03fe020006000a050ce41068000000"
        "31000000000000000000000000000000"
        "00000000000000000000000000000000"
        "000000000000000000000000000000b5"
    ),
    Port.C: bytes.fromhex(
        "0f03fe040206000a050ce41068000000"
        "31000000000000000000000000000000"
        "00000000000000000000000000000000"
        "000000000000000000000000000000b7"
    ),
    Port.D: bytes.fromhex(
        "0f03fe080606000a050ce41068000000"
        "31000000000000000000000000000000"
        "00000000000000000000000000000000"
        "000000000000000000000000000000bb"
    ),
}


def build_stop_packet(port: Port) -> bytes:
    """Собрать USB STOP-пакет."""
    return STOP_TEMPLATES[port]


# ============================================================================
#  USB: polling frames
# ============================================================================

def _poll_frame(p1: int, p2: int, selector: int) -> bytes:
    pkt = bytearray(REPORT_SIZE)
    pkt[0] = 0x0F
    pkt[1] = p1
    pkt[2] = p2
    pkt[3] = selector
    pkt[4] = p2 + selector
    pkt[5] = 0x06
    pkt[7] = 0x0A
    pkt[8] = 0x05
    pkt[9] = 0x0C
    pkt[10] = 0xE4
    pkt[11] = 0x10
    pkt[12] = 0x68
    pkt[16] = 0x31
    pkt[23] = 0xB5
    return bytes(pkt)


def frame_per_port(selector: int) -> bytes:
    """0f0355XX — per-port телеметрия."""
    return _poll_frame(0x03, 0x55, selector)


def frame_bank_a(selector: int) -> bytes:
    """0f035aXX — bank poll A."""
    return _poll_frame(0x03, 0x5A, selector)


def frame_bank_b(selector: int) -> bytes:
    """0f035fXX — bank poll B."""
    return _poll_frame(0x03, 0x5F, selector)


# псевдонимы для совместимости со старым кодом
frame_0355 = frame_per_port
frame_035a = frame_bank_a
frame_035f = frame_bank_b


def frame_query_serial(selector: int) -> bytes:
    """0f0357XX — запрос серийника."""
    pkt = bytearray(REPORT_SIZE)
    pkt[0] = 0x0F
    pkt[1] = 0x03
    pkt[2] = 0x57
    pkt[3] = selector
    pkt[4] = 0x57 + selector
    return bytes(pkt)


def frame_query_firmware(selector: int) -> bytes:
    """0f0366XX — запрос прошивки."""
    pkt = bytearray(REPORT_SIZE)
    pkt[0] = 0x0F
    pkt[1] = 0x03
    pkt[2] = 0x66
    pkt[3] = selector
    pkt[4] = 0x66 + selector
    return bytes(pkt)


# ============================================================================
#  BLE: variable-length frames
# ============================================================================
#
#     [0f] [LEN] [payload...] [CHK]
#     LEN = len(payload) + 1
#     CHK = sum(payload) & 0xff

BLE_HEADER = 0x0F


def _ble_wrap(payload: bytes) -> bytes:
    if not payload:
        raise ValueError("payload must not be empty")
    length = len(payload) + 1
    chk = sum(payload) & 0xFF
    return bytes([BLE_HEADER, length]) + payload + bytes([chk])


def frame_per_port_ble(selector: int) -> bytes:
    return _ble_wrap(bytes([0x55, selector]))


def frame_bank_a_ble(selector: int) -> bytes:
    return _ble_wrap(bytes([0x5A, selector]))


def frame_bank_b_ble(selector: int) -> bytes:
    return _ble_wrap(bytes([0x5F, selector]))


def frame_query_serial_ble(selector: int) -> bytes:
    return _ble_wrap(bytes([0x57, selector]))


def frame_query_firmware_ble(selector: int) -> bytes:
    return _ble_wrap(bytes([0x66, selector]))


def build_stop_packet_ble(port: Port) -> bytes:
    """BLE STOP: payload = [0xfe, selector]."""
    return _ble_wrap(bytes([0xFE, int(port)]))


def build_start_packet_ble(
    port: Port,
    chemistry: Chemistry,
    cells: int,
    mode: int,
    charge_current_a: float,
    discharge_current_a: float = 0.5,
    charge_cutoff_mv: int | None = None,
    discharge_cutoff_mv: int | None = None,
    **ignored: object,
) -> bytes:
    """
    BLE START.

    Payload (17 байт):
        CMD  port  chem  cells  mode  chg  dch
        dch_hi dch_lo  chg_hi chg_lo  00×6
    """
    from ._defaults import DEFAULTS

    d = DEFAULTS[chemistry]
    if charge_cutoff_mv is None:
        charge_cutoff_mv = d.charge_cutoff_mv
    if discharge_cutoff_mv is None:
        discharge_cutoff_mv = d.discharge_cutoff_mv

    payload = bytearray()
    payload.append(0x05)
    payload.append(int(port))
    payload.append(int(chemistry))
    payload.append(cells & 0xFF)
    payload.append(int(mode) & 0xFF)
    payload.append(int(round(charge_current_a * 10)) & 0xFF)
    payload.append(int(round(discharge_current_a * 10)) & 0xFF)
    payload.append((discharge_cutoff_mv >> 8) & 0xFF)
    payload.append(discharge_cutoff_mv & 0xFF)
    payload.append((charge_cutoff_mv >> 8) & 0xFF)
    payload.append(charge_cutoff_mv & 0xFF)
    payload += b"\x00" * 6
    return _ble_wrap(bytes(payload))
