from dataclasses import dataclass, field

import pytest
from PySide6.QtCore import QAbstractNativeEventFilter, QByteArray

from demi.platform.windows_raw_input import (
    HID_USAGE_GENERIC_MOUSE,
    HID_USAGE_PAGE_GENERIC,
    RIDEV_INPUTSINK,
    RIDEV_NOLEGACY,
    RIDEV_REMOVE,
    RawInputDevice,
    RawInputRegistrationConflictError,
    WindowsRawInputBackend,
    WindowsRawInputFilter,
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
