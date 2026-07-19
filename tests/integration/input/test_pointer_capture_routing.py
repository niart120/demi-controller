from dataclasses import dataclass, field

from demi.application.coordinator import CaptureCoordinator
from demi.application.state import AppState
from demi.domain.controller import ControllerFrame, LogicalButton
from demi.input.publisher import InputPublisher


@dataclass
class FakeClock:
    """Provide deterministic evaluation timestamps."""

    now_ns: int = 1_000_000_000

    def monotonic_ns(self) -> int:
        """Return the current timestamp."""
        return self.now_ns


@dataclass
class FakeSink:
    """Record evaluated controller frames."""

    frames: list[ControllerFrame] = field(default_factory=list)

    def offer_frame(self, frame: ControllerFrame) -> None:
        """Store one evaluated frame."""
        self.frames.append(frame)


@dataclass
class FakePointerCapture:
    """Record pointer capture transitions."""

    calls: list[bool] = field(default_factory=list)

    def set_pointer_capture(self, enabled: bool) -> None:
        """Record one pointer transition."""
        self.calls.append(enabled)


def test_pointer_capture_start_preserves_keyboard_and_adds_mouse_input() -> None:
    clock = FakeClock()
    sink = FakeSink()
    pointer_capture = FakePointerCapture()
    publisher = InputPublisher(clock=clock, sink=sink)
    coordinator = CaptureCoordinator(
        publisher=publisher,
        pointer_capture=pointer_capture,
    )
    publisher.state.press_key("F")

    before_capture = coordinator.evaluate()
    assert before_capture.buttons == frozenset({LogicalButton.A})

    assert coordinator.start_capture() is True
    assert coordinator.last_frame is not None
    assert coordinator.last_frame.buttons == frozenset({LogicalButton.A})

    publisher.state.press_mouse_button("LEFT")
    publisher.state.add_mouse_motion(2.0, 0.0)
    clock.now_ns += 10_000_000
    captured = coordinator.evaluate()

    assert captured.buttons == frozenset({LogicalButton.A, LogicalButton.ZR})
    assert captured.gyro_rate.z_radians_per_second < 0.0
    assert pointer_capture.calls == [True]


def test_pointer_capture_stop_clears_mouse_but_preserves_keyboard() -> None:
    clock = FakeClock()
    sink = FakeSink()
    pointer_capture = FakePointerCapture()
    publisher = InputPublisher(clock=clock, sink=sink)
    coordinator = CaptureCoordinator(
        publisher=publisher,
        pointer_capture=pointer_capture,
    )
    publisher.state.press_key("F")
    assert coordinator.start_capture() is True
    publisher.state.press_mouse_button("LEFT")
    publisher.state.add_mouse_motion(2.0, 0.0)

    released = coordinator.stop_capture()

    assert released is not None
    assert released.buttons == frozenset({LogicalButton.A})
    assert released.gyro_rate.z_radians_per_second == 0.0
    assert publisher.state.held_keys
    assert publisher.state.held_mouse_buttons == set()
    assert coordinator.evaluate().buttons == frozenset({LogicalButton.A})
    assert pointer_capture.calls == [True, False]


def test_focus_loss_neutralizes_operational_keyboard_without_pointer_capture() -> None:
    clock = FakeClock()
    sink = FakeSink()
    publisher = InputPublisher(clock=clock, sink=sink)
    coordinator = CaptureCoordinator(
        publisher=publisher,
        pointer_capture=FakePointerCapture(),
    )
    publisher.state.press_key("F")
    assert coordinator.evaluate().buttons == frozenset({LogicalButton.A})

    neutral = coordinator.on_focus_lost()

    assert neutral is not None
    assert neutral.capture_active is False
    assert neutral.buttons == frozenset()
    assert neutral.gyro_rate.z_radians_per_second == 0.0
    assert neutral.accel_g.z_g == 1.0
    assert publisher.state.held_keys == set()
    assert coordinator.app_state is AppState.SUSPENDED
