"""pyskyrc — pure-Python control for SkyRC Q200neo / T1000."""

from ._version import __version__
from .charger import ChargeParameters, SkyRCCharger
from .enums import (
    Chemistry,
    CycleDirection,
    LiMode,
    NiMode,
    PbMode,
    Port,
    State,
)
from .exceptions import (
    ChecksumError,
    DeviceIOError,
    DeviceNotFoundError,
    InvalidParameterError,
    NoAckError,
    ProtocolError,
    SkyRCError,
)
from .protocol import DeviceInfo
from .telemetry import ChargeEvent, EventKind, PortTelemetry

__all__ = [
    "__version__",
    "SkyRCCharger",
    "ChargeParameters",
    "Port",
    "Chemistry",
    "LiMode",
    "NiMode",
    "PbMode",
    "State",
    "CycleDirection",
    "DeviceInfo",
    "PortTelemetry",
    "ChargeEvent",
    "EventKind",
    "SkyRCError",
    "DeviceNotFoundError",
    "DeviceIOError",
    "ProtocolError",
    "InvalidParameterError",
    "NoAckError",
    "ChecksumError",
]