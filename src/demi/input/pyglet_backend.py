"""Normalize pyglet keyboard and mouse events at the input boundary."""

from typing import Protocol

from pyglet.window import key, mouse

from demi.application.coordinator import CaptureCoordinator
from demi.domain.physical_input import KeySource


class EventWindow(Protocol):
    """Window event target that accepts an input handler object."""

    def push_handlers(self, *objects: object) -> None:
        """Register backend event handlers with a pyglet window."""


_MODIFIER_NAMES: tuple[tuple[int, str], ...] = (
    (key.MOD_CTRL, "CTRL"),
    (key.MOD_SHIFT, "SHIFT"),
    (key.MOD_ALT, "ALT"),
    (key.MOD_COMMAND, "COMMAND"),
    (key.MOD_OPTION, "OPTION"),
)
_MOUSE_BUTTON_NAMES = {
    mouse.LEFT: "LEFT",
    mouse.MIDDLE: "MIDDLE",
    mouse.RIGHT: "RIGHT",
}


class PygletInputBackend:
    """Convert pyglet events into a coordinator-owned physical input state."""

    def __init__(self, coordinator: CaptureCoordinator) -> None:
        """Initialize an event backend for one capture coordinator."""
        self._coordinator = coordinator
        self._active_keys: dict[int, KeySource] = {}

    def install(self, window: EventWindow) -> None:
        """Install this backend as a pyglet window event handler."""
        window.push_handlers(self)

    def on_key_press(self, symbol: int, modifiers: int) -> bool | None:
        """Handle a key press, reserving F12 for capture release."""
        if symbol == key.F12:
            self._active_keys.clear()
            self._coordinator.stop_capture()
            return True
        if not self._coordinator.is_captured:
            self._active_keys.clear()
            return None

        source = KeySource(self._key_symbol(symbol), self._modifier_names(modifiers))
        self._active_keys[symbol] = source
        self._coordinator.publisher.state.press_key(source.symbol, source.modifiers)
        return None

    def on_key_release(self, symbol: int, modifiers: int) -> bool | None:
        """Handle a key release without allowing F12 into mappings."""
        if symbol == key.F12:
            return True
        source = self._active_keys.pop(symbol, None)
        if source is None:
            if not self._coordinator.is_captured:
                return None
            source = KeySource(self._key_symbol(symbol), self._modifier_names(modifiers))
        self._coordinator.publisher.state.release_key(source.symbol, source.modifiers)
        return None

    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int) -> None:
        """Handle a mouse button press while capture is active."""
        del x, y, modifiers
        if self._coordinator.is_captured:
            self._coordinator.publisher.state.press_mouse_button(self._mouse_button(button))

    def on_mouse_release(self, x: int, y: int, button: int, modifiers: int) -> None:
        """Handle a mouse button release while capture is active."""
        del x, y, modifiers
        if self._coordinator.is_captured:
            self._coordinator.publisher.state.release_mouse_button(self._mouse_button(button))

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int) -> None:
        """Accumulate relative mouse movement while capture is active."""
        del x, y
        if self._coordinator.is_captured:
            self._coordinator.publisher.state.add_mouse_motion(dx, dy)

    def on_deactivate(self) -> None:
        """Suspend capture and neutralize on window focus loss."""
        self._active_keys.clear()
        self._coordinator.on_focus_lost()

    def on_activate(self) -> None:
        """Return focus to idle without automatically recapturing input."""
        self._coordinator.on_focus_gained()

    @staticmethod
    def _key_symbol(symbol: int) -> str:
        value = key.symbol_string(symbol).upper()
        if value.startswith("_") and value[1:].isdigit():
            return value[1:]
        return value

    @staticmethod
    def _modifier_names(modifiers: int) -> frozenset[str]:
        return frozenset(name for mask, name in _MODIFIER_NAMES if modifiers & mask)

    @staticmethod
    def _mouse_button(button: int) -> str:
        if button in _MOUSE_BUTTON_NAMES:
            return _MOUSE_BUTTON_NAMES[button]
        if button > 0 and button & (button - 1) == 0:
            return f"BUTTON_{button.bit_length()}"
        return f"BUTTON_{button}"
