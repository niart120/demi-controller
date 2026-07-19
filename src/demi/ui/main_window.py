"""Minimal Qt main window used by the application shell."""

from __future__ import annotations

import sys
from collections.abc import Callable
from contextlib import suppress
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication, QDialog, QMainWindow, QWidget

from demi.application.state import AppState, ConnectionState
from demi.domain.errors import DomainValueError
from demi.domain.settings import WindowSettings
from demi.input.qt_adapter import QtInputAdapter
from demi.input.relative_pointer import (
    QtRelativePointerBackend,
    RelativePointerCapability,
    RelativePointerQuality,
)
from demi.platform.windows_mouse_hook import WindowsMouseInputSuppressor
from demi.platform.windows_raw_input import WindowsRawInputBackend
from demi.ui.controller_preview import ControllerPreviewWidget
from demi.ui.dialogs.connection import ConnectionDialog
from demi.ui.status_bar import MainStatusBar, StatusBarState
from demi.ui.toolbar import MainToolBar, ToolbarState

if TYPE_CHECKING:
    from PySide6.QtGui import QCloseEvent

    from demi.app import WindowSpec
    from demi.application.coordinator import CaptureCoordinator
    from demi.application.ui_state import ApplicationUiSnapshot
    from demi.domain.controller import ControllerFrame
    from demi.domain.settings import ControllerColorSettings
    from demi.input.publisher import InputPublisher


type ShutdownCallback = Callable[[WindowSettings | None], bool]
type RelativePointerBackend = WindowsRawInputBackend | QtRelativePointerBackend
type SettingsDialogFactory = Callable[[QWidget], QDialog | None]
type InputStateChangedCallback = Callable[[], object]


