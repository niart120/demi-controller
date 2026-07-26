"""Gamepad input port and pure standard-layout conversion."""

from math import hypot
from typing import Protocol, runtime_checkable

from demi.domain.controller import LogicalButton, StickVector
from demi.domain.gamepad import GamepadButton, GamepadDevice, GamepadState

STICK_DEAD_ZONE = 0.15
TRIGGER_BUTTON_THRESHOLD = 0.5
SDL_AXIS_MAXIMUM = 32_767


class GamepadInputPort(Protocol):
    """Non-blocking source of one normalized gamepad snapshot."""

    def poll(self) -> GamepadState:
        """Return the latest connected gamepad state or an explicit neutral state."""

    def close(self) -> None:
        """Release backend resources; repeated calls must be harmless."""


@runtime_checkable
class GamepadSelectionPort(Protocol):
    """Enumerate and select a gamepad without leaking SDL details."""

    def connected_devices(self) -> tuple[GamepadDevice, ...]:
        """Return the currently connected selectable gamepads."""

    def select_device(self, persistent_id: str | None) -> None:
        """Select one persistent ID, or ``None`` for automatic selection."""


class PreferredGamepadBackend(GamepadSelectionPort):
    """Use a preferred gamepad backend until it disconnects.

    The selected backend remains stable for one connection session. This keeps
    a Windows XInput controller from being mixed with an SDL fallback device.
    """

    def __init__(self, *, preferred: GamepadInputPort, fallback: GamepadInputPort) -> None:
        """Create a selector that checks ``preferred`` before ``fallback``."""
        self._preferred = preferred
        self._fallback = fallback
        self._active: GamepadInputPort | None = None
        self._selected_persistent_id: str | None = None

    def poll(self) -> GamepadState:
        """Return the selected backend state, selecting on connection."""
        if self._selected_persistent_id is not None:
            return self._fallback.poll()
        active = self._active
        if active is not None:
            state = active.poll()
            if state.connected:
                return state
            self._active = None
        preferred_state = self._preferred.poll()
        if preferred_state.connected:
            self._active = self._preferred
            return preferred_state
        fallback_state = self._fallback.poll()
        if fallback_state.connected:
            self._active = self._fallback
        return fallback_state

    def connected_devices(self) -> tuple[GamepadDevice, ...]:
        """Return the SDL fallback devices that can be selected persistently."""
        fallback = self._fallback
        if not isinstance(fallback, GamepadSelectionPort):
            return ()
        return fallback.connected_devices()

    def select_device(self, persistent_id: str | None) -> None:
        """Select an SDL fallback device or restore automatic preference."""
        fallback = self._fallback
        if not isinstance(fallback, GamepadSelectionPort):
            return
        fallback.select_device(persistent_id)
        self._selected_persistent_id = persistent_id
        self._active = None

    def close(self) -> None:
        """Close both candidates regardless of the currently selected backend."""
        self._preferred.close()
        self._fallback.close()
        self._active = None


def apply_stick_dead_zone(
    raw_x: int,
    raw_y: int,
    *,
    dead_zone: float = STICK_DEAD_ZONE,
    invert_y: bool = True,
) -> StickVector:
    """Normalize an SDL signed stick pair after radial dead-zone rescaling.

    Args:
        raw_x: SDL horizontal signed 16-bit axis value.
        raw_y: Signed 16-bit vertical axis value.
        dead_zone: Radial normalized magnitude that becomes neutral.
        invert_y: Whether positive raw Y points down rather than up.

    Returns:
        A clamped stick vector using positive-up domain coordinates.
    """
    normalized_x = _clamp(raw_x / SDL_AXIS_MAXIMUM, -1.0, 1.0)
    y_sign = -1.0 if invert_y else 1.0
    normalized_y = _clamp(y_sign * raw_y / SDL_AXIS_MAXIMUM, -1.0, 1.0)
    magnitude = hypot(normalized_x, normalized_y)
    if magnitude <= dead_zone:
        return StickVector(0.0, 0.0)
    scaled_magnitude = min((magnitude - dead_zone) / (1.0 - dead_zone), 1.0)
    scale = scaled_magnitude / magnitude
    return StickVector(
        _clamp(normalized_x * scale, -1.0, 1.0),
        _clamp(normalized_y * scale, -1.0, 1.0),
    )


def normalize_trigger(raw_value: int) -> float:
    """Normalize an SDL signed trigger axis to the domain's zero-to-one range."""
    return _clamp((raw_value + 32_768) / 65_535, 0.0, 1.0)


def normalize_unsigned_trigger(raw_value: int) -> float:
    """Normalize an XInput unsigned trigger value to the domain's zero-to-one range."""
    return _clamp(raw_value / 255, 0.0, 1.0)


def standard_gamepad_buttons(state: GamepadState) -> frozenset[LogicalButton]:
    """Convert the fixed SDL standard layout into Pro Controller buttons."""
    if not state.connected:
        return frozenset()
    mapping = {
        GamepadButton.SOUTH: LogicalButton.B,
        GamepadButton.EAST: LogicalButton.A,
        GamepadButton.WEST: LogicalButton.Y,
        GamepadButton.NORTH: LogicalButton.X,
        GamepadButton.DPAD_UP: LogicalButton.DPAD_UP,
        GamepadButton.DPAD_DOWN: LogicalButton.DPAD_DOWN,
        GamepadButton.DPAD_LEFT: LogicalButton.DPAD_LEFT,
        GamepadButton.DPAD_RIGHT: LogicalButton.DPAD_RIGHT,
        GamepadButton.LEFT_SHOULDER: LogicalButton.L,
        GamepadButton.RIGHT_SHOULDER: LogicalButton.R,
        GamepadButton.LEFT_STICK: LogicalButton.LEFT_STICK,
        GamepadButton.RIGHT_STICK: LogicalButton.RIGHT_STICK,
        GamepadButton.BACK: LogicalButton.MINUS,
        GamepadButton.START: LogicalButton.PLUS,
        GamepadButton.GUIDE: LogicalButton.HOME,
    }
    buttons = {target for source, target in mapping.items() if source in state.buttons}
    if state.left_trigger >= TRIGGER_BUTTON_THRESHOLD:
        buttons.add(LogicalButton.ZL)
    if state.right_trigger >= TRIGGER_BUTTON_THRESHOLD:
        buttons.add(LogicalButton.ZR)
    return frozenset(buttons)


def combine_sticks(
    mapped: StickVector,
    gamepad: StickVector,
    *,
    circular_limit: bool,
) -> StickVector:
    """Combine mapped and gamepad sticks with per-direction maxima."""
    x = _combine_axis(mapped.x, gamepad.x)
    y = _combine_axis(mapped.y, gamepad.y)
    magnitude = hypot(x, y)
    if circular_limit and magnitude > 1.0:
        x /= magnitude
        y /= magnitude
    return StickVector(x, y)


def _combine_axis(first: float, second: float) -> float:
    return max(first, 0.0, second) - max(-first, 0.0, -second)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))
