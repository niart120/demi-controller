from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, get_ident

from demi.application.state import ConnectionState
from demi.controller.commands import ConnectSaved, Disconnect, DiscoverAdapters, RequestStatus
from demi.controller.events import (
    AdapterDescriptor,
    AdaptersDiscovered,
    ConnectionChanged,
    RuntimeEvent,
    StatusSnapshot,
)
from demi.controller.runtime import ControllerRuntime
from demi.domain.controller import ControllerFrame
from demi.domain.settings import ControllerColorSettings


@dataclass
class FakeClock:
    """Monotonic clock for command integration tests."""

    now_ns: int = 1_000_000_000

    def monotonic_ns(self) -> int:
        """Return the configured timestamp."""
        return self.now_ns


@dataclass
class RecordingEvents:
    """Event sink with command milestone signals."""

    events: list[RuntimeEvent] = field(default_factory=list)
    discovered: Event = field(default_factory=Event)
    connected: Event = field(default_factory=Event)
    status: Event = field(default_factory=Event)
    ready_after_disconnect: Event = field(default_factory=Event)

    def emit(self, event: RuntimeEvent) -> None:
        """Record events and signal expected milestones."""
        self.events.append(event)
        if isinstance(event, AdaptersDiscovered):
            self.discovered.set()
        elif isinstance(event, ConnectionChanged):
            if event.state is ConnectionState.CONNECTED:
                self.connected.set()
            if event.state is ConnectionState.READY and self.connected.is_set():
                self.ready_after_disconnect.set()
        elif isinstance(event, StatusSnapshot):
            self.status.set()


@dataclass
class RecordingAdapter:
    """Fake adapter recording every worker-owned operation."""

    operations: list[str] = field(default_factory=list)
    thread_ids: list[int] = field(default_factory=list)

    def _record(self, name: str) -> None:
        self.operations.append(name)
        self.thread_ids.append(get_ident())

    async def discover_adapters(self) -> tuple[AdapterDescriptor, ...]:
        """Return one fake USB adapter."""
        self._record("discover")
        return (AdapterDescriptor("usb:0", "Fake", "usb"),)

    async def connect_saved(
        self,
        adapter_id: str,
        bond_path: Path,
        timeout_seconds: float,
        colors: ControllerColorSettings,
    ) -> None:
        """Record a saved connection."""
        del adapter_id, bond_path, timeout_seconds, colors
        self._record("connect_saved")

    async def start_pairing(
        self,
        adapter_id: str,
        timeout_seconds: float,
        colors: ControllerColorSettings,
    ) -> None:
        """Record a pairing request."""
        del adapter_id, timeout_seconds, colors
        self._record("pairing")

    async def disconnect(self) -> None:
        """Record a disconnect request."""
        self._record("disconnect")

    async def recreate_with_colors(self, colors: ControllerColorSettings) -> None:
        """Record a color recreation request."""
        del colors
        self._record("colors")

    async def apply_frame(self, frame: ControllerFrame) -> None:
        """Record a complete frame application."""
        del frame
        self._record("apply_frame")

    async def close(self) -> None:
        """Record adapter close."""
        self._record("close")


def test_commands_are_ordered_on_worker_and_events_return_to_the_sink() -> None:
    adapter = RecordingAdapter()
    events = RecordingEvents()
    runtime = ControllerRuntime(
        adapter_factory=lambda: adapter,
        event_sink=events,
        clock=FakeClock(),
    )
    runtime.start()

    runtime.post(DiscoverAdapters())
    assert events.discovered.wait(timeout=1.0)
    runtime.post(
        ConnectSaved(
            adapter_id="usb:0",
            bond_path=Path("bonds/default.json"),
            timeout_seconds=30.0,
            colors=ControllerColorSettings(),
        )
    )
    assert events.connected.wait(timeout=1.0)
    runtime.post(RequestStatus())
    assert events.status.wait(timeout=1.0)
    runtime.post(Disconnect())
    assert events.ready_after_disconnect.wait(timeout=1.0)

    runtime.close()

    assert adapter.operations[:4] == ["discover", "connect_saved", "apply_frame", "apply_frame"]
    assert "disconnect" in adapter.operations
    assert adapter.operations[-1] == "close"
    assert len(set(adapter.thread_ids)) == 1
