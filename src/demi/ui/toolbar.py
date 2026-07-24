"""Qt standard toolbar whose public actions follow application state."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QLabel, QMenu, QToolBar, QToolButton, QWidget

from demi.application.state import AppState, ConnectionState


@dataclass(frozen=True, slots=True)
class ToolbarState:
    """Describe the state that controls the main toolbar.

    Attributes:
        application_state: Current lifecycle and capture state.
        connection_state: Current connection lifecycle state.
        dialog_open: Whether one settings dialog currently owns interaction.
        connection_retryable: Whether an error-state connection action is safe.
    """

    application_state: AppState
    connection_state: ConnectionState
    dialog_open: bool
    connection_retryable: bool = True


class MainToolBar(QToolBar):
    """Expose standard Qt actions for the main application controls."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the toolbar with state-driven, initially disabled actions.

        Args:
            parent: Optional Qt parent for the toolbar.
        """
        super().__init__(parent)
        self.setObjectName("main-toolbar")
        self.setMovable(False)
        self.setFloatable(False)
        self.connection_action = QAction(self.tr("Connect"), self)
        self.mouse_input_status = QLabel(self)
        self.mouse_input_status.setObjectName("mouse-input-status")
        self.mouse_input_status.setMinimumWidth(132)
        self.connection_settings_action = QAction(self.tr("Connection"), self)
        self.bindings_action = QAction(self.tr("Bindings"), self)
        self.mouse_action = QAction(self.tr("Mouse"), self)
        self.colors_action = QAction(self.tr("Colors"), self)
        self.settings_menu = QMenu(self)
        self.settings_menu.addActions(
            (
                self.connection_settings_action,
                self.bindings_action,
                self.mouse_action,
                self.colors_action,
            )
        )
        self.settings_button = QToolButton(self)
        self.settings_button.setText(self.tr("Settings"))
        self.settings_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.settings_button.setMenu(self.settings_menu)
        self.settings_button.setEnabled(False)
        for action in (self.connection_action,):
            action.setEnabled(False)
            self.addAction(action)
        self.mouse_input_status_action = self.addWidget(self.mouse_input_status)
        for action in self.settings_menu.actions():
            action.setEnabled(False)
        self.settings_action = self.addWidget(self.settings_button)
        self.settings_action.setEnabled(False)

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
        connection_available = interaction_available and (
            connection_state in {ConnectionState.READY, ConnectionState.CONNECTED}
            or (connection_state is ConnectionState.ERROR and state.connection_retryable)
        )

        self.connection_action.setText(
            self.tr("Disconnect") if is_connected else self.tr("Connect")
        )
        self.connection_action.setEnabled(connection_available)
        mouse_state = (
            self.tr("Mouse input: ON (F5)") if is_captured else self.tr("Mouse input: OFF (F5)")
        )
        mouse_color = "#176B3A" if is_captured else "#7A1F1F"
        self.mouse_input_status.setText(mouse_state)
        self.mouse_input_status.setStyleSheet(
            f"background: {mouse_color}; color: white; font-weight: bold; "
            "padding: 4px 8px; border-radius: 3px;"
        )
        self.mouse_input_status.setAccessibleName(mouse_state)
        self.mouse_input_status.setEnabled(interaction_available)
        self.mouse_input_status_action.setEnabled(interaction_available)
        for action in (
            self.connection_settings_action,
            self.bindings_action,
            self.mouse_action,
            self.colors_action,
        ):
            action.setEnabled(interaction_available)
        self.settings_button.setEnabled(interaction_available)
        self.settings_action.setEnabled(interaction_available)

    def bind_connection_action(self, callback: Callable[[], object]) -> None:
        """Route enabled connection action requests to the application layer.

        Args:
            callback: Semantic connect-or-disconnect request owned by the
                application layer.
        """
        self.connection_action.triggered.connect(lambda _checked=False: callback())

    def set_connection_shortcuts(self, shortcuts: Sequence[str]) -> None:
        """Assign configured window shortcuts to the connection action.

        Args:
            shortcuts: Portable Qt key sequence strings owned by local actions.
        """
        self.connection_action.setShortcuts([QKeySequence(shortcut) for shortcut in shortcuts])
