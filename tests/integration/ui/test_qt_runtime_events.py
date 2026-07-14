from dataclasses import dataclass, field
from pathlib import Path
from threading import Thread, get_ident

import pytest
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from demi.app import ApplicationSession, SystemClock, WindowSpec
from demi.application.coordinator import CaptureCoordinator
from demi.application.state import AppState, ConnectionState
from demi.application.ui_state import ApplicationUiSnapshot
from demi.config.paths import SettingsPaths
from demi.config.repository import SettingsLoadResult, SettingsLoadStatus
from demi.controller.commands import ControllerCommand
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
from demi.ui.application import QtApplicationEventRouter
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


class _RecordingMainWindow(MainWindow):
    """Main window that records every widget refresh thread."""

    def __init__(self, spec: WindowSpec) -> None:
        self.refresh_threads: list[int] = []
        super().__init__(spec)

    def refresh(self, snapshot: ApplicationUiSnapshot) -> None:
        """Record the GUI thread before applying the standard refresh."""
        self.refresh_threads.append(get_ident())
        super().refresh(snapshot)


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