class MainWindow(QMainWindow):
    """Own the top-level Qt window and its minimum shell layout."""

    def __init__(self, spec: WindowSpec) -> None:
        """Create a resizable main window from validated saved dimensions.

        Args:
            spec: Requested dimensions and maximized state from settings.
        """
        super().__init__()
        self.setWindowTitle("Project_Demi")
        self.setMinimumSize(800, 520)
        self.resize(max(spec.width, self.minimumWidth()), max(spec.height, self.minimumHeight()))
        self._controller_preview = ControllerPreviewWidget(parent=self)
        self.setCentralWidget(self._controller_preview)
        self._main_toolbar = MainToolBar(self)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._main_toolbar)
        self._mapping_dialog_factory: SettingsDialogFactory | None = None
        self._connection_dialog_factory: SettingsDialogFactory | None = None
        self._colors_dialog_factory: SettingsDialogFactory | None = None
        self._active_settings_dialog: QDialog | None = None
        self._latest_snapshot: ApplicationUiSnapshot | None = None
        self._main_toolbar.mapping_action.triggered.connect(
            lambda _checked=False: self._open_settings_dialog(self._mapping_dialog_factory)
        )
        self._main_toolbar.connection_settings_action.triggered.connect(
            lambda _checked=False: self._open_settings_dialog(self._connection_dialog_factory)
        )
        self._main_toolbar.colors_action.triggered.connect(
            lambda _checked=False: self._open_settings_dialog(self._colors_dialog_factory)
        )
        self._status_bar = MainStatusBar(self)
        self.setStatusBar(self._status_bar)
        self._main_toolbar.refresh(
            ToolbarState(
                application_state=AppState.IDLE,
                connection_state=ConnectionState.STOPPED,
                dialog_open=False,
            )
        )
        self._status_bar.refresh(
            StatusBarState(
                adapter_label="None",
                connection_state=ConnectionState.STOPPED,
                application_state=AppState.IDLE,
                pointer_quality=RelativePointerQuality.UNAVAILABLE,
                preview_only=True,
                warning="",
                error=None,
            )
        )
        self.setMouseTracking(True)
        self._shutdown_callback: ShutdownCallback | None = None
        self._close_accepted = False
        self._shutdown_started = False
        self._input_application: QApplication | None = None
        self._input_adapter: QtInputAdapter | None = None
        self._input_state_changed_callback: InputStateChangedCallback | None = None
        self._native_input_filter: WindowsRawInputBackend | None = None
        self._mouse_input_suppressor: WindowsMouseInputSuppressor | None = None
        self._relative_pointer_backend: RelativePointerBackend | None = None
        self._input_coordinator: CaptureCoordinator | None = None
        self._input_evaluation_interval_ms: int | None = None
        self._input_evaluation_timer = QTimer(self)
        self._input_evaluation_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._input_evaluation_timer.timeout.connect(self._on_input_evaluation_timeout)
        self._last_frame: ControllerFrame | None = None
        self._quit_action = QAction(self)
        self._quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self._quit_action.triggered.connect(self.close)
        self.addAction(self._quit_action)
        if spec.maximized:
            self.showMaximized()

    @property
    def quit_action(self) -> QAction:
        """Return the standard Ctrl+Q action routed through closeEvent."""
        return self._quit_action

    def set_shutdown_callback(self, callback: ShutdownCallback) -> None:
        """Set the application-owned callback required before native close.

        Args:
            callback: Receives the state captured before the native window is
                destroyed and returns whether native close is safe.
        """
        self._shutdown_callback = callback

    def set_input_state_changed_callback(self, callback: InputStateChangedCallback | None) -> None:
        """Set the GUI refresh request invoked after an input-state transition.

        Args:
            callback: Refreshes the application snapshot after F12, focus, or
                dialog input changes; ``None`` disables the notification.
        """
        self._input_state_changed_callback = callback

    def begin_shutdown(self) -> None:
        """Stop UI-owned callbacks and close the active dialog once."""
        if self._shutdown_started:
            return
        self._shutdown_started = True
        self._remove_input_filters()
        dialog = self._active_settings_dialog
        self._active_settings_dialog = None
        if dialog is not None:
            dialog.blockSignals(True)
            dialog.done(int(QDialog.DialogCode.Rejected))

    def set_pointer_capture(self, enabled: bool) -> None:
        """Apply or release foreground pointer capture for controller input.

        Args:
            enabled: Whether the main window should own pointer capture.
        """
        if enabled:
            self.grabMouse()
            self.setCursor(Qt.CursorShape.BlankCursor)
            suppressor = self._mouse_input_suppressor
            try:
                if suppressor is not None:
                    suppressor.start()
            except OSError:
                self.releaseMouse()
                self.unsetCursor()
                raise
            return
        try:
            suppressor = self._mouse_input_suppressor
            if suppressor is not None:
                suppressor.stop()
        finally:
            self.releaseMouse()
            self.unsetCursor()

    @property
    def relative_pointer_capability(self) -> RelativePointerCapability:
        """Return the configured relative-pointer capability for UI presentation."""
        backend = self._relative_pointer_backend
        if backend is None:
            return RelativePointerCapability(RelativePointerQuality.UNAVAILABLE)
        return backend.capability

    @property
    def controller_preview(self) -> ControllerPreviewWidget:
        """Return the main-window-owned controller preview widget."""
        return self._controller_preview

    @property
    def main_toolbar(self) -> MainToolBar:
        """Return the standard toolbar owned by this main window."""
        return self._main_toolbar

    @property
    def status_bar(self) -> MainStatusBar:
        """Return the standard status bar owned by this main window."""
        return self._status_bar

    def refresh(self, snapshot: ApplicationUiSnapshot) -> None:
        """Render a framework-independent application snapshot.

        Args:
            snapshot: Main-thread state selected by the application layer.
        """
        if self._shutdown_started:
            return
        self._latest_snapshot = snapshot
        self._main_toolbar.refresh(
            ToolbarState(
                application_state=snapshot.application_state,
                connection_state=snapshot.connection_state,
                dialog_open=snapshot.dialog_open or self._active_settings_dialog is not None,
                connection_retryable=snapshot.connection_retryable,
            )
        )
        self._status_bar.refresh(
            StatusBarState(
                adapter_label=snapshot.adapter_label,
                connection_state=snapshot.connection_state,
                application_state=snapshot.application_state,
                pointer_quality=self.relative_pointer_capability.quality,
                preview_only=snapshot.preview_only,
                warning=snapshot.warning,
                error=snapshot.error,
            )
        )
        self._refresh_connection_dialog(snapshot)

    @property
    def active_settings_dialog(self) -> QDialog | None:
        """Return the non-blocking settings dialog currently owned by the window."""
        return self._active_settings_dialog

    def bind_settings_dialog_factories(
        self,
        *,
        mapping: SettingsDialogFactory,
        connection: SettingsDialogFactory,
        colors: SettingsDialogFactory,
    ) -> None:
        """Bind application-owned factories for the three editable dialogs.

        Args:
            mapping: Creates a mapping dialog for this main window.
            connection: Creates a connection settings dialog for this main window.
            colors: Creates a controller-colors dialog for this main window.
        """
        self._mapping_dialog_factory = mapping
        self._connection_dialog_factory = connection
        self._colors_dialog_factory = colors

    def open_settings_dialog(self, factory: SettingsDialogFactory) -> None:
        """Open a dialog from an application-owned settings factory.

        Args:
            factory: Creates the dialog for the already-selected settings flow.
        """
        self._open_settings_dialog(factory)

    def replace_active_settings_dialog(self, factory: SettingsDialogFactory) -> bool:
        """Replace the active settings dialog without discarding its draft.

        Args:
            factory: Creates the dialog that supersedes the active dialog.

        Returns:
            Whether a replacement dialog was created and opened.
        """
        if self._shutdown_started:
            return False
        previous_dialog = self._active_settings_dialog
        if previous_dialog is None:
            return False
        dialog = factory(self)
        if dialog is None:
            return False
        previous_dialog.hide()
        self._activate_settings_dialog(dialog)
        previous_dialog.deleteLater()
        return True

    @property
    def input_evaluation_interval_ms(self) -> int | None:
        """Return the configured input evaluation interval, if input is ready."""
        return self._input_evaluation_interval_ms

    @property
    def input_evaluation_timer_type(self) -> Qt.TimerType:
        """Return the Qt timer type selected for scheduled input evaluation."""
        return self._input_evaluation_timer.timerType()

    @property
    def last_frame(self) -> ControllerFrame | None:
        """Return the latest evaluated frame received by the preview boundary."""
        return self._last_frame

    def configure_input(
        self,
        *,
        publisher: InputPublisher,
        coordinator: CaptureCoordinator,
        raw_input_backend: WindowsRawInputBackend | None = None,
        mouse_input_suppressor: WindowsMouseInputSuppressor | None = None,
    ) -> None:
        """Install the Qt and native input filters owned by this main window.

        Args:
            publisher: Receives normalized pointer movement for input evaluation.
            coordinator: Owns capture, neutralization, and failure transitions.
            raw_input_backend: Optional injectable Win32 backend for tests.
            mouse_input_suppressor: Optional injectable Windows mouse-delivery
                suppressor for tests.

        Raises:
            RuntimeError: If input was already configured or QApplication is absent.
        """
        if self._input_adapter is not None:
            raise RuntimeError
        application = QApplication.instance()
        if application is None:
            raise RuntimeError
        if not isinstance(application, QApplication):
            raise TypeError
        backend = raw_input_backend
        if backend is None and sys.platform == "win32":
            backend = WindowsRawInputBackend(
                on_relative_motion=publisher.state.add_mouse_motion,
                on_read_failure=coordinator.on_relative_input_read_failure,
            )
        if backend is None:
            self._relative_pointer_backend = QtRelativePointerBackend(
                on_relative_motion=lambda motion: publisher.state.add_mouse_motion(
                    motion.dx,
                    motion.dy,
                )
            )
        else:
            application.installNativeEventFilter(backend)
            self._native_input_filter = backend
            self._relative_pointer_backend = backend
        if mouse_input_suppressor is not None:
            self._mouse_input_suppressor = mouse_input_suppressor
        elif sys.platform == "win32":
            self._mouse_input_suppressor = WindowsMouseInputSuppressor(
                on_button_pressed=publisher.state.press_mouse_button,
                on_button_released=publisher.state.release_mouse_button,
            )
        self._input_coordinator = coordinator
        adapter = QtInputAdapter(
            state=publisher.state,
            is_captured=lambda: coordinator.is_captured,
            is_keyboard_active=lambda: coordinator.operational_input_active,
            on_stop_capture=self._stop_input_capture,
            on_focus_lost=self._handle_input_focus_loss,
            on_focus_gained=self._handle_input_focus_gain,
            on_dialog_opened=self._open_input_configuration,
            capture_epoch=lambda: coordinator.capture_epoch,
            on_relative_position=self._handle_relative_position,
            is_focus_event_target=lambda watched: watched is self,
        )
        application.installEventFilter(adapter)
        self._input_application = application
        self._input_adapter = adapter
        self._input_evaluation_interval_ms = publisher.evaluation_interval_ms
        self._input_evaluation_timer.setInterval(self._input_evaluation_interval_ms)
        self._input_evaluation_timer.start()

    def start_relative_pointer_capture(self, capture_epoch: int) -> None:
        """Start the selected relative-pointer backend for the main window."""
        backend = self._require_relative_pointer_backend()
        if isinstance(backend, WindowsRawInputBackend):
            backend.start_capture(int(self.winId()), capture_epoch=capture_epoch)
            return
        backend.start_relative_pointer_capture(capture_epoch)

    def stop_relative_pointer_capture(self) -> None:
        """Stop the selected relative-pointer backend if it was configured."""
        backend = self._relative_pointer_backend
        if backend is None:
            return
        if isinstance(backend, WindowsRawInputBackend):
            backend.stop_capture()
            return
        backend.stop_relative_pointer_capture()

    def on_dialog_opened(self) -> None:
        """Neutralize capture before a UI-owned modal dialog opens."""
        adapter = self._input_adapter
        if adapter is not None:
            adapter.on_dialog_opened()

    def evaluate_input(self) -> ControllerFrame:
        """Evaluate one scheduled input tick through the capture coordinator.

        Returns:
            The frame offered to runtime and preview from this single evaluation.

        Raises:
            RuntimeError: If the window input boundary is not configured.
        """
        coordinator = self._input_coordinator
        if coordinator is None:
            raise RuntimeError
        return coordinator.evaluate()

    def set_frame(self, frame: ControllerFrame) -> None:
        """Store one evaluated frame for the controller preview boundary.

        Args:
            frame: Complete immutable state from the shared input evaluation.
        """
        self._last_frame = frame
        self._controller_preview.set_frame(frame)

    def set_controller_colors(self, colors: ControllerColorSettings) -> None:
        """Update preview colors without changing the current controller frame.

        Args:
            colors: Four validated controller colors selected by the UI.
        """
        self._controller_preview.set_colors(colors)

    def window_state(self) -> WindowSettings | None:
        """Return a valid saved state without losing a maximized normal size."""
        size = self.normalGeometry().size() if self.isMaximized() else self.size()
        try:
            return WindowSettings(
                width=size.width(),
                height=size.height(),
                maximized=self.isMaximized(),
            )
        except DomainValueError:
            return None

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt override name.
        """Route native close and Ctrl+Q through one ordered callback."""
        if self._close_accepted:
            event.accept()
            return
        callback = self._shutdown_callback
        if callback is None:
            event.ignore()
            return
        if callback(self.window_state()):
            self._close_accepted = True
            self.begin_shutdown()
            event.accept()
            return
        event.ignore()

    def _handle_relative_position(self, x: float, y: float, capture_epoch: int) -> None:
        backend = self._relative_pointer_backend
        if isinstance(backend, QtRelativePointerBackend):
            backend.handle_position(x, y, capture_epoch=capture_epoch)

    def _stop_input_capture(self) -> None:
        self._run_input_transition(lambda coordinator: coordinator.stop_capture())

    def _handle_input_focus_loss(self) -> None:
        self._run_input_transition(lambda coordinator: coordinator.on_focus_lost())

    def _handle_input_focus_gain(self) -> None:
        self._run_input_transition(lambda coordinator: coordinator.on_focus_gained())

    def _open_input_configuration(self) -> None:
        self._run_input_transition(lambda coordinator: coordinator.open_configuration())

    def _run_input_transition(
        self,
        transition: Callable[[CaptureCoordinator], object],
    ) -> None:
        coordinator = self._input_coordinator
        if coordinator is None:
            return
        transition(coordinator)
        callback = self._input_state_changed_callback
        if callback is not None:
            callback()

    def _open_settings_dialog(self, factory: SettingsDialogFactory | None) -> None:
        if self._shutdown_started or factory is None or self._active_settings_dialog is not None:
            return
        dialog = factory(self)
        if dialog is None:
            return
        self._activate_settings_dialog(dialog)

    def _activate_settings_dialog(self, dialog: QDialog) -> None:
        """Show one application-owned settings dialog and track its lifetime."""
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self._active_settings_dialog = dialog
        snapshot = self._latest_snapshot
        if snapshot is not None:
            self._refresh_connection_dialog(snapshot)
        dialog.finished.connect(
            lambda _result, closed_dialog=dialog: self._clear_active_settings_dialog(closed_dialog)
        )
        dialog.open()

    def _clear_active_settings_dialog(self, dialog: QDialog) -> None:
        if self._active_settings_dialog is dialog:
            self._active_settings_dialog = None
            snapshot = self._latest_snapshot
            if snapshot is not None:
                self.refresh(snapshot)

    def _refresh_connection_dialog(self, snapshot: ApplicationUiSnapshot) -> None:
        dialog = self._active_settings_dialog
        if isinstance(dialog, ConnectionDialog):
            dialog.set_adapters(snapshot.adapters)

    def _on_input_evaluation_timeout(self) -> None:
        if not self._shutdown_started and self._input_coordinator is not None:
            self.evaluate_input()

    def _require_relative_pointer_backend(self) -> RelativePointerBackend:
        backend = self._relative_pointer_backend
        if backend is None:
            raise RuntimeError
        return backend

    def _remove_input_filters(self) -> None:
        suppressor = self._mouse_input_suppressor
        if suppressor is not None:
            with suppress(OSError):
                suppressor.stop()
        self._input_evaluation_timer.stop()
        self._input_evaluation_interval_ms = None
        self._input_coordinator = None
        application = self._input_application
        if application is None:
            return
        adapter = self._input_adapter
        if adapter is not None:
            application.removeEventFilter(adapter)
        native_input_filter = self._native_input_filter
        if native_input_filter is not None:
            application.removeNativeEventFilter(native_input_filter)
        self._input_application = None
        self._input_adapter = None
        self._native_input_filter = None
