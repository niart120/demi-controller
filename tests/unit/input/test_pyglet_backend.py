from dataclasses import dataclass, field

from pyglet.window import key, mouse

from demi.application.coordinator import CaptureCoordinator
from demi.domain.controller import ControllerFrame
from demi.domain.physical_input import KeySource, MouseButtonSource
from demi.input.publisher import InputPublisher
from demi.input.pyglet_backend import PygletInputBackend


@dataclass
class FakeClock:
    """Deterministic clock for backend tests."""

    now_ns: int = 1_000_000_000

    def monotonic_ns(self) -> int:
        """Return the configured monotonic timestamp."""
        return self.now_ns


@dataclass
class FakeSink:
    """In-memory frame sink for backend tests."""

    frames: list[ControllerFrame] = field(default_factory=list)

    def offer_frame(self, frame: ControllerFrame) -> None:
        """Store the offered frame."""
        self.frames.append(frame)


@dataclass
class FakeWindow:
    """Window port for backend tests."""

    exclusive_calls: list[bool] = field(default_factory=list)

    def set_exclusive_mouse(self, exclusive: bool = True) -> None:
        """Record exclusive mouse changes."""
        self.exclusive_calls.append(exclusive)


def make_backend() -> tuple[PygletInputBackend, CaptureCoordinator]:
    """Create a backend with a capture-enabled fake coordinator."""
    publisher = InputPublisher(clock=FakeClock(), sink=FakeSink())
    coordinator = CaptureCoordinator(publisher=publisher, window=FakeWindow())
    coordinator.start_capture()
    return PygletInputBackend(coordinator), coordinator


def test_key_events_normalize_symbol_and_modifiers() -> None:
    backend, coordinator = make_backend()

    backend.on_key_press(key.F, key.MOD_CTRL | key.MOD_SHIFT)

    assert coordinator.publisher.state.held_keys == {KeySource("F", frozenset({"CTRL", "SHIFT"}))}

    backend.on_key_release(key.F, key.MOD_CTRL | key.MOD_SHIFT)
    assert coordinator.publisher.state.held_keys == set()


def test_mouse_events_and_relative_motion_update_physical_state() -> None:
    backend, coordinator = make_backend()

    backend.on_mouse_press(0, 0, mouse.LEFT, 0)
    backend.on_mouse_press(0, 0, 8, 0)
    backend.on_mouse_motion(0, 0, 3, -2)

    assert coordinator.publisher.state.held_mouse_buttons == {
        MouseButtonSource("LEFT"),
        MouseButtonSource("BUTTON_4"),
    }
    assert coordinator.publisher.state.consume_mouse_motion() == (3, -2)


def test_events_outside_capture_are_ignored() -> None:
    publisher = InputPublisher(clock=FakeClock(), sink=FakeSink())
    coordinator = CaptureCoordinator(publisher=publisher, window=FakeWindow())
    backend = PygletInputBackend(coordinator)

    backend.on_key_press(key.F, 0)
    backend.on_mouse_press(0, 0, mouse.LEFT, 0)
    backend.on_mouse_motion(0, 0, 3, 2)

    assert publisher.state.held_keys == set()
    assert publisher.state.held_mouse_buttons == set()
    assert publisher.state.consume_mouse_motion() == (0.0, 0.0)
