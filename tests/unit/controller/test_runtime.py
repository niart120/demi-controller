import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, Thread, get_ident
from time import monotonic

import pytest

from demi.application.state import ConnectionState
from demi.controller.adapter import ControllerAdapterError
from demi.controller.commands import (
    ConnectSaved,
    DiscoverAdapters,
    RecreateWithColors,
    StartPairing,
)
from demi.controller.events import (
    AdapterDescriptor,
    AdaptersDiscovered,
    ConnectionChanged,
    ControllerError,
    ControllerErrorCategory,
    RuntimeEvent,
    RuntimeStopped,
)
from demi.controller.runtime import ControllerRuntime
from demi.domain.controller import AccelG, ControllerFrame, GyroRate, StickVector
from demi.domain.settings import ControllerColorSettings


@dataclass
class FakeClock:
    """Monotonic clock for runtime lifecycle tests."""

    now_ns: int = 1_000_000_000

    def monotonic_ns(self) -> int:
        """Return the configured timestamp."""
        return self.now_ns


@dataclass
class EventRecorder:
    """Thread-safe enough event recorder for short lifecycle tests."""

    events: list[RuntimeEvent] = field(default_factory=list)
    ready: Event = field(default_factory=Event)
    stopped: Event = field(default_factory=Event)
    error: Event = field(default_factory=Event)
    connected: Event = field(default_factory=Event)
    discovered: Event = field(default_factory=Event)
    thread_ids: list[int] = field(default_factory=list)

    def emit(self, event: RuntimeEvent) -> None:
        """Record an event and signal lifecycle milestones."""
        self.events.append(event)
        self.thread_ids.append(get_ident())
        if isinstance(event, ConnectionChanged) and event.state.value == "ready":
            self.ready.set()
        if isinstance(event, ConnectionChanged) and event.state.value == "connected":
            self.connected.set()
        if isinstance(event, AdaptersDiscovered):
            self.discovered.set()
        if isinstance(event, RuntimeStopped):
            self.stopped.set()
        if isinstance(event, ControllerError):
            self.error.set()


def make_frame(*, sequence: int = 1, epoch: int = 1) -> ControllerFrame:
    """Build a public-domain frame for runtime lifecycle tests."""
    return ControllerFrame(
        sequence=sequence,
        capture_epoch=epoch,
        monotonic_ns=sequence,
        buttons=frozenset(),
        left_stick=StickVector(x=0.0, y=0.0),
        right_stick=StickVector(x=0.0, y=0.0),
        gyro_rate=GyroRate(0.0, 0.0, 0.0),
        accel_g=AccelG(0.0, 0.0, 1.0),
        capture_active=True,
    )


@dataclass
class FakeAdapter:
    """Minimal async adapter owned by the runtime worker."""

    close_thread_id: int | None = None
    closed: bool = False
    connect_error: Exception | None = None
    discover_error: Exception | None = None
    disconnect_error: Exception | None = None
    recreate_error: Exception | None = None
    discover_calls: int = 0
    connect_calls: int = 0
    recreate_calls: int = 0
    close_calls: int = 0
    apply_calls: int = 0
    fail_on_apply_call: int | None = None

    async def discover_adapters(self) -> tuple[AdapterDescriptor, ...]:
        """Return no adapters for the lifecycle test."""
        self.discover_calls += 1
        if self.discover_error is not None:
            raise self.discover_error
        return ()

    async def connect_saved(
        self,
        adapter_id: str,
        bond_path: Path,
        timeout_seconds: float,
        colors: ControllerColorSettings,
    ) -> None:
        """Complete a fake saved connection."""
        del adapter_id, bond_path, timeout_seconds, colors
        self.connect_calls += 1
        if self.closed:
            raise RuntimeError
        if self.connect_error is not None:
            raise self.connect_error

    async def start_pairing(
        self,
        adapter_id: str,
        bond_path: Path,
        timeout_seconds: float,
        colors: ControllerColorSettings,
    ) -> None:
        """Complete a fake pairing operation."""
        del adapter_id, bond_path, timeout_seconds, colors

    async def disconnect(self, *, neutral: bool = True) -> None:
        """Complete a fake disconnect."""
        del neutral
        if self.disconnect_error is not None:
            raise self.disconnect_error

    async def recreate_with_colors(
        self, colors: ControllerColorSettings, *, neutral: bool = True
    ) -> None:
        """Complete a fake color recreation."""
        del colors, neutral
        self.recreate_calls += 1
        if self.recreate_error is not None:
            raise self.recreate_error

    async def send_frame(self, frame: ControllerFrame) -> None:
        """Accept a frame without hardware."""
        del frame
        self.apply_calls += 1
        if self.apply_calls == self.fail_on_apply_call:
            raise RuntimeError

    async def close(self) -> None:
        """Record the worker thread that closed the adapter."""
        self.close_thread_id = get_ident()
        self.close_calls += 1
        self.closed = True


