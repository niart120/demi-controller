from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, get_ident

from demi.controller.events import (
    AdapterDescriptor,
    ConnectionChanged,
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
    thread_ids: list[int] = field(default_factory=list)

    def emit(self, event: RuntimeEvent) -> None:
        """Record an event and signal lifecycle milestones."""
        self.events.append(event)
        self.thread_ids.append(get_ident())
        if isinstance(event, ConnectionChanged) and event.state.value == "ready":
            self.ready.set()
        if isinstance(event, RuntimeStopped):
            self.stopped.set()


@dataclass
class FakeAdapter:
    """Minimal async adapter owned by the runtime worker."""

    close_thread_id: int | None = None

    async def discover_adapters(self) -> tuple[AdapterDescriptor, ...]:
        """Return no adapters for the lifecycle test."""
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

    async def recreate_with_colors(self, colors: ControllerColorSettings) -> None:
        """Complete a fake color recreation."""
        del colors

    async def apply_frame(self, frame: ControllerFrame) -> None:
        """Accept a frame without hardware."""
        del frame

    async def close(self) -> None:
        """Record the worker thread that closed the adapter."""
        self.close_thread_id = get_ident()


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
