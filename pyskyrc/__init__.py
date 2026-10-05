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
    "ChargeEvent",
    "ChargeParameters",
    "ChecksumError",
    "Chemistry",
    "CycleDirection",
    "DeviceIOError",
    "DeviceInfo",
    "DeviceNotFoundError",
    "EventKind",
    "InvalidParameterError",
    "LiMode",
    "NiMode",
    "NoAckError",
    "PbMode",
    "Port",
    "PortTelemetry",
    "ProtocolError",
    "SkyRCCharger",
    "SkyRCError",
    "State",
    "__version__",
]