@dataclass
class WaitingConnectAdapter(FakeAdapter):
    """Keep a saved connection pending until the runtime cancels it."""

    connect_started: Event = field(default_factory=Event)
    connect_cancelled: Event = field(default_factory=Event)

    async def connect_saved(
        self,
        adapter_id: str,
        bond_path: Path,
        timeout_seconds: float,
        colors: ControllerColorSettings,
    ) -> None:
        """Wait indefinitely and record task cancellation."""
        del adapter_id, bond_path, timeout_seconds, colors
        self.connect_calls += 1
        self.connect_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.connect_cancelled.set()
            raise


@dataclass
class WaitingPairingAdapter(FakeAdapter):
    """Keep pairing pending until the runtime cancels it."""

    pairing_started: Event = field(default_factory=Event)
    pairing_cancelled: Event = field(default_factory=Event)

    async def start_pairing(
        self,
        adapter_id: str,
        bond_path: Path,
        timeout_seconds: float,
        colors: ControllerColorSettings,
    ) -> None:
        """Wait indefinitely and record task cancellation."""
        del adapter_id, bond_path, timeout_seconds, colors
        self.pairing_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.pairing_cancelled.set()
            raise


@dataclass
class WaitingRecreateAdapter(FakeAdapter):
    """Keep color recreation pending until the runtime cancels it."""

    recreate_started: Event = field(default_factory=Event)
    recreate_cancelled: Event = field(default_factory=Event)

    async def recreate_with_colors(
        self, colors: ControllerColorSettings, *, neutral: bool = True
    ) -> None:
        """Wait indefinitely and record task cancellation."""
        del colors, neutral
        self.recreate_calls += 1
        self.recreate_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.recreate_cancelled.set()
            raise


@dataclass
class WaitingCloseAdapter(FakeAdapter):
    """Pause adapter cleanup so shutdown-in-progress is observable."""

    close_started: Event = field(default_factory=Event)
    close_release: Event = field(default_factory=Event)

    async def close(self) -> None:
        """Wait for the test before completing adapter cleanup."""
        self.close_started.set()
        if not self.close_release.wait(timeout=1.0):
            raise TimeoutError
        await super().close()


@dataclass
class WaitingFrameAdapter(FakeAdapter):
    """Keep one active frame pending until shutdown cancellation."""

    frame_started: Event = field(default_factory=Event)
    frame_cancelled: Event = field(default_factory=Event)
    active_sequences: list[int] = field(default_factory=list)

    async def send_frame(self, frame: ControllerFrame) -> None:
        """Block active input but allow rest-state cleanup."""
        self.apply_calls += 1
        if not frame.capture_active:
            return
        self.active_sequences.append(frame.sequence)
        self.frame_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.frame_cancelled.set()
            raise


