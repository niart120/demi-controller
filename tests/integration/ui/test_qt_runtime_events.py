from dataclasses import dataclass, field, replace
from pathlib import Path
from threading import Thread, get_ident

import pytest
from PySide6.QtCore import QCoreApplication, QObject, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QWidget

from demi.app import ApplicationSession, SystemClock, WindowSpec
from demi.application.coordinator import CaptureCoordinator
from demi.application.dialogs import DialogKind
from demi.application.state import AppState, ConnectionState
from demi.application.ui_state import ApplicationUiSnapshot
from demi.config.paths import SettingsPaths
from demi.config.repository import SettingsLoadResult, SettingsLoadStatus
from demi.controller.commands import (
    ConnectSaved,
    ControllerCommand,
    Disconnect,
    DiscoverAdapters,
    RecreateWithColors,
)
from demi.controller.events import (
    AdapterDescriptor,
    AdaptersDiscovered,
    ConnectionChanged,
    ControllerError,
    ControllerErrorCategory,
    PairingProgress,
    RuntimeEvent,
    RuntimeStopped,
    StatusSnapshot,
    WatchdogNeutralized,
)
from demi.domain.controller import ControllerFrame
from demi.domain.settings import AppSettings
from demi.input.publisher import InputPublisher
from demi.platform.windows_mouse_hook import WindowsMouseInputSuppressor
from demi.ui.application import QtApplicationEventRouter
from demi.ui.dialogs.colors import ControllerColorsDialog
from demi.ui.dialogs.connection import ConnectionDialog, PairingConfirmationDialog
from demi.ui.dialogs.mapping import MappingDialog
from demi.ui.event_bridge import QtRuntimeEventBridge
from demi.ui.main_window import MainWindow


class _PresentationReceiver:
    def __init__(self) -> None:
        self.adapter_labels: tuple[str, ...] = ()
        self.delivery_thread: int | None = None

    def handle_runtime_event(self, event: RuntimeEvent) -> None:
        assert isinstance(event, AdaptersDiscovered)
        self.adapter_labels = tuple(adapter.display_name for adapter in event.adapters)
        self.delivery_thread = get_ident()


class _RecordingApplicationSession:
    def __init__(self) -> None:
        self.events: list[RuntimeEvent] = []

    def handle_runtime_event(self, event: RuntimeEvent) -> None:
        self.events.append(event)


@dataclass
class _Runtime:
    """Runtime fake that records frames and commands without a worker loop."""

    commands: list[ControllerCommand] = field(default_factory=list)
    frames: list[ControllerFrame] = field(default_factory=list)

    def start(self) -> None:
        """Satisfy the application runtime boundary."""

    def post(self, command: ControllerCommand) -> None:
        """Record one main-thread runtime command."""
        self.commands.append(command)

    def offer_frame(self, frame: ControllerFrame) -> bool:
        """Record one neutral or active controller frame."""
        self.frames.append(frame)
        return True

    def close(self) -> None:
        """Satisfy the application runtime boundary."""


@dataclass
class _Repository:
    """Settings fake used only to assemble an application session."""

    result: SettingsLoadResult

    def load(self) -> SettingsLoadResult:
        """Return the configured settings result."""
        return self.result

    def save(self, settings: AppSettings) -> None:
        """Accept a validated settings snapshot."""
        del settings


@dataclass
class _PointerCapture:
    """Capture boundary that records foreground ownership changes."""

    enabled: list[bool] = field(default_factory=list)

    def set_pointer_capture(self, enabled: bool) -> None:
        """Record the requested capture state."""
        self.enabled.append(enabled)


@dataclass
class _MouseHookRegistrar:
    """Provide a no-op low-level hook boundary for GUI route tests."""

    handles: list[int] = field(default_factory=list)

    def install(self, callback: object) -> int:
        """Record an installed callback without touching desktop input."""
        del callback
        handle = len(self.handles) + 1
        self.handles.append(handle)
        return handle

    def remove(self, handle: int) -> None:
        """Record removal by dropping the supplied hook handle."""
        self.handles.remove(handle)


