from threading import Thread, get_ident

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from demi.controller.events import AdapterDescriptor, AdaptersDiscovered, RuntimeEvent
from demi.ui.event_bridge import QtRuntimeEventBridge


class _PresentationReceiver:
    def __init__(self) -> None:
        self.adapter_labels: tuple[str, ...] = ()
        self.delivery_thread: int | None = None

    def handle_runtime_event(self, event: RuntimeEvent) -> None:
        assert isinstance(event, AdaptersDiscovered)
        self.adapter_labels = tuple(adapter.display_name for adapter in event.adapters)
        self.delivery_thread = get_ident()


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
