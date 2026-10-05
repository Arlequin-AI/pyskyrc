"""
Разбор входящих кадров от зарядника.

Поддерживает оба формата:
  · USB HID — фиксированные 64-байтные кадры
  · BLE     — переменная длина (0f LEN payload CHK)

Формат 0f2255XX (per-port telemetry):

    offset  field
    ------  ----------------------------------------
      0..2  0f 22 55
        3   port selector
        4   state
        5   counter
      6..13 unknown
       14   temperature, °C
     15..16 zero
     17..28 6 × uint16 BE, cell mV
     29..34 unknown
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .enums import Port, State

MAX_CELL_SPREAD_MV = 200
MIN_CELL_MV        = 2500
MAX_CELL_MV        = 4500


# ============================================================================
#  Dataclasses
# ============================================================================

@dataclass(frozen=True, slots=True)
class PortTelemetry:
    """Снимок состояния одного порта."""

    port: Port
    state: State
    temperature_c: int
    cells_mv: tuple[int, ...]
    total_mv: int
    delta_mv: int

    @property
    def has_battery(self) -> bool:
        return bool(self.cells_mv)

    @property
    def total_v(self) -> float:
        return self.total_mv / 1000.0

    @property
    def cells_v(self) -> tuple[float, ...]:
        return tuple(v / 1000.0 for v in self.cells_mv)


class EventKind(Enum):
    START = "start"
    STOP = "stop"


@dataclass(frozen=True, slots=True)
class ChargeEvent:
    kind: EventKind
    port: Port


# ============================================================================
#  Helpers
# ============================================================================

def _is_valid_cells(cells: list[int]) -> bool:
    if len(cells) != 6:
        return False
    if not all(MIN_CELL_MV <= v <= MAX_CELL_MV for v in cells):
        return False
    return (max(cells) - min(cells)) <= MAX_CELL_SPREAD_MV


def _try_port(value: int) -> Port | None:
    try:
        return Port(value)
    except ValueError:
        return None


def _try_state(value: int) -> State:
    try:
        return State(value)
    except ValueError:
        return State.UNKNOWN


# ============================================================================
#  Parsers
# ============================================================================

def parse_telemetry(packet: bytes) -> PortTelemetry | None:
    """Разобрать 0f2255XX (per-port live telemetry)."""
    if len(packet) < 35:
        return None
    if packet[0] != 0x0F or packet[1] != 0x22 or packet[2] != 0x55:
        return None

    port = _try_port(packet[3])
    if port is None:
        return None

    cells = [
        (packet[17 + i * 2] << 8) | packet[17 + i * 2 + 1]
        for i in range(6)
    ]

    if _is_valid_cells(cells):
        total = sum(cells)
        delta = max(cells) - min(cells)
        cells_tuple: tuple[int, ...] = tuple(cells)
    else:
        total = 0
        delta = 0
        cells_tuple = ()

    return PortTelemetry(
        port=port,
        state=_try_state(packet[4]),
        temperature_c=packet[14],
        cells_mv=cells_tuple,
        total_mv=total,
        delta_mv=delta,
    )


def parse_event(packet: bytes) -> ChargeEvent | None:
    """Разобрать ACK: 0f0405XX = START, 0f04feXX = STOP."""
    if len(packet) < 4:
        return None
    if packet[0] != 0x0F or packet[1] != 0x04:
        return None

    port = _try_port(packet[3])
    if port is None:
        return None

    if packet[2] == 0x05:
        return ChargeEvent(EventKind.START, port)
    if packet[2] == 0xFE:
        return ChargeEvent(EventKind.STOP, port)
    return None


# ---- совместимость со старым кодом (dict-API) ----

def parse_2255(packet: bytes) -> dict | None:
    """Старый dict-API для обратной совместимости."""
    info = parse_telemetry(packet)
    if info is None:
        return None
    return {
        "port":      info.port.name,
        "state":     int(info.state),
        "state_str": info.state.name.lower(),
        "temp_c":    info.temperature_c,
        "cells_mv":  list(info.cells_mv) if info.cells_mv else [0] * 6,
        "real":      info.has_battery,
        "counter":   0,
    }