class _RecordingMainWindow(MainWindow):
    """Main window that records every widget refresh thread."""

    def __init__(self, spec: WindowSpec) -> None:
        self.refresh_threads: list[int] = []
        super().__init__(spec)

    def refresh(self, snapshot: ApplicationUiSnapshot) -> None:
        """Record the GUI thread before applying the standard refresh."""
        self.refresh_threads.append(get_ident())
        super().refresh(snapshot)


def test_f12_capture_release_refreshes_the_bound_toolbar(
    qt_application: QApplication,
) -> None:
    """Keep F12 capture release consistent with the toolbar action state."""
    settings = AppSettings.default()
    runtime = _Runtime()
    window = MainWindow(WindowSpec(width=960, height=640, maximized=False))
    coordinator = CaptureCoordinator(
        publisher=InputPublisher(clock=SystemClock(), sink=runtime),
        pointer_capture=window,
    )
    session = ApplicationSession(
        settings=settings,
        paths=SettingsPaths(Path("config"), Path("data"), Path("log")),
        repository=_Repository(SettingsLoadResult(settings, SettingsLoadStatus.FIRST_RUN)),
        runtime=runtime,
        coordinator=coordinator,
    )
    router = QtApplicationEventRouter(window)
    router.bind(session)
    window.configure_input(
        publisher=coordinator.publisher,
        coordinator=coordinator,
        mouse_input_suppressor=WindowsMouseInputSuppressor(registrar=_MouseHookRegistrar()),
    )

    window.main_toolbar.capture_action.trigger()
    assert coordinator.app_state is AppState.CAPTURED
    assert window.main_toolbar.capture_action.text() == "入力解除"
    assert window.main_toolbar.capture_action.isChecked()

    QCoreApplication.sendEvent(
        window,
        QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_F12, Qt.KeyboardModifier.NoModifier),
    )
    qt_application.processEvents()

    assert coordinator.app_state is AppState.IDLE
    assert window.main_toolbar.capture_action.text() == "入力開始"
    assert not window.main_toolbar.capture_action.isChecked()


@pytest.mark.parametrize(
    ("action_name", "dialog_type", "dialog_kind"),
    [
        ("mapping_action", MappingDialog, DialogKind.MAPPING),
        ("connection_settings_action", ConnectionDialog, DialogKind.CONNECTION),
        ("colors_action", ControllerColorsDialog, DialogKind.COLORS),
    ],
)
def test_router_binds_each_settings_action_to_a_session_owned_dialog(
    qt_application: QApplication,
    action_name: str,
    dialog_type: type[MappingDialog | ConnectionDialog | ControllerColorsDialog],
    dialog_kind: DialogKind,
) -> None:
    """Drive the normal GUI router path used by production composition."""
    settings = AppSettings.default()
    runtime = _Runtime()
    coordinator = CaptureCoordinator(
        publisher=InputPublisher(clock=SystemClock(), sink=runtime),
        pointer_capture=_PointerCapture(),
    )
    session = ApplicationSession(
        settings=settings,
        paths=SettingsPaths(Path("config"), Path("data"), Path("log")),
        repository=_Repository(SettingsLoadResult(settings, SettingsLoadStatus.FIRST_RUN)),
        runtime=runtime,
        coordinator=coordinator,
    )
    window = MainWindow(WindowSpec(width=960, height=640, maximized=False))
    router = QtApplicationEventRouter(window)
    router.bind(session)

    action = getattr(window.main_toolbar, action_name)
    action.trigger()
    qt_application.processEvents()

    dialog = window.active_settings_dialog
    assert isinstance(dialog, dialog_type)
    assert dialog.isVisible()
    assert dialog.parentWidget() is window
    assert session.dialogs.model.kind is dialog_kind
    assert session.settings_modal.editor is not None

    dialog.reject()
    qt_application.processEvents()

    assert window.active_settings_dialog is None
    assert session.dialogs.model.kind is DialogKind.NONE
    assert session.settings_modal.editor is None
    assert action.isEnabled()


