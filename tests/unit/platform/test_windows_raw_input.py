import ctypes
from dataclasses import dataclass, field

import pytest
from PySide6.QtCore import QAbstractNativeEventFilter, QByteArray

from demi.domain.controller import ControllerFrame
from demi.input.publisher import InputPublisher
from demi.platform.windows_raw_input import (
    HID_USAGE_GENERIC_MOUSE,
    HID_USAGE_PAGE_GENERIC,
    RIDEV_INPUTSINK,
    RIDEV_NOLEGACY,
    RIDEV_REMOVE,
    RIM_TYPEMOUSE,
    WM_INPUT,
    NativeWindowsMessage,
    RawInputDevice,
    RawInputRegistrationConflictError,
    RawMousePacket,
    WindowsRawInputBackend,
    WindowsRawInputFilter,
    _NativeRawInputHeader,
    _NativeRawMouse,
    decode_raw_mouse_payload,
)


def test_native_event_filter_leaves_non_raw_messages_for_qt() -> None:
    native_filter = WindowsRawInputFilter()

    assert isinstance(native_filter, QAbstractNativeEventFilter)
    assert (
        native_filter.nativeEventFilter(
            QByteArray(b"windows_generic_MSG"),
            0,
        )
        is False
    )
    assert native_filter.nativeEventFilter(QByteArray(b"xcb_generic_event_t"), 0) is False


@dataclass
class FakeRawInputRegistrar:
    """Record the device registrations requested by one raw-input backend."""

    devices: list[RawInputDevice] = field(default_factory=list)

    def register(self, device: RawInputDevice) -> None:
        """Record one logical Win32 registration payload."""
        self.devices.append(device)


@dataclass
class FakeClock:
    """Provide the scheduled input evaluation time for a platform test."""

    now_ns: int = 1_000_000_000

    def monotonic_ns(self) -> int:
        """Return the configured monotonic timestamp."""
        return self.now_ns


@dataclass
class RecordingFrameSink:
    """Keep frames published at the input evaluation boundary."""

    frames: list[ControllerFrame] = field(default_factory=list)

    def offer_frame(self, frame: ControllerFrame) -> None:
        """Record one evaluated frame."""
        self.frames.append(frame)


@dataclass
class FakeNativeMessageReader:
    """Translate stable fixture addresses into native Windows message values."""

    messages: dict[int, NativeWindowsMessage]

    def read(self, message_address: int) -> NativeWindowsMessage:
        """Return the message represented by a fixture address."""
        return self.messages[message_address]


@dataclass
class FixtureRawInputReader:
    """Decode copied Win32 structure fixtures by raw-input handle."""

    payloads: dict[int, bytes]

    def read_mouse(self, raw_input_handle: int) -> RawMousePacket | None:
        """Decode the copied raw-input payload for one fixture handle."""
        return decode_raw_mouse_payload(self.payloads[raw_input_handle])


def _raw_mouse_payload(*, dx: int, dy: int, flags: int = 0) -> bytes:
    header_size = ctypes.sizeof(_NativeRawInputHeader)
    mouse_size = ctypes.sizeof(_NativeRawMouse)
    header = _NativeRawInputHeader(RIM_TYPEMOUSE, header_size + mouse_size, None, 0)
    mouse = _NativeRawMouse(flags, 0, 0, 0, dx, dy, 0)
    return bytes(header) + bytes(mouse)


def test_raw_input_capture_registers_one_foreground_window_then_removes_it() -> None:
    registrar = FakeRawInputRegistrar()
    backend = WindowsRawInputBackend(registrar=registrar)

    backend.start_capture(0x1234)
    backend.start_capture(0x1234)

    assert registrar.devices == [
        RawInputDevice(
            usage_page=HID_USAGE_PAGE_GENERIC,
            usage=HID_USAGE_GENERIC_MOUSE,
            flags=0,
            target_window_handle=0x1234,
        )
    ]
    assert registrar.devices[0].flags & (RIDEV_INPUTSINK | RIDEV_NOLEGACY) == 0

    with pytest.raises(RawInputRegistrationConflictError):
        backend.start_capture(0x5678)

    backend.stop_capture()
    backend.stop_capture()

    assert registrar.devices[-1] == RawInputDevice(
        usage_page=HID_USAGE_PAGE_GENERIC,
        usage=HID_USAGE_GENERIC_MOUSE,
        flags=RIDEV_REMOVE,
        target_window_handle=None,
    )
    assert len(registrar.devices) == 2


def test_relative_wm_input_deltas_accumulate_then_one_evaluation_consumes_them() -> None:
    clock = FakeClock()
    sink = RecordingFrameSink()
    publisher = InputPublisher(clock=clock, sink=sink)
    backend = WindowsRawInputBackend(
        registrar=FakeRawInputRegistrar(),
        on_relative_motion=publisher.state.add_mouse_motion,
        message_reader=FakeNativeMessageReader(
            {
                1: NativeWindowsMessage(message=WM_INPUT, l_param=101, window_handle=0x1234),
                2: NativeWindowsMessage(message=WM_INPUT, l_param=102, window_handle=0x1234),
                3: NativeWindowsMessage(message=WM_INPUT, l_param=103, window_handle=0x1234),
            }
        ),
        raw_input_reader=FixtureRawInputReader(
            {
                101: _raw_mouse_payload(dx=4, dy=-2),
                102: _raw_mouse_payload(dx=-1, dy=6),
                103: _raw_mouse_payload(dx=3, dy=-5),
            }
        ),
    )
    backend.start_capture(0x1234)
    publisher.publish(capture_active=True, capture_epoch=1)

    for address in (1, 2, 3):
        assert backend.nativeEventFilter(QByteArray(b"windows_generic_MSG"), address) is False

    assert (publisher.state.accumulated_dx, publisher.state.accumulated_dy) == (6.0, -1.0)

    clock.now_ns += 8_000_000
    publisher.publish(capture_active=True, capture_epoch=1)

    assert publisher.state.consume_mouse_motion() == (0.0, 0.0)
    publisher.publish(capture_active=True, capture_epoch=1)
    assert publisher.state.consume_mouse_motion() == (0.0, 0.0)