@dataclass
class CleanupRecordingAdapter(FakeAdapter):
    """Record ordered shutdown stages and fail at one selected stage."""

    fail_stage: str | None = None
    cleanup_operations: list[str] = field(default_factory=list)
    rest_calls: int = 0

    async def send_frame(self, frame: ControllerFrame) -> None:
        """Record initial and shutdown rest-state application."""
        self.apply_calls += 1
        if frame.capture_active:
            return
        self.rest_calls += 1
        if self.rest_calls == 1:
            return
        self.cleanup_operations.append("rest")
        if self.fail_stage == "rest":
            raise RuntimeError

    async def disconnect(self, *, neutral: bool = True) -> None:
        """Record disconnect and optionally fail it."""
        del neutral
        self.cleanup_operations.append("disconnect")
        if self.fail_stage == "disconnect":
            raise RuntimeError

    async def close(self) -> None:
        """Record close and optionally fail it."""
        self.cleanup_operations.append("close")
        self.close_calls += 1
        if self.fail_stage == "close":
            raise RuntimeError


def test_close_cancels_a_waiting_saved_connection_without_waiting_for_timeout() -> None:
    adapter = WaitingConnectAdapter()
    events = EventRecorder()
    runtime = ControllerRuntime(
        adapter_factory=lambda: adapter,
        event_sink=events,
        clock=FakeClock(),
    )
    runtime.start()
    runtime.post(
        ConnectSaved(
            adapter_id="usb:0",
            bond_path=Path("bond.json"),
            timeout_seconds=120.0,
            colors=ControllerColorSettings(),
        )
    )
    assert adapter.connect_started.wait(timeout=1.0)

    started_at = monotonic()
    runtime.close()
    elapsed = monotonic() - started_at

    assert elapsed < 1.0
    assert adapter.connect_cancelled.is_set()
    assert runtime.is_alive is False


def test_close_cancels_pairing_without_emitting_a_controller_error() -> None:
    adapter = WaitingPairingAdapter()
    events = EventRecorder()
    runtime = ControllerRuntime(
        adapter_factory=lambda: adapter,
        event_sink=events,
        clock=FakeClock(),
    )
    runtime.start()
    runtime.post(
        StartPairing(
            adapter_id="usb:0",
            bond_path=Path("bond.json"),
            timeout_seconds=120.0,
            colors=ControllerColorSettings(),
        )
    )
    assert adapter.pairing_started.wait(timeout=1.0)

    runtime.close()

    assert adapter.pairing_cancelled.is_set()
    assert not any(isinstance(event, ControllerError) for event in events.events)
    assert sum(isinstance(event, RuntimeStopped) for event in events.events) == 1


def test_close_cancels_color_recreation_without_late_connected_or_ready_events() -> None:
    adapter = WaitingRecreateAdapter()
    events = EventRecorder()
    runtime = ControllerRuntime(
        adapter_factory=lambda: adapter,
        event_sink=events,
        clock=FakeClock(),
    )
    runtime.start()
    runtime.post(
        ConnectSaved(
            adapter_id="usb:0",
            bond_path=Path("bond.json"),
            timeout_seconds=30.0,
            colors=ControllerColorSettings(),
        )
    )
    assert events.connected.wait(timeout=1.0)
    runtime.post(RecreateWithColors(ControllerColorSettings(body="#ABCDEF")))
    assert adapter.recreate_started.wait(timeout=1.0)
    event_count = len(events.events)

    runtime.close()

    assert adapter.recreate_cancelled.is_set()
    late_states = [
        event.state for event in events.events[event_count:] if isinstance(event, ConnectionChanged)
    ]
    assert ConnectionState.CONNECTED not in late_states
    assert ConnectionState.READY not in late_states


