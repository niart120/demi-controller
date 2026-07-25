"""Windows XInput adapter for controllers SDL cannot read completely."""

import ctypes
from dataclasses import dataclass
from typing import Protocol

from demi.domain.gamepad import GamepadButton, GamepadState
from demi.input.gamepad import apply_stick_dead_zone, normalize_unsigned_trigger


@dataclass(frozen=True, slots=True)
class XInputSnapshot:
    """Raw values for one connected XInput slot."""

    buttons: int
    left_trigger: int
    right_trigger: int
    left_x: int
    left_y: int
    right_x: int
    right_y: int

    @classmethod
    def neutral(cls) -> "XInputSnapshot":
        """Return a connected XInput state with no active controls."""
        return cls(0, 0, 0, 0, 0, 0, 0)


class XInputReader(Protocol):
    """Read one XInput slot without leaking ctypes into the backend."""

    def get_state(self, slot: int) -> XInputSnapshot | None:
        """Return one connected slot state, or ``None`` when disconnected."""


class WindowsXInputBackend:
    """Poll one XInput controller and normalize it to a gamepad state."""

    def __init__(self, reader: XInputReader | None = None) -> None:
        """Create an XInput reader and defer slot selection until polling."""
        self._reader = reader if reader is not None else _CtypesXInputReader()
        self._slot: int | None = None
        self._closed = False

    def poll(self) -> GamepadState:
        """Return the selected connected XInput state or neutral when absent."""
        if self._closed:
            return GamepadState.neutral()
        slot = self._slot
        snapshot = self._reader.get_state(slot) if slot is not None else None
        if snapshot is None:
            self._slot = None
            for candidate in range(4):
                snapshot = self._reader.get_state(candidate)
                if snapshot is not None:
                    self._slot = candidate
                    break
        if snapshot is None:
            return GamepadState.neutral()
        return GamepadState(
            connected=True,
            buttons=frozenset(
                button for button, mask in _BUTTON_MASKS.items() if snapshot.buttons & mask
            ),
            left_stick=apply_stick_dead_zone(snapshot.left_x, snapshot.left_y, invert_y=False),
            right_stick=apply_stick_dead_zone(snapshot.right_x, snapshot.right_y, invert_y=False),
            left_trigger=normalize_unsigned_trigger(snapshot.left_trigger),
            right_trigger=normalize_unsigned_trigger(snapshot.right_trigger),
        )

    def close(self) -> None:
        """Mark this backend closed; XInput has no open handle to release."""
        self._closed = True
        self._slot = None


class _XInputGamepad(ctypes.Structure):
    _fields_ = [
        ("buttons", ctypes.c_ushort),
        ("left_trigger", ctypes.c_ubyte),
        ("right_trigger", ctypes.c_ubyte),
        ("left_x", ctypes.c_short),
        ("left_y", ctypes.c_short),
        ("right_x", ctypes.c_short),
        ("right_y", ctypes.c_short),
    ]


class _XInputState(ctypes.Structure):
    _fields_ = [("packet_number", ctypes.c_ulong), ("gamepad", _XInputGamepad)]


class _CtypesXInputReader:
    def __init__(self) -> None:
        # WinDLL is absent from non-Windows ctypes stubs.
        windows_dll = getattr(ctypes, "WinDLL")  # noqa: B009
        self._get_state = windows_dll("xinput1_4.dll").XInputGetState
        self._get_state.argtypes = [ctypes.c_uint, ctypes.POINTER(_XInputState)]
        self._get_state.restype = ctypes.c_uint

    def get_state(self, slot: int) -> XInputSnapshot | None:
        state = _XInputState()
        if self._get_state(slot, ctypes.byref(state)) != 0:
            return None
        gamepad = state.gamepad
        return XInputSnapshot(
            gamepad.buttons,
            gamepad.left_trigger,
            gamepad.right_trigger,
            gamepad.left_x,
            gamepad.left_y,
            gamepad.right_x,
            gamepad.right_y,
        )


_BUTTON_MASKS = {
    GamepadButton.DPAD_UP: 0x0001,
    GamepadButton.DPAD_DOWN: 0x0002,
    GamepadButton.DPAD_LEFT: 0x0004,
    GamepadButton.DPAD_RIGHT: 0x0008,
    GamepadButton.BACK: 0x0020,
    GamepadButton.START: 0x0010,
    GamepadButton.LEFT_STICK: 0x0040,
    GamepadButton.RIGHT_STICK: 0x0080,
    GamepadButton.LEFT_SHOULDER: 0x0100,
    GamepadButton.RIGHT_SHOULDER: 0x0200,
    GamepadButton.SOUTH: 0x1000,
    GamepadButton.EAST: 0x2000,
    GamepadButton.WEST: 0x4000,
    GamepadButton.NORTH: 0x8000,
}
