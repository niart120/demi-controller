"""Qt standard toolbar whose public actions follow application state."""

from dataclasses import dataclass

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QToolBar, QWidget

from demi.application.state import AppState, ConnectionState


@dataclass(frozen=True, slots=True)
class ToolbarState:
    """Describe the state that controls the main toolbar.

    Attributes:
        application_state: Current lifecycle and capture state.
        connection_state: Current connection lifecycle state.
        dialog_open: Whether one settings dialog currently owns interaction.
    """

    application_state: AppState
    connection_state: ConnectionState
    dialog_open: bool


class MainToolBar(QToolBar):
    """Expose standard Qt actions for the main application controls."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the toolbar with state-driven, initially disabled actions.

        Args:
            parent: Optional Qt parent for the toolbar.
        """
        super().__init__(parent)
        self.setObjectName("main-toolbar")
        self.connection_action = QAction("接続", self)
        self.capture_action = QAction("入力開始", self)
        self.capture_action.setCheckable(True)
        self.mapping_action = QAction("割り当て", self)
        self.connection_settings_action = QAction("接続設定", self)
        self.colors_action = QAction("色", self)
        for action in (
            self.connection_action,
            self.capture_action,
            self.mapping_action,
            self.connection_settings_action,
            self.colors_action,
        ):
            action.setEnabled(False)
            self.addAction(action)

    def refresh(self, state: ToolbarState) -> None:
        """Update action labels, check state, and enabled state.

        Args:
            state: Application state observed by the GUI main thread.
        """
        connection_state = state.connection_state
        application_state = state.application_state
        is_connected = connection_state is ConnectionState.CONNECTED
        is_captured = application_state is AppState.CAPTURED
        interaction_available = not state.dialog_open and application_state not in {
            AppState.SHUTTING_DOWN,
            AppState.STOPPED,
        }
        connection_available = interaction_available and connection_state in {
            ConnectionState.READY,
            ConnectionState.CONNECTED,
        }
        capture_available = interaction_available and application_state in {
            AppState.IDLE,
            AppState.CAPTURED,
        }

        self.connection_action.setText("切断" if is_connected else "接続")
        self.connection_action.setEnabled(connection_available)
        self.capture_action.setText("入力解除" if is_captured else "入力開始")
        self.capture_action.setChecked(is_captured)
        self.capture_action.setEnabled(capture_available)
        for action in (
            self.mapping_action,
            self.connection_settings_action,
            self.colors_action,
        ):
            action.setEnabled(interaction_available)
