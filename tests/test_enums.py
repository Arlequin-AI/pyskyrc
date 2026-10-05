"""Enum tests."""

import pytest

from pyskyrc.enums import (
    Chemistry,
    CycleDirection,
    LiMode,
    NiMode,
    PbMode,
    Port,
    State,
)


def test_port_roundtrip():
    assert Port.from_name("a") == Port.A
    assert Port.from_name("B") == Port.B
    assert Port.A.value == 0x01
    assert Port.D.value == 0x08


def test_port_from_name_invalid():
    with pytest.raises(ValueError):
        Port.from_name("X")


def test_chemistry_values():
    assert Chemistry.LiPo == 0x00
    assert Chemistry.Pb == 0x06


def test_li_modes():
    assert LiMode.BALANCE_CHARGE == 0
    assert LiMode.STORAGE == 3


def test_ni_modes():
    assert NiMode.CHARGE == 0
    assert NiMode.RE_PEAK == 3
    assert NiMode.CYCLE == 4


def test_pb_modes():
    assert PbMode.NORMAL == 0
    assert PbMode.COLD_CHARGE == 3


def test_state_name_of():
    assert State.name_of(0x01) == "charging"
    assert State.name_of(0x99) == "unknown(0x99)"


def test_cycle_direction():
    assert CycleDirection.CHARGE_DISCHARGE == 0
    assert CycleDirection.DISCHARGE_CHARGE == 1
