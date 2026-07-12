from dataclasses import dataclass, field

from demi.application.coordinator import CaptureCoordinator
from demi.application.state import AppState
from demi.domain.controller import ControllerFrame
from demi.input.publisher import InputPublisher


@dataclass
class FakeClock:
    """Deterministic clock for coordinator tests."""

    now_ns: int = 1_000_000_000

    def monotonic_ns(self) -> int:
        """Return the configured monotonic timestamp."""
        return self.now_ns


@dataclass
class FakeSink:
    """In-memory frame sink for coordinator tests."""

    frames: list[ControllerFrame] = field(default_factory=list)

    def offer_frame(self, frame: ControllerFrame) -> None:
        """Store the offered frame."""
        self.frames.append(frame)


@dataclass
class FakeWindow:
    """Window port recording exclusive mouse changes."""

    exclusive_calls: list[bool] = field(default_factory=list)
    fail_on_enable: bool = False

    def set_exclusive_mouse(self, exclusive: bool = True) -> None:
        """Record or reject an exclusive mouse request."""
        if exclusive and self.fail_on_enable:
            raise OSError
        self.exclusive_calls.append(exclusive)


def make_coordinator(window: FakeWindow) -> tuple[CaptureCoordinator, FakeSink]:
    """Create a coordinator and its recording sink."""
    sink = FakeSink()
    publisher = InputPublisher(clock=FakeClock(), sink=sink)
    return CaptureCoordinator(publisher=publisher, window=window), sink


def test_capture_start_and_stop_emit_epoch_neutrals_and_clear_state() -> None:
    window = FakeWindow()
    coordinator, sink = make_coordinator(window)

    assert coordinator.start_capture() is True
    assert coordinator.app_state is AppState.CAPTURED
    assert coordinator.capture_epoch == 1
    assert sink.frames[-1].capture_active is True

    coordinator.publisher.state.press_key("F")
    frame = coordinator.stop_capture()

    assert frame is not None
    assert coordinator.app_state is AppState.IDLE
    assert coordinator.capture_epoch == 2
    assert frame.capture_active is False
    assert frame.buttons == frozenset()
    assert coordinator.publisher.state.held_keys == set()
    assert window.exclusive_calls == [True, False]


def test_capture_start_failure_keeps_idle_and_does_not_publish_input() -> None:
    window = FakeWindow(fail_on_enable=True)
    coordinator, sink = make_coordinator(window)

    assert coordinator.start_capture() is False

    assert coordinator.app_state is AppState.IDLE
    assert coordinator.capture_epoch == 1
    assert sink.frames == []
