from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, get_ident

from demi.application.state import ConnectionState
from demi.controller.adapter import ControllerAdapterError
from demi.controller.commands import ConnectSaved, DiscoverAdapters, RecreateWithColors
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
from demi.domain.controller import ControllerFrame
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

    async def disconnect(self) -> None:
        """Complete a fake disconnect."""
        if self.disconnect_error is not None:
            raise self.disconnect_error

    async def recreate_with_colors(self, colors: ControllerColorSettings) -> None:
        """Complete a fake color recreation."""
        del colors
        self.recreate_calls += 1
        if self.recreate_error is not None:
            raise self.recreate_error

    async def apply_frame(self, frame: ControllerFrame) -> None:
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
