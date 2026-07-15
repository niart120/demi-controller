"""Suppress mouse delivery outside Demi while a Windows capture is active."""

import ctypes
import sys
from collections.abc import Callable
from typing import Protocol

WH_MOUSE_LL = 14
HC_ACTION = 0
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_RBUTTONDBLCLK = 0x0206
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MBUTTONDBLCLK = 0x0209
WM_MOUSEWHEEL = 0x020A
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C
WM_XBUTTONDBLCLK = 0x020D
WM_MOUSEHWHEEL = 0x020E

_BUTTON_PRESS_MESSAGES = frozenset(
    {
        WM_LBUTTONDOWN,
        WM_LBUTTONDBLCLK,
        WM_RBUTTONDOWN,
        WM_RBUTTONDBLCLK,
        WM_MBUTTONDOWN,
        WM_MBUTTONDBLCLK,
        WM_XBUTTONDOWN,
        WM_XBUTTONDBLCLK,
    }
)
_BUTTON_RELEASE_MESSAGES = frozenset(
    {
        WM_LBUTTONUP,
        WM_RBUTTONUP,
        WM_MBUTTONUP,
        WM_XBUTTONUP,
    }
)
_SUPPRESSED_MESSAGES = frozenset(
    {
        WM_MOUSEMOVE,
        *_BUTTON_PRESS_MESSAGES,
        *_BUTTON_RELEASE_MESSAGES,
        WM_MOUSEWHEEL,
        WM_MOUSEHWHEEL,
    }
)

type MouseButtonSink = Callable[[str], object]
type MouseMessageCallback = Callable[[int, int], bool]


class MouseHookRegistrar(Protocol):
    """Install and remove one process-owned low-level mouse hook."""

    def install(self, callback: MouseMessageCallback) -> int:
        """Install ``callback`` and return its nonzero native hook handle."""

    def remove(self, handle: int) -> None:
        """Remove the hook identified by ``handle``."""


class WindowsMouseHookError(OSError):
    """Report a Windows low-level mouse hook registration failure."""


