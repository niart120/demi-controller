"""Queued Qt delivery for immutable controller runtime events."""

from collections.abc import Callable
from typing import overload

from PySide6.QtCore import QObject, Qt, Signal, Slot

from demi.controller.events import (
    AdaptersDiscovered,
    ConnectionChanged,
    ControllerError,
    PairingProgress,
    RuntimeEvent,
    RuntimeStopped,
    StatusSnapshot,
    WatchdogNeutralized,
)

type RuntimeEventReceiver = Callable[[RuntimeEvent], object]


class QtRuntimeEventBridge(QObject):
    """Deliver worker events to a receiver on the GUI Qt thread."""

    runtime_event = Signal(object)

    def __init__(
        self,
        receiver: RuntimeEventReceiver,
        parent: QObject | None = None,
    ) -> None:
        """Create a queued worker-to-GUI event boundary.

        Args:
            receiver: Main-thread callback that reduces one runtime event.
            parent: Optional Qt owner for the bridge lifecycle.
        """
        super().__init__(parent)
        self._receiver = receiver
        self.runtime_event.connect(self._deliver, Qt.ConnectionType.QueuedConnection)

    @overload
    def emit(self, signal: bytes | bytearray | memoryview, /, *args: None) -> bool: ...

    @overload
    def emit(self, event: RuntimeEvent) -> None: ...

    def emit(
        self,
        event: bytes | bytearray | memoryview | RuntimeEvent,
        *args: None,
    ) -> bool | None:
        """Queue a runtime event or preserve QObject's legacy emission API.

        Args:
            event: Runtime event created by the controller worker, or a legacy
                Qt signal signature.
            args: Values passed through with a legacy Qt signal signature.

        Returns:
            The legacy QObject emission result, or ``None`` after queuing a
            runtime event.
        """
        if isinstance(event, (bytes, bytearray, memoryview)):
            return super().emit(event, *args)
        self.runtime_event.emit(_runtime_event_from_signal(event))
        return None

    @Slot(object)
    def _deliver(self, event: object) -> None:
        self._receiver(_runtime_event_from_signal(event))


def _runtime_event_from_signal(event: object) -> RuntimeEvent:
    if isinstance(
        event,
        (
            AdaptersDiscovered,
            ConnectionChanged,
            ControllerError,
            PairingProgress,
            RuntimeStopped,
            StatusSnapshot,
            WatchdogNeutralized,
        ),
    ):
        return event
    raise TypeError
