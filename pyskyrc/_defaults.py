"""Дефолты по химиям."""

from dataclasses import dataclass

from .enums import Chemistry, LiMode, NiMode, PbMode


@dataclass(frozen=True, slots=True)
class ChemistryDefaults:
    mode: int
    cells: int
    charge_cutoff_mv: int
    discharge_cutoff_mv: int


DEFAULTS: dict[Chemistry, ChemistryDefaults] = {
    Chemistry.LiPo: ChemistryDefaults(int(LiMode.BALANCE_CHARGE), 6, 4200, 3000),
    Chemistry.LiIo: ChemistryDefaults(int(LiMode.BALANCE_CHARGE), 6, 4100, 3200),
    Chemistry.LiFe: ChemistryDefaults(int(LiMode.BALANCE_CHARGE), 2, 3650, 2600),
    Chemistry.LiHV: ChemistryDefaults(int(LiMode.BALANCE_CHARGE), 2, 4350, 3100),
    Chemistry.NiMH: ChemistryDefaults(int(NiMode.CHARGE),         4,    6,  900),
    Chemistry.NiCd: ChemistryDefaults(int(NiMode.CHARGE),         4,    6,  900),
    Chemistry.Pb:   ChemistryDefaults(int(PbMode.NORMAL),         6, 2400, 1800),
}