def test_router_routes_connection_dialog_actions_through_the_application_session(
    qt_application: QApplication,
) -> None:
    """Keep connection discovery, pairing, and saved connect outside widgets."""
    settings = AppSettings.default()
    runtime = _Runtime()
    coordinator = CaptureCoordinator(
        publisher=InputPublisher(clock=SystemClock(), sink=runtime),
        pointer_capture=_PointerCapture(),
    )
    session = ApplicationSession(
        settings=settings,
        paths=SettingsPaths(Path("config"), Path("data"), Path("log")),
        repository=_Repository(SettingsLoadResult(settings, SettingsLoadStatus.FIRST_RUN)),
        runtime=runtime,
        coordinator=coordinator,
    )
    window = MainWindow(WindowSpec(width=960, height=640, maximized=False))
    router = QtApplicationEventRouter(window)
    router.bind(session)
    adapters = (AdapterDescriptor("usb:0", "Test Adapter", "usb"),)
    router.handle_runtime_event(AdaptersDiscovered(adapters))
    router.handle_runtime_event(ConnectionChanged(ConnectionState.READY))

    window.main_toolbar.connection_settings_action.trigger()
    qt_application.processEvents()
    dialog = window.active_settings_dialog
    assert isinstance(dialog, ConnectionDialog)
    dialog.select_adapter(0)

    dialog.request_rescan()
    assert runtime.commands == [DiscoverAdapters()]
    router.handle_runtime_event(AdaptersDiscovered(adapters))
    assert dialog.rescan_button.isEnabled()

    dialog.request_pairing()
    qt_application.processEvents()
    confirmation = window.active_settings_dialog
    assert isinstance(confirmation, PairingConfirmationDialog)
    assert session.dialogs.model.kind is DialogKind.PAIRING_CONFIRMATION

    confirmation.reject()
    qt_application.processEvents()
    restored_dialog = window.active_settings_dialog
    assert isinstance(restored_dialog, ConnectionDialog)
    assert session.dialogs.model.kind is DialogKind.CONNECTION

    restored_dialog.request_connect()
    qt_application.processEvents()

    assert window.active_settings_dialog is None
    assert session.dialogs.model.kind is DialogKind.NONE
    assert isinstance(runtime.commands[-1], ConnectSaved)


def test_router_routes_colors_preview_cancel_and_reconnect_through_the_session(
    qt_application: QApplication,
) -> None:
    """Keep preview and connected-color actions in the session-owned flow."""
    settings = AppSettings.default()
    runtime = _Runtime()
    coordinator = CaptureCoordinator(
        publisher=InputPublisher(clock=SystemClock(), sink=runtime),
        pointer_capture=_PointerCapture(),
    )
    assert coordinator.start_capture()
    session = ApplicationSession(
        settings=settings,
        paths=SettingsPaths(Path("config"), Path("data"), Path("log")),
        repository=_Repository(SettingsLoadResult(settings, SettingsLoadStatus.FIRST_RUN)),
        runtime=runtime,
        coordinator=coordinator,
    )
    window = MainWindow(WindowSpec(width=960, height=640, maximized=False))
    window.set_frame(runtime.frames[-1])
    router = QtApplicationEventRouter(window)
    router.bind(session)
    router.handle_runtime_event(ConnectionChanged(ConnectionState.CONNECTED))
    original_colors = settings.controller_colors

    window.main_toolbar.colors_action.trigger()
    qt_application.processEvents()
    cancelled = window.active_settings_dialog
    assert isinstance(cancelled, ControllerColorsDialog)
    assert cancelled.set_color("body", "#ABCDEF")
    assert window.controller_preview.model is not None
    assert window.controller_preview.model.body_color == "#ABCDEF"

    cancelled.reject()
    qt_application.processEvents()
    assert window.controller_preview.model is not None
    assert window.controller_preview.model.body_color == original_colors.body

    window.main_toolbar.colors_action.trigger()
    qt_application.processEvents()
    deferred = window.active_settings_dialog
    assert isinstance(deferred, ControllerColorsDialog)
    assert deferred.set_color("buttons", "#123456")
    deferred.request_save()
    qt_application.processEvents()
    deferred_confirmation = deferred.reconnect_confirmation
    assert deferred_confirmation is not None
    defer_button = deferred_confirmation.button(QMessageBox.StandardButton.No)
    assert defer_button is not None
    defer_button.click()
    qt_application.processEvents()
    assert session.settings.controller_colors.buttons == "#123456"
    assert session.ui_snapshot.color_reconnect_pending is False
    assert window.active_settings_dialog is None
    assert not any(isinstance(command, RecreateWithColors) for command in runtime.commands)

    window.main_toolbar.colors_action.trigger()
    qt_application.processEvents()
    reconnecting = window.active_settings_dialog
    assert isinstance(reconnecting, ControllerColorsDialog)
    assert reconnecting.set_color("left_grip", "#654321")
    reconnecting.request_save()
    qt_application.processEvents()
    reconnect_confirmation = reconnecting.reconnect_confirmation
    assert reconnect_confirmation is not None
    reconnect_button = reconnect_confirmation.button(QMessageBox.StandardButton.Yes)
    assert reconnect_button is not None
    reconnect_button.click()
    qt_application.processEvents()

    assert session.settings.controller_colors.left_grip == "#654321"
    assert isinstance(runtime.commands[-1], RecreateWithColors)
    assert window.active_settings_dialog is None


