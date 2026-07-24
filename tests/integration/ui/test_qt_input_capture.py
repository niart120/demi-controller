from dataclasses import dataclass, field

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QObject, QPointF, Qt
from PySide6.QtGui import QFocusEvent, QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QPushButton

from demi.app import WindowSpec
from demi.application.coordinator import CaptureCoordinator, CaptureFailure
from demi.application.state import AppState
from demi.domain.controller import ControllerFrame, LogicalButton
from demi.domain.settings import MouseSettings
from demi.input.publisher import InputPublisher
from demi.input.qt_adapter import QtInputAdapter
from demi.platform.windows_mouse_hook import (
    WM_LBUTTONDOWN,
    WM_LBUTTONUP,
    WindowsMouseInputSuppressor,
)
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


@pytest.mark.parametrize("mouse_gyro_enabled", [False, True])
def test_keyboard_input_reaches_evaluated_frame_without_pointer_capture(
    qt_application: object,
    mouse_gyro_enabled: bool,
) -> None:
    """Keep keyboard mappings active whether or not mouse gyro is enabled."""
    assert qt_application is not None
    clock = FakeClock()
    sink = FakeSink()
    publisher = InputPublisher(
        clock=clock,
        sink=sink,
        mouse_settings=MouseSettings(gyro_enabled=mouse_gyro_enabled),
    )
    window = MainWindow(WindowSpec(width=960, height=640, maximized=False))
    coordinator = CaptureCoordinator(publisher=publisher, pointer_capture=window)
    window.configure_input(publisher=publisher, coordinator=coordinator)

    QCoreApplication.sendEvent(window, _key_event(Qt.Key.Key_F))
    clock.now_ns += 8_000_000
    frame = window.evaluate_input()

    assert coordinator.is_captured is False
    assert frame.capture_active is True
    assert frame.pointer_capture_active is False
    assert frame.buttons == frozenset({LogicalButton.A})

    QCoreApplication.sendEvent(
        window,
        QKeyEvent(QEvent.Type.KeyRelease, Qt.Key.Key_F, Qt.KeyboardModifier.NoModifier),
    )
    clock.now_ns += 8_000_000
    assert window.evaluate_input().buttons == frozenset()
    coordinator.begin_shutdown()


def test_f5_toggles_pointer_while_focus_dialog_and_shutdown_neutralize_all_input(
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
        on_toggle_capture=coordinator.toggle_capture,
        on_focus_lost=coordinator.on_focus_lost,
        on_focus_gained=coordinator.on_focus_gained,
        on_dialog_opened=coordinator.open_configuration,
    )
    target = QObject()

    assert coordinator.start_capture() is True
    publisher.state.press_key("F")
    publisher.state.add_mouse_motion(4.0, -2.0)

    adapter.eventFilter(target, _key_event(Qt.Key.Key_F5))

    assert coordinator.app_state is AppState.IDLE
    assert sink.frames[-1].capture_active is True
    assert sink.frames[-1].buttons == frozenset({LogicalButton.A})
    assert publisher.state.held_keys
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


def test_capture_suppresses_external_mouse_delivery_and_preserves_button_mapping(
    qt_application: object,
) -> None:
    assert qt_application is not None
    clock = FakeClock()
    sink = FakeSink()
    publisher = InputPublisher(clock=clock, sink=sink)
    window = MainWindow(WindowSpec(width=960, height=640, maximized=False))
    registrar = FakeRawInputRegistrar()
    raw_input = WindowsRawInputBackend(registrar=registrar)
    hook_registrar = FakeMouseHookRegistrar()
    suppressor = WindowsMouseInputSuppressor(
        registrar=hook_registrar,
        on_button_pressed=publisher.state.press_mouse_button,
        on_button_released=publisher.state.release_mouse_button,
    )
    coordinator = CaptureCoordinator(
        publisher=publisher,
        pointer_capture=window,
        relative_pointer_capture=window,
    )
    window.configure_input(
        publisher=publisher,
        coordinator=coordinator,
        raw_input_backend=raw_input,
        mouse_input_suppressor=suppressor,
    )

    assert coordinator.start_capture() is True
    assert suppressor.handle_message(WM_LBUTTONDOWN) is True
    assert publisher.state.is_source_active("MOUSE:LEFT") is True
    assert suppressor.handle_message(WM_LBUTTONUP) is True
    assert publisher.state.is_source_active("MOUSE:LEFT") is False

    window._mouse_input_toggle_action.trigger()

    assert coordinator.app_state is AppState.IDLE
    assert suppressor.active is False
    assert hook_registrar.removed_handles == [0x1234]


def test_mouse_suppression_releases_for_focus_dialog_and_shutdown(
    qt_application: object,
) -> None:
    assert qt_application is not None
    publisher = InputPublisher(clock=FakeClock(), sink=FakeSink())
    window = MainWindow(WindowSpec(width=960, height=640, maximized=False))
    hook_registrar = FakeMouseHookRegistrar()
    suppressor = WindowsMouseInputSuppressor(registrar=hook_registrar)
    coordinator = CaptureCoordinator(publisher=publisher, pointer_capture=window)
    window.configure_input(
        publisher=publisher,
        coordinator=coordinator,
        mouse_input_suppressor=suppressor,
    )

    assert coordinator.start_capture() is True
    assert coordinator.on_focus_lost() is not None
    assert coordinator.app_state is AppState.SUSPENDED
    assert suppressor.active is False

    coordinator.on_focus_gained()
    assert coordinator.start_capture() is True
    window.on_dialog_opened()
    assert coordinator.app_state is AppState.CONFIGURING
    assert suppressor.active is False

    assert coordinator.close_configuration() is True
    assert coordinator.start_capture() is True
    assert coordinator.begin_shutdown() is not None
    assert suppressor.active is False
    assert hook_registrar.removed_handles == [0x1234, 0x1234, 0x1234]


@dataclass
class FakeMouseHookRegistrar:
    """Record low-level hook registration without calling Win32."""

    callbacks: list[object] = field(default_factory=list)
    removed_handles: list[int] = field(default_factory=list)

    def install(self, callback: object) -> int:
        """Store the supplied callback and return a stable hook handle."""
        self.callbacks.append(callback)
        return 0x1234

    def remove(self, handle: int) -> None:
        """Record one logical hook removal."""
        self.removed_handles.append(handle)


class FailingMouseHookRegistrar:
    """Reject mouse-hook installation without exposing a Windows API."""

    def install(self, callback: object) -> int:
        """Reject the registration attempt."""
        del callback
        raise OSError

    def remove(self, handle: int) -> None:
        """Accept cleanup after a failed installation."""
        del handle


def test_mouse_hook_registration_failure_rolls_back_capture(
    qt_application: object,
) -> None:
    assert qt_application is not None
    publisher = InputPublisher(clock=FakeClock(), sink=FakeSink())
    window = MainWindow(WindowSpec(width=960, height=640, maximized=False))
    raw_input = WindowsRawInputBackend(registrar=FakeRawInputRegistrar())
    suppressor = WindowsMouseInputSuppressor(registrar=FailingMouseHookRegistrar())
    coordinator = CaptureCoordinator(
        publisher=publisher,
        pointer_capture=window,
        relative_pointer_capture=window,
    )
    window.configure_input(
        publisher=publisher,
        coordinator=coordinator,
        raw_input_backend=raw_input,
        mouse_input_suppressor=suppressor,
    )

    assert coordinator.start_capture() is False
    assert coordinator.app_state is AppState.IDLE
    assert coordinator.capture_failure is CaptureFailure.POINTER_CAPTURE
    assert suppressor.active is False


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
