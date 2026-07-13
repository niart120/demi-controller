from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, get_ident

from demi.application.state import ConnectionState
from demi.controller.adapter import ControllerAdapterError
from demi.controller.commands import (
    ConnectSaved,
    Disconnect,
    DiscoverAdapters,
    RequestStatus,
    StartPairing,
)
from demi.controller.events import (
    AdapterDescriptor,
    AdaptersDiscovered,
    ConnectionChanged,
    ControllerError,
    ControllerErrorCategory,
    RuntimeEvent,
    StatusSnapshot,
    WatchdogNeutralized,
)
from demi.controller.runtime import ControllerRuntime
from demi.domain.controller import AccelG, ControllerFrame, GyroRate, StickVector
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
    watchdog_neutralized: Event = field(default_factory=Event)
    error: Event = field(default_factory=Event)
    ready_after_error: Event = field(default_factory=Event)

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
        elif isinstance(event, WatchdogNeutralized):
            self.watchdog_neutralized.set()
        elif isinstance(event, ControllerError):
            self.error.set()
        if (
            isinstance(event, ConnectionChanged)
            and event.state is ConnectionState.READY
            and self.error.is_set()
        ):
            self.ready_after_error.set()


@dataclass
class RecordingAdapter:
    """Fake adapter recording every worker-owned operation."""

    operations: list[str] = field(default_factory=list)
    thread_ids: list[int] = field(default_factory=list)
    applied_frames: list[ControllerFrame] = field(default_factory=list)
    applied: Event = field(default_factory=Event)
    applied_active: Event = field(default_factory=Event)
    pairing_bond_paths: list[Path] = field(default_factory=list)
    active_frame_attempts: list[ControllerFrame] = field(default_factory=list)
    connect_started: Event | None = None
    connect_release: Event | None = None
    active_frame_error: Exception | None = None

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
        if self.connect_started is not None:
            self.connect_started.set()
        if self.connect_release is not None and not self.connect_release.wait(timeout=1.0):
            raise TimeoutError

    async def start_pairing(
        self,
        adapter_id: str,
        bond_path: Path,
        timeout_seconds: float,
        colors: ControllerColorSettings,
    ) -> None:
        """Record a pairing request."""
        del adapter_id, timeout_seconds, colors
        self.pairing_bond_paths.append(bond_path)
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
        self._record("apply_frame")
        if frame.capture_active:
            self.active_frame_attempts.append(frame)
            if self.active_frame_error is not None:
                raise self.active_frame_error
        self.applied_frames.append(frame)
        self.applied.set()
        if frame.capture_active:
            self.applied_active.set()

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


def make_frame(*, sequence: int, epoch: int, active: bool = True) -> ControllerFrame:
    """Build a valid frame for runtime mailbox integration tests."""
    return ControllerFrame(
        sequence=sequence,
        capture_epoch=epoch,
        monotonic_ns=sequence,
        buttons=frozenset(),
        left_stick=StickVector(x=0.0, y=0.0),
        right_stick=StickVector(x=0.0, y=0.0),
        gyro_rate=GyroRate(0.0, 0.0, 0.0),
        accel_g=AccelG(0.0, 0.0, 1.0),
        capture_active=active,
    )


def test_unconnected_frames_are_retained_and_connected_worker_applies_latest_only() -> None:
    connect_started = Event()
    connect_release = Event()
    adapter = RecordingAdapter(
        connect_started=connect_started,
        connect_release=connect_release,
    )
    events = RecordingEvents()
    runtime = ControllerRuntime(
        adapter_factory=lambda: adapter,
        event_sink=events,
        clock=FakeClock(),
    )
    runtime.start()

    pending = make_frame(sequence=1, epoch=1)
    assert runtime.offer_frame(pending) is True
    latest_snapshot: StatusSnapshot | None = None
    for _ in range(10):
        events.status.clear()
        runtime.post(RequestStatus())
        assert events.status.wait(timeout=1.0)
        latest_snapshot = next(
            event for event in reversed(events.events) if isinstance(event, StatusSnapshot)
        )
        if latest_snapshot.latest_frame == pending:
            break
    assert latest_snapshot is not None
    assert latest_snapshot.latest_frame == pending
    assert runtime.latest_frame == pending
    assert adapter.applied_frames == []

    second = make_frame(sequence=2, epoch=1)
    newest = make_frame(sequence=3, epoch=1)
    runtime.post(
        ConnectSaved(
            adapter_id="usb:0",
            bond_path=Path("bonds/default.json"),
            timeout_seconds=30.0,
            colors=ControllerColorSettings(),
        )
    )
    assert connect_started.wait(timeout=1.0)
    assert runtime.offer_frame(second) is True
    assert runtime.offer_frame(newest) is True
    connect_release.set()
    assert events.connected.wait(timeout=1.0)
    assert adapter.applied_active.wait(timeout=1.0)

    assert adapter.applied_frames[-1] == newest
    assert second not in adapter.applied_frames
    runtime.close()