def test_router_binds_connection_and_capture_toolbar_actions_to_the_session(
    qt_application: QApplication,
) -> None:
    """Use the session state machine for normal toolbar operations."""
    settings = replace(
        AppSettings.default(),
        connection=replace(AppSettings.default().connection, adapter_id="usb:0"),
    )
    runtime = _Runtime()
    pointer_capture = _PointerCapture()
    coordinator = CaptureCoordinator(
        publisher=InputPublisher(clock=SystemClock(), sink=runtime),
        pointer_capture=pointer_capture,
    )
    session = ApplicationSession(
        settings=settings,
        paths=SettingsPaths(Path("config"), Path("data"), Path("log")),
        repository=_Repository(SettingsLoadResult(settings, SettingsLoadStatus.LOADED)),
        runtime=runtime,
        coordinator=coordinator,
    )
    window = MainWindow(WindowSpec(width=960, height=640, maximized=False))
    router = QtApplicationEventRouter(window)
    router.bind(session)
    router.handle_runtime_event(
        AdaptersDiscovered((AdapterDescriptor("usb:0", "Test Adapter", "usb"),))
    )
    router.handle_runtime_event(ConnectionChanged(ConnectionState.READY, adapter_id="usb:0"))

    window.main_toolbar.capture_action.trigger()
    assert coordinator.is_captured
    assert runtime.frames[-1].capture_active
    assert window.main_toolbar.capture_action.isChecked()

    window.main_toolbar.capture_action.trigger()
    assert not coordinator.is_captured
    assert not runtime.frames[-1].capture_active
    assert not window.main_toolbar.capture_action.isChecked()

    window.main_toolbar.connection_action.trigger()
    assert isinstance(runtime.commands[-1], ConnectSaved)
    assert session.ui_snapshot.connection_state is ConnectionState.CONNECTING

    router.handle_runtime_event(ConnectionChanged(ConnectionState.CONNECTED, adapter_id="usb:0"))
    window.main_toolbar.connection_action.trigger()
    assert isinstance(runtime.commands[-1], Disconnect)
    assert session.ui_snapshot.connection_state is ConnectionState.DISCONNECTING
    assert qt_application is not None


def test_router_opens_connection_settings_when_connection_is_not_configured(
    qt_application: QApplication,
) -> None:
    """Show configuration rather than silently ignoring an unconfigured connect."""
    settings = AppSettings.default()
    runtime = _Runtime()
    coordinator = CaptureCoordinator(
        publisher=InputPublisher(clock=SystemClock(), sink=runtime),
        pointer_capture=_PointerCapture(),
    )
    session = ApplicationSession(
        settings=settings,
        paths=SettingsPaths(Path("config"), Path("data"), Path("log")),
        repository=_Repository(SettingsLoadResult(settings, SettingsLoadStatus.FIRST_RUN)),
        runtime=runtime,
        coordinator=coordinator,
    )
    window = MainWindow(WindowSpec(width=960, height=640, maximized=False))
    router = QtApplicationEventRouter(window)
    router.bind(session)
    router.handle_runtime_event(ConnectionChanged(ConnectionState.READY))

    window.main_toolbar.connection_action.trigger()
    qt_application.processEvents()

    dialog = window.active_settings_dialog
    assert isinstance(dialog, ConnectionDialog)
    assert session.dialogs.model.kind is DialogKind.CONNECTION

    dialog.reject()
    qt_application.processEvents()

    assert window.active_settings_dialog is None
    assert session.dialogs.model.kind is DialogKind.NONE
    assert window.main_toolbar.connection_action.isEnabled()


