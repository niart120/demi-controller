from threading import Thread, get_ident

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from demi.application.state import ConnectionState
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
from demi.ui.event_bridge import QtRuntimeEventBridge


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
