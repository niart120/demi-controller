from dataclasses import dataclass, field

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeyEvent

from demi.application.coordinator import CaptureCoordinator
from demi.application.state import AppState
from demi.domain.controller import ControllerFrame
from demi.input.publisher import InputPublisher
from demi.input.qt_adapter import QtInputAdapter


@dataclass
class FakeClock:
    """Deterministic clock for capture integration tests."""

    now_ns: int = 1_000_000_000

    def monotonic_ns(self) -> int:
        """Return the configured monotonic timestamp."""
        return self.now_ns


@dataclass
class FakeSink:
    """Frame sink that records each capture transition."""

    frames: list[ControllerFrame] = field(default_factory=list)

    def offer_frame(self, frame: ControllerFrame) -> None:
        """Store one offered frame."""
        self.frames.append(frame)


@dataclass
class FakeWindow:
    """Pointer capture boundary that records enable and release requests."""

    exclusive_calls: list[bool] = field(default_factory=list)

    def set_pointer_capture(self, enabled: bool) -> None:
        """Record a pointer capture request."""
        self.exclusive_calls.append(enabled)


def test_f12_focus_dialog_and_shutdown_neutralize_qt_capture(
    qt_application: object,
) -> None:
    assert qt_application is not None
    clock = FakeClock()
    sink = FakeSink()
    window = FakeWindow()
    publisher = InputPublisher(clock=clock, sink=sink)
    coordinator = CaptureCoordinator(publisher=publisher, pointer_capture=window)
    adapter = QtInputAdapter(
        state=publisher.state,
        is_captured=lambda: coordinator.is_captured,
        on_stop_capture=coordinator.stop_capture,
        on_focus_lost=coordinator.on_focus_lost,
        on_focus_gained=coordinator.on_focus_gained,
        on_dialog_opened=coordinator.open_configuration,
    )
    target = QObject()

    assert coordinator.start_capture() is True
    publisher.state.press_key("F")
    publisher.state.add_mouse_motion(4.0, -2.0)

    adapter.eventFilter(target, _key_event(Qt.Key.Key_F12))

    assert coordinator.app_state is AppState.IDLE
    assert sink.frames[-1].capture_active is False
    assert sink.frames[-1].buttons == frozenset()
    assert publisher.state.held_keys == set()
    assert publisher.state.consume_mouse_motion() == (0.0, 0.0)

    assert coordinator.start_capture() is True
    publisher.state.press_key("F")
    adapter.eventFilter(target, QEvent(QEvent.Type.FocusOut))
    adapter.eventFilter(target, QEvent(QEvent.Type.FocusIn))

    assert coordinator.app_state is AppState.IDLE
    assert coordinator.is_captured is False
    assert sink.frames[-1].capture_active is False
    assert publisher.state.held_keys == set()

    assert coordinator.start_capture() is True
    publisher.state.press_key("F")
    adapter.on_dialog_opened()

    assert coordinator.app_state is AppState.CONFIGURING
    assert sink.frames[-1].capture_active is False
    assert publisher.state.held_keys == set()

    assert coordinator.close_configuration() is True
    assert coordinator.start_capture() is True
    publisher.state.press_key("F")
    shutdown_frame = coordinator.begin_shutdown()

    assert coordinator.app_state is AppState.SHUTTING_DOWN
    assert shutdown_frame is not None
    assert shutdown_frame.capture_active is False
    assert shutdown_frame.buttons == frozenset()
    assert publisher.state.held_keys == set()
    assert window.exclusive_calls == [True, False, True, False, True, False, True, False]


def _key_event(key: Qt.Key) -> QKeyEvent:
    return QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)
