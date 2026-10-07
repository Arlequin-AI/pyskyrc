"""Перечисления протокола SkyRC."""

from enum import IntEnum


class Port(IntEnum):
    A = 0x01
    B = 0x02
    C = 0x04
    D = 0x08

    @classmethod
    def from_name(cls, name: str) -> "Port":
        try:
            return cls[name.upper()]
        except KeyError as exc:
            raise ValueError(f"unknown port: {name!r}") from exc


class Chemistry(IntEnum):
    LiPo = 0x00
    LiIo = 0x01
    LiFe = 0x02
    LiHV = 0x03
    NiMH = 0x04
    NiCd = 0x05
    Pb = 0x06


class LiMode(IntEnum):
    BALANCE_CHARGE = 0x00
    CHARGE = 0x01
    DISCHARGE = 0x02
    STORAGE = 0x03


class NiMode(IntEnum):
    CHARGE = 0x00
    DISCHARGE = 0x02
    RE_PEAK = 0x03
    CYCLE = 0x04


class PbMode(IntEnum):
    NORMAL = 0x00
    DISCHARGE = 0x01
    AGM = 0x02
    COLD_CHARGE = 0x03


class CycleDirection(IntEnum):
    CHARGE_DISCHARGE = 0x00
    DISCHARGE_CHARGE = 0x01


class State(IntEnum):
    OFF = 0x00
    CHARGING = 0x01
    IDLE = 0x02
    UNKNOWN = 0x03
    STARTING = 0x04

    @classmethod
    def name_of(cls, value: int) -> str:
        try:
            return cls(value).name.lower()
        except ValueError:
            return f"unknown(0x{value:02x})"
