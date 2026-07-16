"""Qt application lifecycle boundary."""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

from PySide6.QtCore import QCoreApplication, QEvent, QTimer
from PySide6.QtWidgets import QApplication

from demi.application.dialogs import DialogKind
from demi.application.state import ConnectionState
from demi.controller.events import RuntimeStopped
from demi.ui.dialogs.colors import ControllerColorsDialog
from demi.ui.dialogs.connection import ConnectionDialog, PairingConfirmationDialog
from demi.ui.dialogs.mapping import MappingDialog
from demi.ui.main_window import MainWindow

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from PySide6.QtWidgets import QWidget

    from demi.app import ApplicationSession, WindowPort, WindowSpec
    from demi.application.settings_editor import SettingsEditor
    from demi.controller.events import RuntimeEvent
    from demi.domain.settings import WindowSettings


class QtApplicationRunner:
    """Own one process-wide QApplication and its event-loop status."""

    def __init__(self, argv: Sequence[str] | None = None) -> None:
        """Create or reuse the process-wide Qt application.

        Args:
            argv: Arguments supplied to a newly created QApplication. The
                process arguments are used when omitted.
        """
        existing = QApplication.instance()
        self._application = (
            existing
            if isinstance(existing, QApplication)
            else QApplication(list(sys.argv if argv is None else argv))
        )
        self._window: MainWindow | None = None

    @property
    def application(self) -> QApplication:
        """Return the process-wide QApplication owned or reused by this runner."""
        return self._application

    def run(self) -> int:
        """Enter the Qt event loop and return its exit status."""
        window = self._window
        if window is None:
            raise RuntimeError
        window.show()
        close_after_ms = _test_auto_close_ms()
        if close_after_ms is not None:
            QTimer.singleShot(close_after_ms, window.close)
        try:
            return self._application.exec()
        finally:
            self._dispose_window(window)

    def _dispose_window(self, window: MainWindow) -> None:
        """Delete the runner-owned top-level window on the GUI thread."""
        if window.isVisible():
            window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(window, QEvent.Type.DeferredDelete)
        self._window = None

    def configure(
        self,
        *,
        window: WindowPort,
        on_shutdown_requested: Callable[[WindowSettings | None], bool],
    ) -> None:
        """Connect the application-owned shutdown callback to one window.

        Args:
            window: The sole top-level window owned by this runner.
            on_shutdown_requested: Ordered shutdown callback that decides
                whether native close may continue.
        """
        if not isinstance(window, MainWindow):
            raise TypeError
        self._window = window
        window.set_shutdown_callback(on_shutdown_requested)

    def create_main_window(self, spec: WindowSpec) -> MainWindow:
        """Create the process main window after QApplication exists.

        Args:
            spec: Validated saved dimensions selected by the application layer.
        """
        return MainWindow(spec)


def _test_auto_close_ms() -> int | None:
    """Return the opted-in process-test close delay, if it is valid."""
    value = os.environ.get("DEMI_QT_TEST_CLOSE_AFTER_MS")
    if value is None:
        return None
    try:
        milliseconds = int(value)
    except ValueError:
        return None
    return milliseconds if milliseconds >= 0 else None


