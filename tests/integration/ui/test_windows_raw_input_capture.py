from dataclasses import dataclass, field

from PySide6.QtCore import QByteArray

from demi.domain.controller import ControllerFrame
from demi.input.publisher import InputPublisher
from demi.platform.windows_raw_input import (
    MOUSE_MOVE_ABSOLUTE,
    WM_INPUT,
    NativeWindowsMessage,
    RawInputDevice,
    RawMousePacket,
    WindowsRawInputBackend,
)


@dataclass
class FakeClock:
    """Provide deterministic input evaluation times."""

    now_ns: int = 1_000_000_000

    def monotonic_ns(self) -> int:
        """Return the configured monotonic timestamp."""
        return self.now_ns


@dataclass
class RecordingFrameSink:
    """Store frames produced by the integration boundary."""

    frames: list[ControllerFrame] = field(default_factory=list)

    def offer_frame(self, frame: ControllerFrame) -> None:
        """Store one evaluated frame."""
        self.frames.append(frame)


@dataclass
class FakeRawInputRegistrar:
    """Accept registrations without invoking the Windows API."""

    devices: list[RawInputDevice] = field(default_factory=list)

    def register(self, device: RawInputDevice) -> None:
        """Record one logical raw-input device selection."""
        self.devices.append(device)


@dataclass
class FakeNativeMessageReader:
    """Translate fixture addresses into native message values."""

    messages: dict[int, NativeWindowsMessage]

    def read(self, message_address: int) -> NativeWindowsMessage:
        """Return the native message represented by an address fixture."""
        return self.messages[message_address]


@dataclass
class FakeRawInputReader:
    """Translate raw-input handles into decoded mouse packets."""

    packets: dict[int, RawMousePacket]

    def read_mouse(self, raw_input_handle: int) -> RawMousePacket | None:
        """Return the decoded packet represented by a handle fixture."""
        return self.packets[raw_input_handle]


def test_absolute_outside_stale_and_other_window_raw_events_do_not_reach_a_frame() -> None:
    clock = FakeClock()
    publisher = InputPublisher(clock=clock, sink=RecordingFrameSink())
    expected_clock = FakeClock()
    expected_publisher = InputPublisher(clock=expected_clock, sink=RecordingFrameSink())
    messages = FakeNativeMessageReader(
        {
            1: NativeWindowsMessage(message=WM_INPUT, l_param=101, window_handle=0x1234),
            2: NativeWindowsMessage(message=WM_INPUT, l_param=102, window_handle=0x1234),
            3: NativeWindowsMessage(message=WM_INPUT, l_param=103, window_handle=0x9876),
            4: NativeWindowsMessage(message=WM_INPUT, l_param=104, window_handle=0x1234),
        }
    )
    packets = FakeRawInputReader(
        {
            101: RawMousePacket(flags=0, dx=4, dy=-2),
            102: RawMousePacket(flags=MOUSE_MOVE_ABSOLUTE, dx=500, dy=500),
            103: RawMousePacket(flags=0, dx=300, dy=300),
            104: RawMousePacket(flags=0, dx=200, dy=200),
        }
    )
    outside_capture = WindowsRawInputBackend(
        registrar=FakeRawInputRegistrar(),
        on_relative_motion=publisher.state.add_mouse_motion,
        message_reader=messages,
        raw_input_reader=packets,
    )
    active_capture = WindowsRawInputBackend(
        registrar=FakeRawInputRegistrar(),
        on_relative_motion=publisher.state.add_mouse_motion,
        message_reader=messages,
        raw_input_reader=packets,
    )

    publisher.publish(capture_active=True, capture_epoch=2)
    expected_publisher.publish(capture_active=True, capture_epoch=2)
    expected_publisher.state.add_mouse_motion(4.0, -2.0)

    assert (
        outside_capture.handle_native_event(
            QByteArray(b"windows_generic_MSG"),
            1,
            capture_epoch=2,
        )
        is False
    )

    active_capture.start_capture(0x1234, capture_epoch=2)
    assert active_capture.nativeEventFilter(QByteArray(b"windows_generic_MSG"), 1) is False
    assert (
        active_capture.handle_native_event(
            QByteArray(b"windows_generic_MSG"),
            2,
            capture_epoch=2,
        )
        is False
    )
    assert (
        active_capture.handle_native_event(
            QByteArray(b"windows_generic_MSG"),
            3,
            capture_epoch=2,
        )
        is False
    )
    assert (
        active_capture.handle_native_event(
            QByteArray(b"windows_generic_MSG"),
            4,
            capture_epoch=1,
        )
        is False
    )

    assert (publisher.state.accumulated_dx, publisher.state.accumulated_dy) == (4.0, -2.0)

    clock.now_ns += 8_000_000
    expected_clock.now_ns += 8_000_000
    frame = publisher.publish(capture_active=True, capture_epoch=2)
    expected_frame = expected_publisher.publish(capture_active=True, capture_epoch=2)

    assert frame == expected_frame
    assert publisher.state.consume_mouse_motion() == (0.0, 0.0)