def test_worker_event_changes_presentation_only_after_queued_gui_delivery(
    qt_application: QApplication,
) -> None:
    receiver = _PresentationReceiver()
    bridge = QtRuntimeEventBridge(receiver.handle_runtime_event)
    assert isinstance(bridge, QObject)
    worker_threads: list[int] = []
    event = AdaptersDiscovered(
        adapters=(AdapterDescriptor("usb:0", "Test Adapter", "usb"),),
    )

    def emit_from_worker() -> None:
        worker_threads.append(get_ident())
        bridge.emit(event)

    main_thread = get_ident()
    worker = Thread(target=emit_from_worker)
    worker.start()
    worker.join()

    assert worker.ident is not None
    assert worker_threads == [worker.ident]
    assert worker_threads[0] != main_thread
    assert receiver.adapter_labels == ()
    assert receiver.delivery_thread is None

    qt_application.processEvents()

    assert receiver.adapter_labels == ("Test Adapter",)
    assert receiver.delivery_thread == main_thread


def test_queued_bridge_delivers_all_runtime_events_in_order_to_application_session(
    qt_application: QApplication,
) -> None:
    session = _RecordingApplicationSession()
    bridge = QtRuntimeEventBridge(session.handle_runtime_event)
    events: tuple[RuntimeEvent, ...] = (
        AdaptersDiscovered((AdapterDescriptor("usb:0", "Test Adapter", "usb"),)),
        ConnectionChanged(ConnectionState.READY, adapter_id="usb:0"),
        PairingProgress("ペアリング待機中"),
        StatusSnapshot(ConnectionState.CONNECTING, latest_frame=None, watchdog_tripped=False),
        WatchdogNeutralized(capture_epoch=3),
        ControllerError(
            category=ControllerErrorCategory.RECONNECT_FAILED,
            summary="接続に失敗しました",
            retryable=True,
            diagnostic_id="test-0001",
        ),
        RuntimeStopped(),
    )

    def emit_from_worker() -> None:
        for event in events:
            bridge.emit(event)

    worker = Thread(target=emit_from_worker)
    worker.start()
    worker.join()

    assert session.events == []

    qt_application.processEvents()

    assert session.events == list(events)


@pytest.mark.parametrize("retryable", [True, False])
def test_worker_fault_is_queued_to_widgets_and_runtime_stop_disables_interaction(
    qt_application: QApplication,
    retryable: bool,
) -> None:
    settings = AppSettings.default()
    runtime = _Runtime()
    pointer_capture = _PointerCapture()
    coordinator = CaptureCoordinator(
        publisher=InputPublisher(clock=SystemClock(), sink=runtime),
        pointer_capture=pointer_capture,
    )
    session = ApplicationSession(
        settings=settings,
        paths=SettingsPaths(Path("config"), Path("data"), Path("log")),
        repository=_Repository(SettingsLoadResult(settings, SettingsLoadStatus.FIRST_RUN)),
        runtime=runtime,
        coordinator=coordinator,
    )
    window = _RecordingMainWindow(WindowSpec(width=960, height=640, maximized=False))
    router = QtApplicationEventRouter(window)
    router.bind(session)
    bridge = QtRuntimeEventBridge(router.handle_runtime_event, parent=window)
    secret = "bond=private-worker-token"  # noqa: S105 - test value must not reach widgets.
    worker_threads: list[int] = []
    main_thread = get_ident()

    assert coordinator.start_capture() is True
    assert runtime.frames[-1].capture_active is True

    def emit_from_worker(event: RuntimeEvent) -> None:
        worker_threads.append(get_ident())
        bridge.emit(event)

    error_worker = Thread(
        target=emit_from_worker,
        args=(
            ControllerError(
                category=ControllerErrorCategory.RECONNECT_FAILED,
                summary=secret,
                retryable=retryable,
                diagnostic_id="worker-fault-0001",
            ),
        ),
    )
    error_worker.start()
    error_worker.join()

    assert window.status_bar.connection_label.text() == "接続: 停止"
    qt_application.processEvents()

    assert coordinator.is_captured is False
    assert runtime.frames[-1].capture_active is False
    assert window.main_toolbar.connection_action.isEnabled() is retryable
    assert window.status_bar.connection_label.text() == "接続: エラー"
    assert window.status_bar.notice_label.text() == "エラー: 保存済み接続に失敗しました"
    assert secret not in window.status_bar.notice_label.text()
    assert set(window.refresh_threads) == {main_thread}

    stopped_worker = Thread(target=emit_from_worker, args=(RuntimeStopped(),))
    stopped_worker.start()
    stopped_worker.join()
    qt_application.processEvents()

    assert worker_threads[0] != main_thread
    assert worker_threads[1] != main_thread
    assert session.ui_snapshot.application_state is AppState.SHUTTING_DOWN
    assert session.ui_snapshot.connection_state is ConnectionState.STOPPED
    assert runtime.frames[-1].capture_active is False
    assert not window.main_toolbar.connection_action.isEnabled()
    assert not window.main_toolbar.capture_action.isEnabled()
    assert not window.main_toolbar.mapping_action.isEnabled()
    assert not window.main_toolbar.connection_settings_action.isEnabled()
    assert not window.main_toolbar.colors_action.isEnabled()
    assert window.status_bar.connection_label.text() == "接続: 停止"
    assert window.status_bar.notice_label.text() == "エラー: 保存済み接続に失敗しました"
    assert set(window.refresh_threads) == {main_thread}


