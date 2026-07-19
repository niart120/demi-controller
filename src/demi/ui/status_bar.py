"""Qt status bar that renders application state as explicit text."""

from dataclasses import dataclass

from PySide6.QtWidgets import QLabel, QStatusBar, QWidget

from demi.application.state import AppState, ConnectionState
from demi.input.relative_pointer import RelativePointerQuality


@dataclass(frozen=True, slots=True)
class StatusBarState:
    """Describe the values rendered in the main status bar.

    Attributes:
        adapter_label: Safe label for the selected adapter.
        connection_state: Current connection lifecycle state.
        application_state: Current capture and lifecycle state.
        pointer_quality: Provenance of relative pointer values.
        preview_only: Whether frames are displayed without runtime output.
        warning: Current safe warning, if any.
        error: Current safe error, if any.
    """

    adapter_label: str
    connection_state: ConnectionState
    application_state: AppState
    pointer_quality: RelativePointerQuality
    preview_only: bool
    warning: str
    error: str | None


class MainStatusBar(QStatusBar):
    """Render independent application status categories with Qt labels."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create a status bar with permanently visible text fields.

        Args:
            parent: Optional Qt parent for the status bar.
        """
        super().__init__(parent)
        self.adapter_label = QLabel(self)
        self.connection_label = QLabel(self)
        self.capture_label = QLabel(self)
        self.pointer_label = QLabel(self)
        self.preview_label = QLabel(self)
        self.notice_label = QLabel(self)
        self.addWidget(self.connection_label)
        self.addWidget(self.notice_label, 1)
        for label in (
            self.adapter_label,
            self.capture_label,
            self.pointer_label,
            self.preview_label,
        ):
            self.addPermanentWidget(label)

    def refresh(self, state: StatusBarState) -> None:
        """Render state using text that does not depend on color.

        Args:
            state: Main-thread state snapshot for the status bar.
        """
        self.adapter_label.setText(
            self.tr("Adapter: {adapter}").format(adapter=self.tr(state.adapter_label))
        )
        self.connection_label.setText(
            self.tr("Connection: {state}").format(
                state=self.tr(_connection_text(state.connection_state))
            )
        )
        self.capture_label.setText(
            self.tr("Mouse capture: {state}").format(
                state=self.tr(_capture_text(state.application_state))
            )
        )
        self.pointer_label.setText(
            self.tr("Pointer: {quality}").format(
                quality=self.tr(_pointer_text(state.pointer_quality))
            )
        )
        self.preview_label.setText(
            self.tr("Preview: only") if state.preview_only else self.tr("Preview: transmitting")
        )
        if state.error is not None:
            self.notice_label.setText(
                self.tr("Error: {message}").format(message=self.tr(state.error))
            )
        elif state.warning:
            self.notice_label.setText(
                self.tr("Warning: {message}").format(message=self.tr(state.warning))
            )
        else:
            self.notice_label.setText(self.tr("Notice: none"))


def _connection_text(state: ConnectionState) -> str:
    return {
        ConnectionState.STOPPED: "Stopped",
        ConnectionState.STARTING: "Starting",
        ConnectionState.READY: "Ready",
        ConnectionState.DISCOVERING: "Discovering",
        ConnectionState.CONNECTING: "Connecting",
        ConnectionState.CONNECTED: "Connected",
        ConnectionState.DISCONNECTING: "Disconnecting",
        ConnectionState.ERROR: "Error",
        ConnectionState.STOPPING: "Stopping",
    }[state]


def _capture_text(state: AppState) -> str:
    return "On" if state is AppState.CAPTURED else "Off"


def _pointer_text(quality: RelativePointerQuality) -> str:
    return {
        RelativePointerQuality.RAW_UNACCELERATED: "Raw Input",
        RelativePointerQuality.RELATIVE_ACCELERATED: "OS accelerated",
        RelativePointerQuality.UNAVAILABLE: "Unavailable",
    }[quality]
