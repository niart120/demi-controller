"""Integration tests for application-driven runtime cancellation."""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, current_thread
from typing import TYPE_CHECKING, cast

from demi.application.shutdown import ApplicationShutdownCoordinator
from demi.controller.commands import ConnectSaved
from demi.controller.events import AdapterDescriptor, RuntimeEvent, RuntimeStopped
from demi.controller.runtime import ControllerRuntime
from demi.domain.controller import ControllerFrame
from demi.domain.settings import AppSettings, ControllerColorSettings

if TYPE_CHECKING:
    from demi.application.coordinator import CaptureCoordinator


@dataclass
class FakeClock:
    """Provide a stable worker timestamp."""

    def monotonic_ns(self) -> int:
        """Return a stable monotonic value."""
        return 1_000_000_000


@dataclass
class RecordingEventSink:
    """Record runtime events emitted by the worker."""

    events: list[RuntimeEvent] = field(default_factory=list)

    def emit(self, event: RuntimeEvent) -> None:
        """Append one event."""
        self.events.append(event)


@dataclass
class WaitingAdapter:
    """Observe worker daemon state and wait for connection cancellation."""

    connect_started: Event = field(default_factory=Event)
    connect_cancelled: Event = field(default_factory=Event)
    worker_daemon: bool | None = None

    async def discover_adapters(self) -> tuple[AdapterDescriptor, ...]:
        """Return no adapters."""
        return ()

    async def connect_saved(
        self,
        adapter_id: str,
        bond_path: Path,
        timeout_seconds: float,
        colors: ControllerColorSettings,
    ) -> None:
        """Wait until application shutdown cancels this operation."""
        del adapter_id, bond_path, timeout_seconds, colors
        self.worker_daemon = current_thread().daemon
        self.connect_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.connect_cancelled.set()
            raise

    async def start_pairing(
        self,
        adapter_id: str,
        bond_path: Path,
        timeout_seconds: float,
        colors: ControllerColorSettings,
    ) -> None:
        """Provide the adapter protocol operation."""
        del adapter_id, bond_path, timeout_seconds, colors

    async def disconnect(self) -> None:
        """Complete fake disconnect."""

    async def recreate_with_colors(self, colors: ControllerColorSettings) -> None:
        """Provide the adapter protocol operation."""
        del colors

    async def send_frame(self, frame: ControllerFrame) -> None:
        """Accept cleanup rest state."""
        del frame

    async def close(self) -> None:
        """Complete adapter cleanup."""


@dataclass
class FakeCapture:
    """Record application shutdown ownership transitions."""

    timeline: list[str]

    def begin_shutdown(self) -> None:
        """Record shutdown start."""
        self.timeline.append("capture.begin_shutdown")

    def finish_shutdown(self) -> None:
        """Record shutdown completion."""
        self.timeline.append("capture.finish_shutdown")


@dataclass
class FakeRepository:
    """Provide the settings persistence boundary."""

    def save(self, settings: AppSettings) -> None:
        """Accept a settings snapshot when one is supplied."""
        del settings


def test_application_shutdown_cancels_connection_and_joins_non_daemon_worker() -> None:
    adapter = WaitingAdapter()
    event_sink = RecordingEventSink()
    runtime = ControllerRuntime(
        adapter_factory=lambda: adapter,
        event_sink=event_sink,
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
    timeline: list[str] = []
    shutdown = ApplicationShutdownCoordinator(
        capture=cast("CaptureCoordinator", FakeCapture(timeline)),
        runtime=runtime,
        repository=FakeRepository(),
        settings_provider=AppSettings.default,
        window_state_provider=lambda: None,
    )

    assert shutdown.request() is True

    assert adapter.worker_daemon is False
    assert adapter.connect_cancelled.is_set()
    assert runtime.is_alive is False
    assert timeline == ["capture.begin_shutdown", "capture.finish_shutdown"]
    assert sum(isinstance(event, RuntimeStopped) for event in event_sink.events) == 1
