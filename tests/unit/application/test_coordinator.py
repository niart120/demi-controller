from dataclasses import dataclass, field

from demi.application.coordinator import CaptureCoordinator
from demi.application.state import AppState
from demi.domain.controller import ControllerFrame, StickVector
from demi.domain.gamepad import GamepadButton, GamepadState
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

    def set_pointer_capture(self, enabled: bool) -> None:
        """Record or reject a pointer capture request."""
        if enabled and self.fail_on_enable:
            raise OSError
        self.exclusive_calls.append(enabled)


@dataclass
class FakeGamepadInput:
    """Gamepad port with an observable poll and shutdown boundary."""

    state: GamepadState = field(default_factory=GamepadState.neutral)
    poll_count: int = 0
    close_count: int = 0

    def poll(self) -> GamepadState:
        """Return the configured fake snapshot."""
        self.poll_count += 1
        return self.state

    def close(self) -> None:
        """Record backend shutdown."""
        self.close_count += 1


def make_coordinator(window: FakeWindow) -> tuple[CaptureCoordinator, FakeSink]:
    """Create a coordinator and its recording sink."""
    sink = FakeSink()
    publisher = InputPublisher(clock=FakeClock(), sink=sink)
    return CaptureCoordinator(publisher=publisher, pointer_capture=window), sink


def test_pointer_capture_start_and_stop_preserve_operational_keyboard() -> None:
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
    assert frame.capture_active is True
    assert frame.buttons
    assert coordinator.publisher.state.held_keys
    assert window.exclusive_calls == [True, False]


def test_capture_start_failure_keeps_idle_and_does_not_publish_input() -> None:
    window = FakeWindow(fail_on_enable=True)
    coordinator, sink = make_coordinator(window)

    assert coordinator.start_capture() is False

    assert coordinator.app_state is AppState.IDLE
    assert coordinator.capture_epoch == 1
    assert sink.frames == []


def test_configuration_transition_neutralizes_capture_without_auto_recapture() -> None:
    window = FakeWindow()
    coordinator, sink = make_coordinator(window)
    assert coordinator.start_capture() is True
    coordinator.publisher.state.press_key("F")

    assert coordinator.open_configuration() is True
    assert coordinator.app_state is AppState.CONFIGURING
    assert coordinator.last_frame is not None
    assert coordinator.last_frame.capture_active is False
    assert coordinator.last_frame.buttons == frozenset()
    assert coordinator.publisher.state.held_keys == set()

    assert coordinator.close_configuration() is True
    assert coordinator.app_state is AppState.IDLE
    assert coordinator.is_captured is False
    assert window.exclusive_calls == [True, False]
    assert len(sink.frames) == 2


def test_evaluation_tick_polls_gamepad_and_shutdown_closes_it() -> None:
    window = FakeWindow()
    sink = FakeSink()
    gamepad = FakeGamepadInput(
        GamepadState(
            connected=True,
            buttons=frozenset({GamepadButton.SOUTH}),
            left_stick=StickVector(0.0, 0.0),
            right_stick=StickVector(0.0, 0.0),
            left_trigger=0.0,
            right_trigger=0.0,
        )
    )
    coordinator = CaptureCoordinator(
        publisher=InputPublisher(clock=FakeClock(), sink=sink),
        pointer_capture=window,
        gamepad_input=gamepad,
    )

    frame = coordinator.evaluate()
    coordinator.begin_shutdown()
    coordinator.begin_shutdown()

    assert gamepad.poll_count == 1
    assert frame.buttons
    assert gamepad.close_count == 1
