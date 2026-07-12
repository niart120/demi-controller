"""Immutable commands sent to the controller runtime worker."""

from dataclasses import dataclass
from pathlib import Path

from demi.domain.settings import ControllerColorSettings


@dataclass(frozen=True, slots=True)
class DiscoverAdapters:
    """Request adapter discovery on the worker thread."""


@dataclass(frozen=True, slots=True)
class ConnectSaved:
    """Request a saved-bond connection without pairing."""

    adapter_id: str
    bond_path: Path
    timeout_seconds: float
    colors: ControllerColorSettings


@dataclass(frozen=True, slots=True)
class StartPairing:
    """Request an explicitly user-approved new pairing attempt."""

    adapter_id: str
    timeout_seconds: float
    colors: ControllerColorSettings


@dataclass(frozen=True, slots=True)
class Disconnect:
    """Request a neutralizing controller disconnect."""


@dataclass(frozen=True, slots=True)
class RecreateWithColors:
    """Request controller recreation with new colors."""

    colors: ControllerColorSettings


@dataclass(frozen=True, slots=True)
class RequestStatus:
    """Request an immediate runtime status event."""


@dataclass(frozen=True, slots=True)
class Shutdown:
    """Request ordered runtime shutdown."""


type ControllerCommand = (
    DiscoverAdapters
    | ConnectSaved
    | StartPairing
    | Disconnect
    | RecreateWithColors
    | RequestStatus
    | Shutdown
)
