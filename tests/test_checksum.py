"""Checksum tests — real payloads from usbmon."""

import pytest

from pyskyrc.protocol import checksum


def _pkt(hex_head: str) -> bytes:
    """Build a 64-byte packet from the first 24 bytes."""
    data = bytes.fromhex(hex_head)
    return data + b"\x00" * (64 - len(data))


# Real START payloads captured from Charge Master 1.55.E207
KNOWN_START = [
    # B LiPo 6S BAL.CHG 1.0/0.5 3.00/4.20
    ("0f1605020006000a050bb810680000003100000000000088", 0x88),
    # B LiPo 6S BAL.CHG 2.0/0.5
    ("0f16050200060014050bb810680000003100000000000092", 0x92),
    # B LiPo 6S DISCHARGE 1.0/1.0
    ("0f1605020006020a0a0bb81068000000310000000000008f", 0x8f),
    # A LiPo 6S BAL.CHG 1.0/0.5
    ("0f1605010006000a050bb810680000003100000000000087", 0x87),
    # D LiPo 6S BAL.CHG 1.0/0.5
    ("0f1605080006000a050ce4106800000031000000000000bb", 0xbb),
    # B NiMH 6S CHARGE trickle=300mA
    ("0f1605020406000a05038400060100002c000000000000da", 0xda),
    # B NiMH 4S RE-PEAK repeat=3
    ("0f1605020404030a050384000603000031000000000000e2", 0xe2),
    # B Pb 12S NORMAL 1.0/0.5
    ("0f160502060c000a050708096000000031000000000000d1", 0xd1),
    # B LiIo 6S BAL.CHG
    ("0f1605020106000a050c80100400000031000000000000ee", 0xee),
]


@pytest.mark.parametrize("hex_head,expected", KNOWN_START)
def test_checksum_start(hex_head: str, expected: int) -> None:
    pkt = _pkt(hex_head)
    assert checksum(pkt) == expected


def test_checksum_port_a_uses_same_formula():
    """Port A uses the same +5 formula as B/C/D (verified on 6S payload)."""
    pkt_a = _pkt("0f1605010006000a050bb810680000003100000000000087")
    assert pkt_a[3] == 0x01
    assert checksum(pkt_a) == 0x87

    # D LiPo 6S START — same body except selector
    pkt_d = _pkt("0f1605080006000a050ce4106800000031000000000000bb")
    assert pkt_d[3] == 0x08
    assert checksum(pkt_d) == 0xbb
