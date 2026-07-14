"""Framework-independent state exposed by the application to the desktop UI."""

from dataclasses import dataclass

from demi.application.presentation import AdapterOption
from demi.application.state import AppState, ConnectionState


@dataclass(frozen=True, slots=True)
class ApplicationUiSnapshot:
    """Describe the current desktop UI state without Qt-specific values.

    Attributes:
        application_state: Capture and application lifecycle state.
        connection_state: Current controller connection lifecycle state.
        adapter_label: Safe label for the selected adapter.
        adapters: Safe discovered adapter choices for connection controls.
        dialog_open: Whether an application-owned settings dialog is active.
        preview_only: Whether frames are displayed without controller output.
        warning: Current safe warning text.
        error: Current safe error text, if any.
        color_reconnect_pending: Whether the user must choose a color reconnect.
    """

    application_state: AppState
    connection_state: ConnectionState
    adapter_label: str
    adapters: tuple[AdapterOption, ...]
    dialog_open: bool
    preview_only: bool
    warning: str
    error: str | None
    color_reconnect_pending: bool