def test_runtime_rejects_commands_and_frames_during_and_after_shutdown() -> None:
    adapter = WaitingCloseAdapter()
    runtime = ControllerRuntime(
        adapter_factory=lambda: adapter,
        event_sink=EventRecorder(),
        clock=FakeClock(),
    )
    runtime.start()
    close_caller = Thread(target=runtime.close)
    close_caller.start()
    assert adapter.close_started.wait(timeout=1.0)
    frame = make_frame()

    with pytest.raises(RuntimeError):
        runtime.post(DiscoverAdapters())
    assert runtime.offer_frame(frame) is False
    assert adapter.discover_calls == 0
    assert adapter.apply_calls == 0

    adapter.close_release.set()
    close_caller.join(timeout=1.0)
    assert close_caller.is_alive() is False
    with pytest.raises(RuntimeError):
        runtime.post(DiscoverAdapters())
    assert runtime.offer_frame(frame) is False


def test_close_cancels_active_frame_and_does_not_apply_the_pending_mailbox_frame() -> None:
    adapter = WaitingFrameAdapter()
    events = EventRecorder()
    runtime = ControllerRuntime(
        adapter_factory=lambda: adapter,
        event_sink=events,
        clock=FakeClock(),
    )
    runtime.start()
    runtime.post(
        ConnectSaved(
            adapter_id="usb:0",
            bond_path=Path("bond.json"),
            timeout_seconds=30.0,
            colors=ControllerColorSettings(),
        )
    )
    assert events.connected.wait(timeout=1.0)
    first = make_frame(sequence=1)
    pending = make_frame(sequence=2)
    assert runtime.offer_frame(first) is True
    assert adapter.frame_started.wait(timeout=1.0)
    assert runtime.offer_frame(pending) is True

    runtime.close()

    assert adapter.frame_cancelled.is_set()
    assert adapter.active_sequences == [first.sequence]
    assert runtime.is_alive is False


@pytest.mark.parametrize("fail_stage", ["rest", "disconnect", "close"])
def test_shutdown_cleanup_preserves_order_and_continues_after_each_failure(
    fail_stage: str,
) -> None:
    adapter = CleanupRecordingAdapter(fail_stage=fail_stage)
    events = EventRecorder()
    runtime = ControllerRuntime(
        adapter_factory=lambda: adapter,
        event_sink=events,
        clock=FakeClock(),
    )
    runtime.start()
    runtime.post(
        ConnectSaved(
            adapter_id="usb:0",
            bond_path=Path("bond.json"),
            timeout_seconds=30.0,
            colors=ControllerColorSettings(),
        )
    )
    assert events.connected.wait(timeout=1.0)

    runtime.close()

    assert adapter.cleanup_operations == ["rest", "disconnect", "close"]
    assert events.stopped.wait(timeout=1.0)
    assert sum(isinstance(event, RuntimeStopped) for event in events.events) == 1
    assert runtime.is_alive is False


def test_concurrent_and_repeated_close_calls_share_one_shutdown_completion() -> None:
    adapter = WaitingConnectAdapter()
    events = EventRecorder()
    runtime = ControllerRuntime(
        adapter_factory=lambda: adapter,
        event_sink=events,
        clock=FakeClock(),
    )
    runtime.start()
    runtime.post(
        ConnectSaved(
            adapter_id="usb:0",
            bond_path=Path("bond.json"),
            timeout_seconds=120.0,
            colors=ControllerColorSettings(),
        )
    )
    assert adapter.connect_started.wait(timeout=1.0)
    errors: list[Exception] = []

    def close_runtime() -> None:
        try:
            runtime.close()
        except Exception as error:  # noqa: BLE001 - assertion records thread failure.
            errors.append(error)

    callers = [Thread(target=close_runtime) for _ in range(4)]
    for caller in callers:
        caller.start()
    for caller in callers:
        caller.join(timeout=1.0)
    runtime.close()

    assert errors == []
    assert all(caller.is_alive() is False for caller in callers)
    assert adapter.close_calls == 1
    assert sum(isinstance(event, RuntimeStopped) for event in events.events) == 1
    assert runtime.is_alive is False


