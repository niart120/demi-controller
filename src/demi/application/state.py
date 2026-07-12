"""Application and connection states used by the main-thread UI."""

from enum import StrEnum


class AppState(StrEnum):
    """Lifecycle states owned by the application coordinator."""

    STARTING = "starting"
    IDLE = "idle"
    CAPTURED = "captured"
    CONFIGURING = "configuring"
    SUSPENDED = "suspended"
    SHUTTING_DOWN = "shutting_down"
    STOPPED = "stopped"


class ConnectionState(StrEnum):
    """Connection states shown by the toolbar and status bar."""

    STOPPED = "stopped"
    STARTING = "starting"
    READY = "ready"
    DISCOVERING = "discovering"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    ERROR = "error"
    STOPPING = "stopping"