def test_shutdown_drops_queued_events_timer_timeouts_and_dialog_callbacks(
    qt_application: QApplication,
) -> None:
    settings = AppSettings.default()
    runtime = _Runtime()
    window = _RecordingMainWindow(WindowSpec(width=960, height=640, maximized=False))
    coordinator = CaptureCoordinator(
        publisher=InputPublisher(clock=SystemClock(), sink=runtime),
        pointer_capture=window,
    )
    session = ApplicationSession(
        settings=settings,
        paths=SettingsPaths(Path("config"), Path("data"), Path("log")),
        repository=_Repository(SettingsLoadResult(settings, SettingsLoadStatus.FIRST_RUN)),
        runtime=runtime,
        coordinator=coordinator,
    )
    router = QtApplicationEventRouter(window)
    router.bind(session)
    bridge = QtRuntimeEventBridge(router.handle_runtime_event, parent=window)
    window.configure_input(publisher=coordinator.publisher, coordinator=coordinator)
    dialogs: list[QDialog] = []

    def create_dialog(parent: QWidget) -> QDialog:
        dialog = QDialog(parent)
        dialog.finished.connect(lambda _result: runtime.post(DiscoverAdapters()))
        dialogs.append(dialog)
        return dialog

    window.bind_settings_dialog_factories(
        mapping=create_dialog,
        connection=lambda _parent: None,
        colors=lambda _parent: None,
    )
    window.main_toolbar.mapping_action.trigger()
    qt_application.processEvents()
    dialog = dialogs[0]
    snapshot_before_shutdown = session.ui_snapshot
    notice_before_shutdown = window.status_bar.notice_label.text()
    frame_count_before_shutdown = len(runtime.frames)

    worker = Thread(
        target=lambda: bridge.emit(
            ControllerError(
                category=ControllerErrorCategory.UNEXPECTED,
                summary="bond=private-late-worker-token",
                retryable=False,
                diagnostic_id="late-worker-0001",
            )
        )
    )
    worker.start()
    worker.join()

    bridge.deactivate()
    router.deactivate()
    window.begin_shutdown()
    qt_application.processEvents()
    window._input_evaluation_timer.timeout.emit()
    dialog.finished.emit(0)
    bridge.emit(
        ControllerError(
            category=ControllerErrorCategory.UNEXPECTED,
            summary="bond=private-post-stop-token",
            retryable=False,
            diagnostic_id="late-worker-0002",
        )
    )
    qt_application.processEvents()

    assert session.ui_snapshot == snapshot_before_shutdown
    assert window.status_bar.notice_label.text() == notice_before_shutdown
    assert len(runtime.frames) == frame_count_before_shutdown
    assert runtime.commands == []
    assert window.input_evaluation_interval_ms is None
    assert not dialog.isVisible()
    assert window.active_settings_dialog is None