def test_runtime_starts_worker_and_closes_without_leaking_the_thread() -> None:
    adapter = FakeAdapter()
    events = EventRecorder()
    runtime = ControllerRuntime(
        adapter_factory=lambda: adapter,
        event_sink=events,
        clock=FakeClock(),
    )
    main_thread_id = get_ident()

    runtime.start()
    assert events.ready.wait(timeout=1.0)
    assert runtime.is_alive is True
    assert events.thread_ids
    assert all(thread_id != main_thread_id for thread_id in events.thread_ids)

    runtime.close()

    assert events.stopped.wait(timeout=1.0)
    assert runtime.is_alive is False
    assert adapter.close_thread_id is not None
    assert adapter.close_thread_id != main_thread_id


def test_runtime_retains_the_latest_accepted_frame_for_status_before_send() -> None:
    runtime = ControllerRuntime(
        adapter_factory=FakeAdapter,
        event_sink=EventRecorder(),
        clock=FakeClock(),
    )
    frame = make_frame(sequence=1)

    assert runtime.offer_frame(frame) is True
    assert runtime.latest_frame == frame


def test_runtime_preserves_adapter_error_category_in_runtime_event() -> None:
    adapter = FakeAdapter(
        connect_error=ControllerAdapterError(ControllerErrorCategory.BOND_NOT_FOUND),
    )
    events = EventRecorder()
    runtime = ControllerRuntime(
        adapter_factory=lambda: adapter,
        event_sink=events,
        clock=FakeClock(),
    )
    runtime.start()
    runtime.post(
        ConnectSaved(
            adapter_id="usb:0",
            bond_path=Path("bond.json"),
            timeout_seconds=30.0,
            colors=ControllerColorSettings(),
        )
    )

    assert events.error.wait(timeout=1.0)
    errors = [event for event in events.events if isinstance(event, ControllerError)]
    assert errors[-1].category is ControllerErrorCategory.BOND_NOT_FOUND
    runtime.close()


def test_runtime_returns_to_ready_and_accepts_retry_after_discovery_error() -> None:
    adapter = FakeAdapter(
        discover_error=ControllerAdapterError(ControllerErrorCategory.ADAPTER_OPEN_FAILED)
    )
    events = EventRecorder()
    runtime = ControllerRuntime(
        adapter_factory=lambda: adapter,
        event_sink=events,
        clock=FakeClock(),
    )
    runtime.start()
    assert events.ready.wait(timeout=1.0)
    events.ready.clear()

    runtime.post(DiscoverAdapters())

    assert events.error.wait(timeout=1.0)
    assert events.ready.wait(timeout=1.0)
    discovery, error, recovered = events.events[-3:]
    assert isinstance(discovery, ConnectionChanged)
    assert discovery.state is ConnectionState.DISCOVERING
    assert isinstance(error, ControllerError)
    assert error.category is ControllerErrorCategory.ADAPTER_OPEN_FAILED
    assert error.summary == ControllerErrorCategory.ADAPTER_OPEN_FAILED.value
    assert isinstance(recovered, ConnectionChanged)
    assert recovered.state is ConnectionState.READY
    assert runtime.connection_state is ConnectionState.READY
    assert runtime.is_alive is True
    assert adapter.discover_calls == 1

    adapter.discover_error = None
    events.ready.clear()
    runtime.post(DiscoverAdapters())

    assert events.ready.wait(timeout=1.0)
    assert adapter.discover_calls == 2
    runtime.close()


