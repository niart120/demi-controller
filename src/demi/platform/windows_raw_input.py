"""Keep Windows native messages and raw-input registration at the platform boundary."""

import ctypes
import sys
from dataclasses import dataclass
from typing import Protocol

from PySide6.QtCore import QAbstractNativeEventFilter, QByteArray

HID_USAGE_PAGE_GENERIC = 0x01
HID_USAGE_GENERIC_MOUSE = 0x02
RIDEV_REMOVE = 0x00000001
RIDEV_NOLEGACY = 0x00000030
RIDEV_INPUTSINK = 0x00000100

type NativeEventType = QByteArray | bytes | bytearray | memoryview


class RawInputConfigurationError(ValueError):
    """Reject a raw-input request that cannot be represented safely."""


class RawInputRegistrationConflictError(RuntimeError):
    """Reject registration of a second main-window receiver in one backend."""


class RawInputUnavailableError(OSError):
    """Report that the current platform does not expose Windows Raw Input."""


@dataclass(frozen=True, slots=True)
class RawInputDevice:
    """Represent one framework-independent raw-input device registration request.

    Args:
        usage_page: HID usage page selected for the device collection.
        usage: HID usage selected within ``usage_page``.
        flags: Win32 registration flags, including ``RIDEV_REMOVE`` on release.
        target_window_handle: Main-window handle, or ``None`` for removal.

    Raises:
        RawInputConfigurationError: If a value cannot be represented by Win32
            or removal retains a target handle.
    """

    usage_page: int
    usage: int
    flags: int
    target_window_handle: int | None

    def __post_init__(self) -> None:
        """Reject impossible Win32 values before crossing the native boundary."""
        if (
            isinstance(self.usage_page, bool)
            or not isinstance(self.usage_page, int)
            or not 0 <= self.usage_page <= 0xFFFF
            or isinstance(self.usage, bool)
            or not isinstance(self.usage, int)
            or not 0 <= self.usage <= 0xFFFF
        ):
            raise RawInputConfigurationError
        if isinstance(self.flags, bool) or not isinstance(self.flags, int) or self.flags < 0:
            raise RawInputConfigurationError
        target = self.target_window_handle
        if target is not None and (
            isinstance(target, bool) or not isinstance(target, int) or target <= 0
        ):
            raise RawInputConfigurationError
        if self.flags & RIDEV_REMOVE and target is not None:
            raise RawInputConfigurationError


class RawInputRegistrar(Protocol):
    """Perform one logical raw-input registration at the Windows API boundary."""

    def register(self, device: RawInputDevice) -> None:
        """Register or remove the supplied raw-input device selection."""


class _NativeRawInputDevice(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", ctypes.c_ushort),
        ("usUsage", ctypes.c_ushort),
        ("dwFlags", ctypes.c_uint32),
        ("hwndTarget", ctypes.c_void_p),
    ]


class CtypesRawInputRegistrar:
    """Call ``RegisterRawInputDevices`` only after a Windows capture request."""

    def register(self, device: RawInputDevice) -> None:
        """Submit one logical device registration to Win32.

        Args:
            device: Validated mouse usage, flags, and optional target handle.

        Raises:
            RawInputUnavailableError: If the current platform is not Windows.
            OSError: If Win32 rejects the request.
        """
        if sys.platform != "win32":
            raise RawInputUnavailableError
        native_device = _NativeRawInputDevice(
            device.usage_page,
            device.usage,
            device.flags,
            device.target_window_handle,
        )
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        register_devices = user32.RegisterRawInputDevices
        register_devices.argtypes = [
            ctypes.POINTER(_NativeRawInputDevice),
            ctypes.c_uint,
            ctypes.c_uint,
        ]
        register_devices.restype = ctypes.c_bool
        if not register_devices(ctypes.byref(native_device), 1, ctypes.sizeof(native_device)):
            raise OSError(ctypes.get_last_error(), "RegisterRawInputDevices failed")


class WindowsRawInputFilter(QAbstractNativeEventFilter):
    """Receive native events without suppressing Qt's normal event delivery."""

    def nativeEventFilter(  # noqa: N802 - Qt override name.
        self,
        event_type: NativeEventType,
        message: int,
    ) -> bool:
        """Leave an event available to Qt until a later raw-input handler reads it.

        Args:
            event_type: Runtime-specific native event category supplied by Qt.
            message: Address of the platform-native event structure.

        Returns:
            False so Qt continues its normal event conversion and delivery.
        """
        del event_type, message
        return False


class WindowsRawInputBackend(WindowsRawInputFilter):
    """Own one foreground mouse Raw Input registration for one Qt main window."""

    def __init__(self, *, registrar: RawInputRegistrar | None = None) -> None:
        """Create a backend with an injectable Win32 registration boundary.

        Args:
            registrar: Native registration provider, defaulting to ``ctypes``.
        """
        super().__init__()
        self._registrar = registrar if registrar is not None else CtypesRawInputRegistrar()
        self._target_window_handle: int | None = None

    def start_capture(self, target_window_handle: int) -> None:
        """Register the one focused main window as the mouse input receiver.

        Args:
            target_window_handle: Native main-window handle supplied by Qt.

        Raises:
            OSError: If Win32 rejects the foreground registration.
            RawInputRegistrationConflictError: If another window is registered.
            RawInputConfigurationError: If the supplied native handle is invalid.
        """
        if (
            isinstance(target_window_handle, bool)
            or not isinstance(target_window_handle, int)
            or target_window_handle <= 0
        ):
            raise RawInputConfigurationError
        registered_handle = self._target_window_handle
        if registered_handle == target_window_handle:
            return
        if registered_handle is not None:
            raise RawInputRegistrationConflictError
        self._registrar.register(
            RawInputDevice(
                usage_page=HID_USAGE_PAGE_GENERIC,
                usage=HID_USAGE_GENERIC_MOUSE,
                flags=0,
                target_window_handle=target_window_handle,
            )
        )
        self._target_window_handle = target_window_handle

    def stop_capture(self) -> None:
        """Remove the foreground mouse registration after capture ends."""
        if self._target_window_handle is None:
            return
        self._registrar.register(
            RawInputDevice(
                usage_page=HID_USAGE_PAGE_GENERIC,
                usage=HID_USAGE_GENERIC_MOUSE,
                flags=RIDEV_REMOVE,
                target_window_handle=None,
            )
        )
        self._target_window_handle = None