class _NativeLowLevelMouseInput(ctypes.Structure):
    _fields_ = [
        ("pt", ctypes.c_long * 2),
        ("mouseData", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("time", ctypes.c_uint32),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class CtypesMouseHookRegistrar:
    """Register a ``WH_MOUSE_LL`` callback without injecting into other processes."""

    def __init__(self) -> None:
        """Create an empty callback registry that keeps native callbacks alive."""
        self._callbacks: dict[int, object] = {}

    def install(self, callback: MouseMessageCallback) -> int:
        """Install one callback on the current GUI thread.

        Args:
            callback: Returns whether the native message must be suppressed.

        Returns:
            Nonzero hook handle returned by ``SetWindowsHookExW``.

        Raises:
            WindowsMouseHookError: If Windows cannot install the hook.
        """
        if sys.platform != "win32":
            raise WindowsMouseHookError
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        hook_procedure_type = ctypes.WINFUNCTYPE(
            ctypes.c_ssize_t,
            ctypes.c_int,
            ctypes.c_size_t,
            ctypes.c_ssize_t,
        )
        call_next_hook = user32.CallNextHookEx
        call_next_hook.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_size_t,
            ctypes.c_ssize_t,
        ]
        call_next_hook.restype = ctypes.c_ssize_t

        @hook_procedure_type
        def native_callback(code: int, message: int, l_param: int) -> int:
            if code == HC_ACTION:
                try:
                    mouse_data = ctypes.cast(
                        l_param,
                        ctypes.POINTER(_NativeLowLevelMouseInput),
                    ).contents.mouseData
                    if callback(int(message), int(mouse_data)):
                        return 1
                except (TypeError, ValueError):
                    return int(call_next_hook(None, code, message, l_param))
            return int(call_next_hook(None, code, message, l_param))

        set_windows_hook = user32.SetWindowsHookExW
        set_windows_hook.argtypes = [
            ctypes.c_int,
            hook_procedure_type,
            ctypes.c_void_p,
            ctypes.c_uint32,
        ]
        set_windows_hook.restype = ctypes.c_void_p
        native_handle = set_windows_hook(WH_MOUSE_LL, native_callback, None, 0)
        if native_handle is None:
            raise WindowsMouseHookError(ctypes.get_last_error())
        handle = int(native_handle)
        self._callbacks[handle] = native_callback
        return handle

    def remove(self, handle: int) -> None:
        """Remove one hook and release its callback reference.

        Args:
            handle: Nonzero native hook handle returned by :meth:`install`.

        Raises:
            WindowsMouseHookError: If Windows cannot remove the hook.
        """
        if sys.platform != "win32":
            raise WindowsMouseHookError
        unhook_windows_hook = ctypes.WinDLL("user32", use_last_error=True).UnhookWindowsHookEx
        unhook_windows_hook.argtypes = [ctypes.c_void_p]
        unhook_windows_hook.restype = ctypes.c_bool
        if not unhook_windows_hook(ctypes.c_void_p(handle)):
            raise WindowsMouseHookError(ctypes.get_last_error())
        self._callbacks.pop(handle, None)


class WindowsMouseInputSuppressor:
    """Block mouse delivery and preserve controller button state during capture."""

    def __init__(
        self,
        *,
        registrar: MouseHookRegistrar | None = None,
        on_button_pressed: MouseButtonSink | None = None,
        on_button_released: MouseButtonSink | None = None,
    ) -> None:
        """Create an inactive mouse-delivery suppressor.

        Args:
            registrar: Low-level hook provider, defaulting to the Win32 implementation.
            on_button_pressed: Receives the canonical source for one press.
            on_button_released: Receives the canonical source for one release.
        """
        self._registrar = registrar if registrar is not None else CtypesMouseHookRegistrar()
        self._on_button_pressed = on_button_pressed
        self._on_button_released = on_button_released
        self._hook_handle: int | None = None
        self._active = False

    @property
    def active(self) -> bool:
        """Return whether mouse messages are currently being suppressed."""
        return self._active

    def start(self) -> None:
        """Start suppressing external mouse delivery for the active capture session.

        Raises:
            OSError: If the low-level hook cannot be installed.
        """
        if self._active:
            return
        handle = self._registrar.install(self.handle_message)
        if isinstance(handle, bool) or not isinstance(handle, int) or handle <= 0:
            raise WindowsMouseHookError
        self._hook_handle = handle
        self._active = True

    def stop(self) -> None:
        """Stop suppression and attempt to remove the low-level hook.

        The active flag is cleared before native removal so an unhook failure
        cannot leave desktop mouse input suppressed.

        Raises:
            OSError: If the hook was active but Windows rejects its removal.
        """
        handle = self._hook_handle
        self._hook_handle = None
        self._active = False
        if handle is not None:
            self._registrar.remove(handle)

    def handle_message(self, message: int, mouse_data: int = 0) -> bool:
        """Update a mapped button and decide whether to suppress one message.

        Args:
            message: One ``WM_MOUSE*`` message received by the low-level hook.
            mouse_data: Native ``MSLLHOOKSTRUCT.mouseData`` value for X buttons.

        Returns:
            ``True`` only while active and the message must not reach its target.
        """
        if not self._active or message not in _SUPPRESSED_MESSAGES:
            return False
        button = _button_symbol(message, mouse_data)
        if button is not None:
            if message in _BUTTON_PRESS_MESSAGES:
                _invoke(self._on_button_pressed, button)
            elif message in _BUTTON_RELEASE_MESSAGES:
                _invoke(self._on_button_released, button)
        return True


def _button_symbol(message: int, mouse_data: int) -> str | None:
    if message in {WM_LBUTTONDOWN, WM_LBUTTONUP, WM_LBUTTONDBLCLK}:
        return "LEFT"
    if message in {WM_RBUTTONDOWN, WM_RBUTTONUP, WM_RBUTTONDBLCLK}:
        return "RIGHT"
    if message in {WM_MBUTTONDOWN, WM_MBUTTONUP, WM_MBUTTONDBLCLK}:
        return "MIDDLE"
    if message in {WM_XBUTTONDOWN, WM_XBUTTONUP, WM_XBUTTONDBLCLK}:
        x_button = (mouse_data >> 16) & 0xFFFF
        if x_button == 1:
            return "BUTTON_4"
        if x_button == 2:
            return "BUTTON_5"
    return None


def _invoke(callback: MouseButtonSink | None, button: str) -> None:
    if callback is not None:
        callback(button)