def test_runtime_returns_to_connected_after_discovery_while_connected() -> None:
    adapter = FakeAdapter()
    events = EventRecorder()
    runtime = ControllerRuntime(
        adapter_factory=lambda: adapter,
        event_sink=events,
        clock=FakeClock(),
    )
    runtime.start()
    assert events.ready.wait(timeout=1.0)
    runtime.post(
        ConnectSaved(
            adapter_id="usb:0",
            bond_path=Path("bond.json"),
            timeout_seconds=30.0,
            colors=ControllerColorSettings(),
        )
    )
    assert events.connected.wait(timeout=1.0)
    events.discovered.clear()
    event_count = len(events.events)

    runtime.post(DiscoverAdapters())

    assert events.discovered.wait(timeout=1.0)
    transitions = [
        event for event in events.events[event_count:] if isinstance(event, ConnectionChanged)
    ]
    assert [event.state for event in transitions] == [
        ConnectionState.DISCOVERING,
        ConnectionState.CONNECTED,
    ]
    assert [event.adapter_id for event in transitions] == ["usb:0", "usb:0"]
    assert runtime.connection_state is ConnectionState.CONNECTED
    runtime.close()


def test_runtime_remains_connected_after_discovery_error_while_connected() -> None:
    adapter = FakeAdapter(
        discover_error=ControllerAdapterError(ControllerErrorCategory.ADAPTER_OPEN_FAILED)
    )
    events = EventRecorder()
    runtime = ControllerRuntime(
        adapter_factory=lambda: adapter,
        event_sink=events,
        clock=FakeClock(),
    )
    runtime.start()
    assert events.ready.wait(timeout=1.0)
    adapter.discover_error = None
    runtime.post(
        ConnectSaved(
            adapter_id="usb:0",
            bond_path=Path("bond.json"),
            timeout_seconds=30.0,
            colors=ControllerColorSettings(),
        )
    )
    assert events.connected.wait(timeout=1.0)
    adapter.discover_error = ControllerAdapterError(ControllerErrorCategory.ADAPTER_OPEN_FAILED)
    events.connected.clear()
    events.error.clear()
    event_count = len(events.events)

    runtime.post(DiscoverAdapters())

    assert events.error.wait(timeout=1.0)
    assert events.connected.wait(timeout=1.0)
    transitions = [
        event for event in events.events[event_count:] if isinstance(event, ConnectionChanged)
    ]
    assert [event.state for event in transitions] == [
        ConnectionState.DISCOVERING,
        ConnectionState.CONNECTED,
    ]
    assert runtime.connection_state is ConnectionState.CONNECTED
    runtime.close()


def test_runtime_restores_connected_state_after_recreating_colors() -> None:
    adapter = FakeAdapter()
    events = EventRecorder()
    runtime = ControllerRuntime(
        adapter_factory=lambda: adapter,
        event_sink=events,
        clock=FakeClock(),
    )
    runtime.start()
    assert events.ready.wait(timeout=1.0)
    runtime.post(
        ConnectSaved(
            adapter_id="usb:0",
            bond_path=Path("bond.json"),
            timeout_seconds=30.0,
            colors=ControllerColorSettings(),
        )
    )
    assert events.connected.wait(timeout=1.0)
    events.connected.clear()
    event_count = len(events.events)

    runtime.post(RecreateWithColors(ControllerColorSettings(body="#ABCDEF")))

    assert events.connected.wait(timeout=1.0)
    transitions = [
        event for event in events.events[event_count:] if isinstance(event, ConnectionChanged)
    ]
    assert [event.state for event in transitions] == [
        ConnectionState.CONNECTING,
        ConnectionState.CONNECTED,
    ]
    assert [event.adapter_id for event in transitions] == ["usb:0", "usb:0"]
    assert adapter.recreate_calls == 1
    assert runtime.connection_state is ConnectionState.CONNECTED
    runtime.close()


