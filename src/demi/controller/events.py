"""Immutable events emitted by the controller runtime worker."""

from dataclasses import dataclass
from enum import StrEnum

from demi.application.state import ConnectionState
from demi.domain.controller import ControllerFrame


@dataclass(frozen=True, slots=True)
class AdapterDescriptor:
    """Safe adapter identity and display metadata."""

    id: str
    display_name: str
    transport: str
    metadata: tuple[tuple[str, str], ...] = ()


class ControllerErrorCategory(StrEnum):
    """Classified controller failures shown to the UI."""

    ADAPTER_NOT_FOUND = "ADAPTER_NOT_FOUND"
    ADAPTER_OPEN_FAILED = "ADAPTER_OPEN_FAILED"
    BOND_NOT_FOUND = "BOND_NOT_FOUND"
    PAIRING_PROFILE_EXISTS = "PAIRING_PROFILE_EXISTS"
    PAIRING_TIMEOUT = "PAIRING_TIMEOUT"
    RECONNECT_FAILED = "RECONNECT_FAILED"
    CONNECTION_LOST = "CONNECTION_LOST"
    INVALID_INPUT = "INVALID_INPUT"
    SHUTDOWN_FAILED = "SHUTDOWN_FAILED"
    UNEXPECTED = "UNEXPECTED"


@dataclass(frozen=True, slots=True)
class AdaptersDiscovered:
    """Report the adapter descriptors returned by the worker."""

    adapters: tuple[AdapterDescriptor, ...]


@dataclass(frozen=True, slots=True)
class ConnectionChanged:
    """Report a connection state transition."""

    state: ConnectionState
    adapter_id: str | None = None
    summary: str = ""


@dataclass(frozen=True, slots=True)
class PairingProgress:
    """Report user-visible progress for a pairing operation."""

    summary: str
    completed: bool = False


@dataclass(frozen=True, slots=True)
class StatusSnapshot:
    """Report runtime status without exposing adapter internals."""

    connection_state: ConnectionState
    latest_frame: ControllerFrame | None
    watchdog_tripped: bool


@dataclass(frozen=True, slots=True)
class WatchdogNeutralized:
    """Report that the worker applied a watchdog rest state."""

    capture_epoch: int


@dataclass(frozen=True, slots=True)
class ControllerError:
    """Report a classified, user-safe controller failure."""

    category: ControllerErrorCategory
    summary: str
    retryable: bool
    diagnostic_id: str


@dataclass(frozen=True, slots=True)
class RuntimeStopped:
    """Report that the worker loop and adapter have stopped."""


type RuntimeEvent = (
    AdaptersDiscovered
    | ConnectionChanged
    | PairingProgress
    | StatusSnapshot
    | WatchdogNeutralized
    | ControllerError
    | RuntimeStopped
)