class QtApplicationEventRouter:
    """Apply queued runtime events to one session and its main window."""

    def __init__(self, window: MainWindow) -> None:
        """Create an unbound GUI-thread event receiver.

        Args:
            window: Main window updated after each reduced runtime event.
        """
        self._window = window
        self._session: ApplicationSession | None = None
        self._runtime_stopped_handler: Callable[[], object] | None = None
        self._active = True

    def bind(self, session: ApplicationSession) -> None:
        """Bind the assembled application session and render its current state.

        Args:
            session: Main-thread application state that receives runtime events.
        """
        if not self._active:
            return
        self._session = session
        self._window.set_input_state_changed_callback(self.refresh)
        self._window.main_toolbar.set_connection_shortcuts(
            session.settings.local_actions.connection
        )
        self._window.main_toolbar.bind_connection_action(self._run_connection_action)
        self._window.main_toolbar.bind_capture_action(self._toggle_capture)
        self._window.bind_settings_dialog_factories(
            mapping=self._create_mapping_dialog,
            connection=self._create_connection_dialog,
            colors=self._create_colors_dialog,
        )
        self.refresh()

    def deactivate(self) -> None:
        """Drop queued runtime callbacks after application shutdown begins."""
        self._active = False
        self._window.set_input_state_changed_callback(None)
        self._session = None
        self._runtime_stopped_handler = None

    def set_runtime_stopped_handler(self, handler: Callable[[], object] | None) -> None:
        """Set the application-owned completion callback for RuntimeStopped.

        Args:
            handler: Callback that completes application shutdown after the
                session has rendered a runtime-stopped snapshot, or ``None``
                to leave the router passive.
        """
        if self._active:
            self._runtime_stopped_handler = handler

    def handle_runtime_event(self, event: RuntimeEvent) -> None:
        """Reduce one bridge-delivered event and refresh the main window.

        Args:
            event: Immutable runtime event delivered on the GUI thread.
        """
        if not self._active:
            return
        session = self._session
        if session is None:
            return
        session.handle_runtime_event(event)
        self.refresh()
        if isinstance(event, RuntimeStopped):
            handler = self._runtime_stopped_handler
            if handler is not None:
                handler()

    def refresh(self) -> None:
        """Render the current session snapshot when a session is bound."""
        if not self._active:
            return
        session = self._session
        if session is not None:
            self._window.refresh(session.ui_snapshot)

    def _run_connection_action(self) -> None:
        """Run one state-dependent connection action and refresh the window."""
        session = self._session
        if session is not None:
            session.connection_action()
            if (
                session.dialogs.model.kind is DialogKind.CONNECTION
                and self._window.active_settings_dialog is None
            ):
                self._window.open_settings_dialog(self._create_connection_dialog)
            self.refresh()

    def _toggle_capture(self) -> None:
        """Toggle input capture through the session and refresh the window."""
        session = self._session
        if session is not None:
            session.toggle_capture()
            self.refresh()

    def _open_settings_editor(self, kind: DialogKind) -> SettingsEditor | None:
        """Open one session-owned draft and return its editor for a Qt dialog."""
        session = self._session
        if session is None or not session.open_settings(kind):
            return None
        editor = session.settings_modal.editor
        if editor is None:
            session.cancel_settings()
            self.refresh()
            return None
        self.refresh()
        return editor

    def _create_mapping_dialog(self, parent: QWidget) -> MappingDialog | None:
        """Create the mapping dialog after opening its application-owned draft."""
        editor = self._open_settings_editor(DialogKind.MAPPING)
        if editor is None:
            return None
        return MappingDialog(
            editor,
            on_dialog_opened=self._window.on_dialog_opened,
            on_save=self._save_settings,
            on_cancel=self._cancel_settings,
            parent=parent,
        )

    def _create_connection_dialog(self, parent: QWidget) -> ConnectionDialog | None:
        """Create the connection dialog after opening its application-owned draft."""
        session = self._session
        if session is None:
            return None
        editor = (
            session.settings_modal.editor
            if session.dialogs.model.kind is DialogKind.CONNECTION
            else self._open_settings_editor(DialogKind.CONNECTION)
        )
        if editor is None:
            return None
        return self._connection_dialog(editor, parent)

    def _connection_dialog(self, editor: SettingsEditor, parent: QWidget) -> ConnectionDialog:
        """Create one connection editor from an already-open session draft."""
        return ConnectionDialog(
            editor,
            on_rescan=self._rescan_adapters,
            on_request_pairing=self._request_pairing,
            on_save_and_connect=self._save_connection_and_connect,
            on_cancel=self._cancel_settings,
            parent=parent,
        )

    def _create_colors_dialog(self, parent: QWidget) -> ControllerColorsDialog | None:
        """Create the colors dialog after opening its application-owned draft."""
        session = self._session
        if session is None:
            return None
        connected = session.ui_snapshot.connection_state is ConnectionState.CONNECTED
        editor = self._open_settings_editor(DialogKind.COLORS)
        if editor is None:
            return None
        return ControllerColorsDialog(
            editor,
            connected=connected,
            on_preview=self._window.set_controller_colors,
            on_save=self._save_settings,
            on_cancel=self._cancel_settings,
            on_defer_reconnect=self._defer_color_reconnect,
            on_reconnect=self._request_color_reconnect,
            parent=parent,
        )

    def _save_settings(self) -> bool:
        """Save the active settings draft and render its updated session snapshot."""
        session = self._session
        if session is None:
            return False
        saved = session.save_settings()
        self.refresh()
        return saved

    def _cancel_settings(self) -> bool:
        """Cancel the active settings draft and render its updated session snapshot."""
        session = self._session
        if session is None:
            return False
        cancelled = session.cancel_settings()
        self.refresh()
        return cancelled

    def _rescan_adapters(self) -> None:
        """Request adapter discovery through the application session."""
        session = self._session
        if session is not None:
            session.rescan_adapters()
            self.refresh()

    def _save_connection_and_connect(self) -> bool:
        """Persist a connection draft and request the existing connect action."""
        if not self._save_settings():
            return False
        session = self._session
        if session is not None:
            session.connection_action()
            self.refresh()
        return True

    def _request_pairing(self) -> bool:
        """Replace an editable connection dialog with pairing confirmation."""
        session = self._session
        if session is None or not session.request_pairing():
            return False
        if self._window.replace_active_settings_dialog(self._create_pairing_confirmation):
            self.refresh()
            return True
        session.cancel_pairing()
        self.refresh()
        return False

    def _create_pairing_confirmation(self, parent: QWidget) -> PairingConfirmationDialog:
        """Create the confirmation dialog for the active connection draft."""
        return PairingConfirmationDialog(
            on_confirm=self._confirm_pairing,
            on_cancel=self._cancel_pairing,
            parent=parent,
        )

    def _confirm_pairing(self) -> bool:
        """Confirm pairing through the application session and refresh the window."""
        session = self._session
        if session is None:
            return False
        confirmed = session.confirm_pairing()
        self.refresh()
        return confirmed

    def _cancel_pairing(self) -> None:
        """Return a pairing confirmation to its editable connection dialog."""
        session = self._session
        if session is None or not session.cancel_pairing():
            return
        editor = session.settings_modal.editor
        if editor is None:
            self.refresh()
            return
        self._window.replace_active_settings_dialog(
            lambda parent: self._connection_dialog(editor, parent)
        )
        self.refresh()

    def _defer_color_reconnect(self) -> None:
        """Keep saved colors without recreating the connected controller."""
        session = self._session
        if session is not None:
            session.defer_color_reconnect()
            self.refresh()

    def _request_color_reconnect(self) -> None:
        """Request an immediate reconnect after saved colors changed."""
        session = self._session
        if session is not None:
            session.request_color_reconnect()
            self.refresh()