def test_runtime_recovers_to_ready_after_color_recreation_error() -> None:
    adapter = FakeAdapter(
        recreate_error=ControllerAdapterError(ControllerErrorCategory.CONNECTION_LOST)
    )
    events = EventRecorder()
    runtime = ControllerRuntime(
        adapter_factory=lambda: adapter,
        event_sink=events,
        clock=FakeClock(),
    )
    runtime.start()
    assert events.ready.wait(timeout=1.0)
    runtime.post(
        ConnectSaved(
            adapter_id="usb:0",
            bond_path=Path("bond.json"),
            timeout_seconds=30.0,
            colors=ControllerColorSettings(),
        )
    )
    assert events.connected.wait(timeout=1.0)
    events.error.clear()
    events.ready.clear()
    event_count = len(events.events)

    runtime.post(RecreateWithColors(ControllerColorSettings(body="#ABCDEF")))

    assert events.error.wait(timeout=1.0)
    assert events.ready.wait(timeout=1.0)
    transitions = [
        event for event in events.events[event_count:] if isinstance(event, ConnectionChanged)
    ]
    assert [event.state for event in transitions] == [
        ConnectionState.CONNECTING,
        ConnectionState.ERROR,
        ConnectionState.READY,
    ]
    assert adapter.closed is True
    assert adapter.close_calls == 1
    assert runtime.connection_state is ConnectionState.READY
    runtime.close()


def test_runtime_creates_a_fresh_adapter_after_error_recovery_releases_one() -> None:
    released = FakeAdapter(
        connect_error=ControllerAdapterError(ControllerErrorCategory.CONNECTION_LOST)
    )
    replacement = FakeAdapter()
    adapters = iter((released, replacement))
    events = EventRecorder()
    runtime = ControllerRuntime(
        adapter_factory=lambda: next(adapters),
        event_sink=events,
        clock=FakeClock(),
    )
    runtime.start()
    assert events.ready.wait(timeout=1.0)
    events.ready.clear()
    runtime.post(
        ConnectSaved(
            adapter_id="usb:0",
            bond_path=Path("bond.json"),
            timeout_seconds=30.0,
            colors=ControllerColorSettings(),
        )
    )

    assert events.error.wait(timeout=1.0)
    assert events.ready.wait(timeout=1.0)
    assert released.closed is True
    assert released.close_calls == 1
    events.connected.clear()
    runtime.post(
        ConnectSaved(
            adapter_id="usb:0",
            bond_path=Path("bond.json"),
            timeout_seconds=30.0,
            colors=ControllerColorSettings(),
        )
    )

    assert events.connected.wait(timeout=1.0)
    assert released.connect_calls == 1
    assert replacement.connect_calls == 1
    assert runtime.connection_state is ConnectionState.CONNECTED
    runtime.close()


def test_runtime_continues_shutdown_cleanup_after_neutral_failure() -> None:
    adapter = FakeAdapter(fail_on_apply_call=2)
    events = EventRecorder()
    runtime = ControllerRuntime(
        adapter_factory=lambda: adapter,
        event_sink=events,
        clock=FakeClock(),
    )
    runtime.start()
    assert events.ready.wait(timeout=1.0)
    runtime.post(
        ConnectSaved(
            adapter_id="usb:0",
            bond_path=Path("bond.json"),
            timeout_seconds=30.0,
            colors=ControllerColorSettings(),
        )
    )
    assert events.connected.wait(timeout=1.0)

    runtime.close()

    assert events.stopped.wait(timeout=1.0)
    assert runtime.is_alive is False
    assert adapter.close_thread_id is not None


def test_runtime_continues_shutdown_cleanup_after_disconnect_failure() -> None:
    adapter = FakeAdapter(disconnect_error=RuntimeError("disconnect failed"))
    events = EventRecorder()
    runtime = ControllerRuntime(
        adapter_factory=lambda: adapter,
        event_sink=events,
        clock=FakeClock(),
    )
    runtime.start()
    assert events.ready.wait(timeout=1.0)
    runtime.post(
        ConnectSaved(
            adapter_id="usb:0",
            bond_path=Path("bond.json"),
            timeout_seconds=30.0,
            colors=ControllerColorSettings(),
        )
    )
    assert events.connected.wait(timeout=1.0)

    runtime.close()

    assert events.stopped.wait(timeout=1.0)
    assert runtime.is_alive is False
    assert adapter.close_thread_id is not None
