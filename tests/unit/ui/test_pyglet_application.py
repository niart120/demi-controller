from collections.abc import Callable
from dataclasses import dataclass, field

from demi.application.coordinator import CaptureCoordinator
from demi.domain.controller import ControllerFrame
from demi.input.publisher import InputPublisher
from demi.input.pyglet_backend import PygletInputBackend
from demi.ui.controller_view import ControllerView
from demi.ui.status_bar import StatusBar
from demi.ui.toolbar import Toolbar
from demi.ui.window import PygletApplication


@dataclass
class FakeClock:
    """Clock scheduler recording the application callback."""

    now_ns: int = 1_000_000_000
    scheduled: list[tuple[Callable[[float], None], float]] = field(default_factory=list)
    unscheduled: list[Callable[[float], None]] = field(default_factory=list)

    def monotonic_ns(self) -> int:
        """Return the configured monotonic timestamp."""
        return self.now_ns

    def schedule_interval(self, callback: Callable[[float], None], interval: float) -> None:
        """Record one scheduled callback."""
        self.scheduled.append((callback, interval))

    def unschedule(self, callback: Callable[[float], None]) -> None:
        """Record an unschedule request."""
        self.unscheduled.append(callback)


@dataclass
class FakeWindow:
    """Window boundary recording event handlers and draw calls."""

    width: int = 960
    height: int = 640
    handlers: list[object] = field(default_factory=list)
    clear_calls: int = 0
    visible_calls: list[bool] = field(default_factory=list)

    def push_handlers(self, *objects: object) -> None:
        """Record installed event handlers."""
        self.handlers.extend(objects)

    def clear(self) -> None:
        """Record a clear request."""
        self.clear_calls += 1

    def set_visible(self, visible: bool = True) -> None:
        """Record visibility changes."""
        self.visible_calls.append(visible)

    def set_exclusive_mouse(self, exclusive: bool = True) -> None:
        """Satisfy the coordinator window port."""
        del exclusive


@dataclass
class FakeSink:
    """In-memory frame sink for application wiring tests."""

    frames: list[ControllerFrame] = field(default_factory=list)

    def offer_frame(self, frame: ControllerFrame) -> None:
        """Store the offered frame."""
        self.frames.append(frame)


def test_application_installs_backend_and_schedules_eight_millisecond_evaluation() -> None:
    sink = FakeSink()
    clock = FakeClock()
    publisher = InputPublisher(clock=clock, sink=sink)
    coordinator = CaptureCoordinator(publisher=publisher, window=FakeWindow())
    backend = PygletInputBackend(coordinator)
    window = FakeWindow()
    application = PygletApplication(
        window=window,
        coordinator=coordinator,
        backend=backend,
        view=ControllerView(),
        toolbar=Toolbar(),
        status_bar=StatusBar(),
        clock=clock,
    )

    application.start()

    assert application.started is True
    assert backend in window.handlers
    assert application in window.handlers
    assert len(clock.scheduled) == 1
    assert window.visible_calls == [True]
    callback, interval = clock.scheduled[0]
    assert interval == 0.008

    callback(0.008)
    assert coordinator.last_frame is sink.frames[-1]

    application.stop()
    assert application.started is False
    assert clock.unscheduled == [callback]
