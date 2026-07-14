from dataclasses import dataclass, field

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QPointF, Qt
from PySide6.QtGui import QFocusEvent, QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QPushButton

from demi.app import WindowSpec
from demi.application.coordinator import CaptureCoordinator
from demi.application.state import AppState
from demi.domain.controller import ControllerFrame
from demi.input.publisher import InputPublisher
from demi.input.qt_adapter import QtInputAdapter
from demi.platform.windows_raw_input import (
    HID_USAGE_GENERIC_MOUSE,
    HID_USAGE_PAGE_GENERIC,
    RawInputDevice,
    WindowsRawInputBackend,
)
from demi.ui.main_window import MainWindow


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


@dataclass
class FakeRawInputRegistrar:
    """Record native registration without calling the Windows API."""

    devices: list[RawInputDevice] = field(default_factory=list)

    def register(self, device: RawInputDevice) -> None:
        """Store one requested Raw Input device registration."""
        self.devices.append(device)


class RecordingButton(QPushButton):
    """Keep Qt event delivery visible while an application filter is active."""

    def __init__(self) -> None:
        """Create a button with an empty event history."""
        super().__init__("確認")
        self.received_event_types: list[QEvent.Type] = []

    def event(self, event: QEvent) -> bool:
        """Record normal Qt delivery before delegating to the standard button."""
        self.received_event_types.append(event.type())
        return super().event(event)


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


def test_raw_input_capture_keeps_qt_button_focus_and_dialog_events(
    qt_application: object,
) -> None:
    assert qt_application is not None
    clock = FakeClock()
    sink = FakeSink()
    publisher = InputPublisher(clock=clock, sink=sink)
    window = MainWindow(WindowSpec(width=960, height=640, maximized=False))
    button = RecordingButton()
    window.setCentralWidget(button)
    registrar = FakeRawInputRegistrar()
    backend = WindowsRawInputBackend(registrar=registrar)
    coordinator = CaptureCoordinator(
        publisher=publisher,
        pointer_capture=window,
        relative_pointer_capture=window,
    )
    window.configure_input(publisher=publisher, coordinator=coordinator, raw_input_backend=backend)

    assert coordinator.start_capture() is True
    assert registrar.devices[0].usage_page == HID_USAGE_PAGE_GENERIC
    assert registrar.devices[0].usage == HID_USAGE_GENERIC_MOUSE
    assert registrar.devices[0].flags == 0

    clicks: list[bool] = []
    button.clicked.connect(lambda: clicks.append(True))
    QCoreApplication.sendEvent(button, _mouse_event(QEvent.Type.MouseButtonPress))
    QCoreApplication.sendEvent(button, _mouse_event(QEvent.Type.MouseButtonRelease))

    assert clicks == [True]
    assert QEvent.Type.MouseButtonPress in button.received_event_types
    assert QEvent.Type.MouseButtonRelease in button.received_event_types
    assert publisher.state.held_mouse_buttons == set()

    QCoreApplication.sendEvent(button, QFocusEvent(QEvent.Type.FocusOut))

    assert QEvent.Type.FocusOut in button.received_event_types
    assert coordinator.app_state is AppState.CAPTURED
    QCoreApplication.sendEvent(window, QEvent(QEvent.Type.WindowDeactivate))
    assert coordinator.app_state is AppState.SUSPENDED
    QCoreApplication.sendEvent(window, QEvent(QEvent.Type.WindowActivate))
    assert coordinator.app_state is AppState.IDLE
    assert coordinator.start_capture() is True

    window.on_dialog_opened()

    assert coordinator.app_state is AppState.CONFIGURING
    coordinator.begin_shutdown()


def _key_event(key: Qt.Key) -> QKeyEvent:
    return QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)


def _mouse_event(event_type: QEvent.Type) -> QMouseEvent:
    buttons = (
        Qt.MouseButton.LeftButton
        if event_type is QEvent.Type.MouseButtonPress
        else Qt.MouseButton.NoButton
    )
    return QMouseEvent(
        event_type,
        QPointF(10.0, 10.0),
        QPointF(10.0, 10.0),
        QPointF(10.0, 10.0),
        Qt.MouseButton.LeftButton,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )
