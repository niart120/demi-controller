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
WM_INPUT = 0x00FF
RIM_TYPEMOUSE = 0
RID_INPUT = 0x10000003
_UINT_ERROR = 0xFFFFFFFF
MOUSE_MOVE_ABSOLUTE = 0x0001
_WINDOWS_GENERIC_MSG = b"windows_generic_MSG"

type NativeEventType = QByteArray | bytes | bytearray | memoryview


class RawInputConfigurationError(ValueError):
    """Reject a raw-input request that cannot be represented safely."""


class RawInputRegistrationConflictError(RuntimeError):
    """Reject registration of a second main-window receiver in one backend."""


class RawInputUnavailableError(OSError):
    """Report that the current platform does not expose Windows Raw Input."""


class RawInputReadError(OSError):
    """Report a failed native message or raw-input payload read."""


@dataclass(frozen=True, slots=True)
class NativeWindowsMessage:
    """Represent the native message values needed before reading Raw Input."""

    message: int
    l_param: int
    window_handle: int | None = None


@dataclass(frozen=True, slots=True)
class RawMousePacket:
    """Represent one decoded Win32 mouse packet without native pointers."""

    flags: int
    dx: int
    dy: int


class NativeMessageReader(Protocol):
    """Decode a Qt native-message address without exposing it to application code."""

    def read(self, message_address: int) -> NativeWindowsMessage:
        """Return the stable values needed to select a raw-input payload."""


class RawInputReader(Protocol):
    """Decode one Win32 raw-input handle into a framework-independent packet."""

    def read_mouse(self, raw_input_handle: int) -> RawMousePacket | None:
        """Return one mouse packet, or ``None`` for a non-mouse payload."""


class RelativeMotionSink(Protocol):
    """Receive decoded relative motion without a native event dependency."""

    def __call__(self, dx: float, dy: float) -> object:
        """Accept one relative mouse movement value pair."""


def _is_windows_generic_message(event_type: NativeEventType) -> bool:
    if isinstance(event_type, QByteArray):
        return bytes(event_type.data()) == _WINDOWS_GENERIC_MSG
    return bytes(event_type) == _WINDOWS_GENERIC_MSG


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


class _NativePoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_int32), ("y", ctypes.c_int32)]


class _NativeMessage(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint32),
        ("wParam", ctypes.c_size_t),
        ("lParam", ctypes.c_ssize_t),
        ("time", ctypes.c_uint32),
        ("pt", _NativePoint),
        ("lPrivate", ctypes.c_uint32),
    ]


class _NativeRawInputHeader(ctypes.Structure):
    _fields_ = [
        ("dwType", ctypes.c_uint32),
        ("dwSize", ctypes.c_uint32),
        ("hDevice", ctypes.c_void_p),
        ("wParam", ctypes.c_size_t),
    ]


class _NativeRawMouse(ctypes.Structure):
    _fields_ = [
        ("usFlags", ctypes.c_ushort),
        ("_padding", ctypes.c_ushort),
        ("ulButtons", ctypes.c_uint32),
        ("ulRawButtons", ctypes.c_uint32),
        ("lLastX", ctypes.c_int32),
        ("lLastY", ctypes.c_int32),
        ("ulExtraInformation", ctypes.c_uint32),
    ]


def decode_raw_mouse_payload(payload: bytes | bytearray | memoryview) -> RawMousePacket | None:
    """Decode a copied ``RAWINPUT`` payload without retaining a native pointer.

    Args:
        payload: Exact bytes returned by ``GetRawInputData`` for one message.

    Returns:
        Decoded mouse flags and deltas, or ``None`` for a non-mouse payload.

    Raises:
        RawInputReadError: If the payload is incomplete or internally inconsistent.
    """
    payload_bytes = bytes(payload)
    header_size = ctypes.sizeof(_NativeRawInputHeader)
    if len(payload_bytes) < header_size:
        raise RawInputReadError
    header = _NativeRawInputHeader.from_buffer_copy(payload_bytes)
    if header.dwSize < header_size or header.dwSize > len(payload_bytes):
        raise RawInputReadError
    if header.dwType != RIM_TYPEMOUSE:
        return None
    mouse_offset = header_size
    if header.dwSize < mouse_offset + ctypes.sizeof(_NativeRawMouse):
        raise RawInputReadError
    mouse = _NativeRawMouse.from_buffer_copy(payload_bytes, mouse_offset)
    return RawMousePacket(
        flags=int(mouse.usFlags),
        dx=int(mouse.lLastX),
        dy=int(mouse.lLastY),
    )


class CtypesNativeMessageReader:
    """Read the Win32 ``MSG`` selected by Qt's native event filter."""

    def read(self, message_address: int) -> NativeWindowsMessage:
        """Decode the message and raw-input handle from a native pointer.

        Args:
            message_address: Address of the Win32 ``MSG`` supplied by Qt.

        Returns:
            Message code and ``lParam`` without returning the native pointer.

        Raises:
            RawInputUnavailableError: If the current platform is not Windows.
            RawInputReadError: If Qt did not provide a readable message address.
        """
        if sys.platform != "win32":
            raise RawInputUnavailableError
        if (
            isinstance(message_address, bool)
            or not isinstance(message_address, int)
            or message_address <= 0
        ):
            raise RawInputReadError
        try:
            native_message = ctypes.cast(
                message_address,
                ctypes.POINTER(_NativeMessage),
            ).contents
        except (TypeError, ValueError) as error:
            raise RawInputReadError from error
        return NativeWindowsMessage(
            message=int(native_message.message),
            l_param=int(native_message.lParam),
            window_handle=(int(native_message.hwnd) if native_message.hwnd is not None else None),
        )


class CtypesRawInputReader:
    """Read one ``RAWINPUT`` payload through ``GetRawInputData``."""

    def read_mouse(self, raw_input_handle: int) -> RawMousePacket | None:
        """Decode one mouse packet from the raw-input handle in ``WM_INPUT``.

        Args:
            raw_input_handle: ``HRAWINPUT`` value taken from a Win32 message.

        Returns:
            Decoded mouse flags and deltas, or ``None`` for a non-mouse input.

        Raises:
            RawInputUnavailableError: If the current platform is not Windows.
            RawInputReadError: If Win32 cannot return a complete input payload.
        """
        if sys.platform != "win32":
            raise RawInputUnavailableError
        if (
            isinstance(raw_input_handle, bool)
            or not isinstance(raw_input_handle, int)
            or raw_input_handle <= 0
        ):
            raise RawInputReadError
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        get_raw_input_data = user32.GetRawInputData
        get_raw_input_data.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_uint),
            ctypes.c_uint,
        ]
        get_raw_input_data.restype = ctypes.c_uint
        payload_size = ctypes.c_uint()
        header_size = ctypes.sizeof(_NativeRawInputHeader)
        result = get_raw_input_data(
            ctypes.c_void_p(raw_input_handle),
            RID_INPUT,
            None,
            ctypes.byref(payload_size),
            header_size,
        )
        if result == _UINT_ERROR or payload_size.value < header_size:
            raise RawInputReadError(ctypes.get_last_error())
        payload = ctypes.create_string_buffer(payload_size.value)
        result = get_raw_input_data(
            ctypes.c_void_p(raw_input_handle),
            RID_INPUT,
            payload,
            ctypes.byref(payload_size),
            header_size,
        )
        if result == _UINT_ERROR or result != payload_size.value:
            raise RawInputReadError(ctypes.get_last_error())
        return decode_raw_mouse_payload(payload.raw[: payload_size.value])


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

    def __init__(
        self,
        *,
        registrar: RawInputRegistrar | None = None,
        on_relative_motion: RelativeMotionSink | None = None,
        message_reader: NativeMessageReader | None = None,
        raw_input_reader: RawInputReader | None = None,
    ) -> None:
        """Create a backend with an injectable Win32 registration boundary.

        Args:
            registrar: Native registration provider, defaulting to ``ctypes``.
            on_relative_motion: Destination for decoded mouse movement while
                capture is active.
            message_reader: Decoder for Qt native ``MSG`` addresses.
            raw_input_reader: Decoder for ``HRAWINPUT`` payloads.
        """
        super().__init__()
        self._registrar = registrar if registrar is not None else CtypesRawInputRegistrar()
        self._on_relative_motion = on_relative_motion
        self._message_reader = (
            message_reader if message_reader is not None else CtypesNativeMessageReader()
        )
        self._raw_input_reader = (
            raw_input_reader if raw_input_reader is not None else CtypesRawInputReader()
        )
        self._target_window_handle: int | None = None
        self._capture_epoch: int | None = None

    def nativeEventFilter(  # noqa: N802 - Qt override name.
        self,
        event_type: NativeEventType,
        message: int,
    ) -> bool:
        """Accumulate decoded Raw Input motion without consuming the Qt event.

        Args:
            event_type: Runtime-specific native event category supplied by Qt.
            message: Address of the platform-native event structure.

        Returns:
            False so Qt continues normal event conversion and delivery.
        """
        return self.handle_native_event(
            event_type,
            message,
            capture_epoch=self._capture_epoch,
        )

    def handle_native_event(
        self,
        event_type: NativeEventType,
        message: int,
        *,
        capture_epoch: int | None,
    ) -> bool:
        """Accumulate one current, relative event without consuming Qt handling.

        Args:
            event_type: Runtime-specific native event category supplied by Qt.
            message: Address of the platform-native event structure.
            capture_epoch: Capture token assigned when the event entered this
                backend, or ``None`` outside capture.

        Returns:
            False so Qt continues normal event conversion and delivery.
        """
        target_window_handle = self._target_window_handle
        if (
            target_window_handle is None
            or self._capture_epoch is None
            or capture_epoch != self._capture_epoch
            or self._on_relative_motion is None
            or not _is_windows_generic_message(event_type)
        ):
            return False
        native_message = self._message_reader.read(message)
        if (
            native_message.message != WM_INPUT
            or native_message.window_handle != target_window_handle
        ):
            return False
        packet = self._raw_input_reader.read_mouse(native_message.l_param)
        if packet is None or packet.flags & MOUSE_MOVE_ABSOLUTE:
            return False
        self._on_relative_motion(float(packet.dx), float(packet.dy))
        return False

    def start_capture(self, target_window_handle: int, *, capture_epoch: int = 0) -> None:
        """Register the one focused main window as the mouse input receiver.

        Args:
            target_window_handle: Native main-window handle supplied by Qt.
            capture_epoch: Capture token for events accepted by this registration.

        Raises:
            OSError: If Win32 rejects the foreground registration.
            RawInputRegistrationConflictError: If another window is registered.
            RawInputConfigurationError: If the supplied native handle is invalid.
        """
        if (
            isinstance(target_window_handle, bool)
            or not isinstance(target_window_handle, int)
            or target_window_handle <= 0
            or isinstance(capture_epoch, bool)
            or not isinstance(capture_epoch, int)
            or capture_epoch < 0
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
        self._capture_epoch = capture_epoch

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
        self._capture_epoch = None