def test_stale_frames_and_watchdog_epoch_restart_are_filtered() -> None:
    clock = FakeClock()
    adapter = RecordingAdapter()
    events = RecordingEvents()
    runtime = ControllerRuntime(
        adapter_factory=lambda: adapter,
        event_sink=events,
        clock=clock,
    )
    runtime.start()
    runtime.post(
        ConnectSaved(
            adapter_id="usb:0",
            bond_path=Path("bonds/default.json"),
            timeout_seconds=30.0,
            colors=ControllerColorSettings(),
        )
    )
    assert events.connected.wait(timeout=1.0)

    first = make_frame(sequence=1, epoch=1)
    assert runtime.offer_frame(first) is True
    assert adapter.applied_active.wait(timeout=1.0)
    assert runtime.offer_frame(make_frame(sequence=0, epoch=1)) is False
    assert runtime.offer_frame(make_frame(sequence=2, epoch=0)) is False

    clock.now_ns += 250_000_000
    assert events.watchdog_neutralized.wait(timeout=1.0)
    assert runtime.watchdog_tripped is True

    adapter.applied_active.clear()
    same_epoch = make_frame(sequence=2, epoch=1)
    assert runtime.offer_frame(same_epoch) is True
    for _ in range(2):
        events.status.clear()
        runtime.post(RequestStatus())
        assert events.status.wait(timeout=1.0)
    assert runtime.latest_frame == same_epoch
    assert adapter.applied_active.wait(timeout=0.1) is False

    new_epoch = make_frame(sequence=3, epoch=2)
    assert runtime.offer_frame(new_epoch) is True
    assert adapter.applied_active.wait(timeout=1.0)
    assert adapter.applied_frames[-1] == new_epoch
    assert same_epoch not in adapter.applied_frames
    runtime.close()


def test_start_pairing_passes_the_bond_path_through_the_runtime_boundary() -> None:
    adapter = RecordingAdapter()
    events = RecordingEvents()
    runtime = ControllerRuntime(
        adapter_factory=lambda: adapter,
        event_sink=events,
        clock=FakeClock(),
    )
    runtime.start()
    bond_path = Path("bonds/pairing.json")
    runtime.post(
        StartPairing(
            adapter_id="usb:0",
            bond_path=bond_path,
            timeout_seconds=30.0,
            colors=ControllerColorSettings(),
        )
    )
    assert events.connected.wait(timeout=1.0)
    runtime.close()

    assert adapter.pairing_bond_paths == [bond_path]


def test_connection_loss_returns_to_ready_and_stops_active_frame_delivery() -> None:
    adapter = RecordingAdapter(
        active_frame_error=ControllerAdapterError(ControllerErrorCategory.CONNECTION_LOST)
    )
    events = RecordingEvents()
    runtime = ControllerRuntime(
        adapter_factory=lambda: adapter,
        event_sink=events,
        clock=FakeClock(),
    )
    runtime.start()
    runtime.post(
        ConnectSaved(
            adapter_id="usb:0",
            bond_path=Path("bonds/default.json"),
            timeout_seconds=30.0,
            colors=ControllerColorSettings(),
        )
    )
    assert events.connected.wait(timeout=1.0)

    first = make_frame(sequence=1, epoch=1)
    assert runtime.offer_frame(first) is True
    assert events.error.wait(timeout=1.0)
    assert events.ready_after_error.wait(timeout=1.0)

    second = make_frame(sequence=2, epoch=1)
    assert runtime.offer_frame(second) is True
    events.status.clear()
    runtime.post(RequestStatus())
    assert events.status.wait(timeout=1.0)

    assert adapter.active_frame_attempts == [first]
    assert adapter.operations[-1] == "close"
    states = [event.state for event in events.events if isinstance(event, ConnectionChanged)]
    assert states[-2:] == [ConnectionState.ERROR, ConnectionState.READY]
    assert any(
        isinstance(event, ControllerError)
        and event.category is ControllerErrorCategory.CONNECTION_LOST
        for event in events.events
    )
    runtime.close()
