"""Telemetry parser tests."""

from pyskyrc.enums import Port, State
from pyskyrc.telemetry import (
    EventKind,
    parse_event,
    parse_telemetry,
)


def _pkt(hex_head: str) -> bytes:
    data = bytes.fromhex(hex_head.replace(" ", ""))
    return data + b"\x00" * (64 - len(data))


def test_parse_telemetry_real_battery():
    # 0f225501 01 000000 00 5acb 023b 00220000 0f23 0f22 0f21 0f1c 0f21 0f22
    hex_str = (
        "0f225501" "01" "000000" "00"
        "5acb" "023b" "00220000"
        "0f23" "0f22" "0f21" "0f1c" "0f21" "0f22"
    )
    pkt = _pkt(hex_str)
    info = parse_telemetry(pkt)
    assert info is not None
    assert info.port == Port.A
    assert info.state == State.CHARGING
    assert info.temperature_c == 0x22
    assert info.cells_mv == (0x0F23, 0x0F22, 0x0F21, 0x0F1C, 0x0F21, 0x0F22)
    assert info.has_battery is True
    assert abs(info.total_v - 23.2) < 0.1


def test_parse_telemetry_empty():
    # dummy cells = 7,7,7,7,7,7 -> no battery
    hex_str = (
        "0f225508" "02" "000000" "00"
        "0000" "0000" "00000000"
        "0007" "0007" "0007" "0007" "0007" "0007"
    )
    pkt = _pkt(hex_str)
    info = parse_telemetry(pkt)
    assert info is not None
    assert info.has_battery is False
    assert info.cells_mv == ()


def test_parse_telemetry_wrong_frame():
    assert parse_telemetry(b"\x00" * 64) is None


def test_parse_event_start():
    pkt = bytes([0x0F, 0x04, 0x05, 0x02]) + b"\x00" * 60
    ev = parse_event(pkt)
    assert ev is not None
    assert ev.kind is EventKind.START
    assert ev.port == Port.B


def test_parse_event_stop():
    pkt = bytes([0x0F, 0x04, 0xFE, 0x08]) + b"\x00" * 60
    ev = parse_event(pkt)
    assert ev is not None
    assert ev.kind is EventKind.STOP
    assert ev.port == Port.D


def test_parse_event_unknown():
    assert parse_event(b"\x00" * 64) is None
