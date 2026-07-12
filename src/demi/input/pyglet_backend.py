"""Normalize pyglet keyboard and mouse events at the input boundary."""

from typing import Protocol, cast

from demi.application.coordinator import CaptureCoordinator
from demi.domain.physical_input import KeySource


class EventWindow(Protocol):
    """Window event target that accepts an input handler object."""

    def push_handlers(self, *objects: object) -> None:
        """Register backend event handlers with a pyglet window."""


class PygletKeyCodes(Protocol):
    """Pyglet key constants and symbol conversion used by the backend."""

    F12: int
    MOD_CTRL: int
    MOD_SHIFT: int
    MOD_ALT: int
    MOD_COMMAND: int
    MOD_OPTION: int

    def symbol_string(self, symbol: int) -> str:
        """Return pyglet's symbolic name for a key value."""


class PygletMouseCodes(Protocol):
    """Pyglet mouse button constants used by the backend."""

    LEFT: int
    MIDDLE: int
    RIGHT: int


class PygletInputBackend:
    """Convert pyglet events into a coordinator-owned physical input state."""

    def __init__(
        self,
        coordinator: CaptureCoordinator,
        *,
        key_codes: PygletKeyCodes | None = None,
        mouse_codes: PygletMouseCodes | None = None,
    ) -> None:
        """Initialize an event backend for one capture coordinator.

        Args:
            coordinator: Main-thread capture lifecycle owner.
            key_codes: Optional pyglet-compatible key constants for tests or
                alternate event sources.
            mouse_codes: Optional pyglet-compatible mouse constants for tests
                or alternate event sources.
        """
        self._coordinator = coordinator
        self._key_codes = key_codes
        self._mouse_codes = mouse_codes
        self._active_keys: dict[int, KeySource] = {}

    def install(self, window: EventWindow) -> None:
        """Install this backend as a pyglet window event handler."""
        window.push_handlers(self)

    def on_key_press(self, symbol: int, modifiers: int) -> bool | None:
        """Handle a key press, reserving F12 for capture release."""
        keys = self._key_codes_or_load()
        if symbol == keys.F12:
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
        keys = self._key_codes_or_load()
        if symbol == keys.F12:
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

    def _key_codes_or_load(self) -> PygletKeyCodes:
        if self._key_codes is None:
            from pyglet.window import key  # noqa: PLC0415

            self._key_codes = cast("PygletKeyCodes", key)
        return self._key_codes

    def _mouse_codes_or_load(self) -> PygletMouseCodes:
        if self._mouse_codes is None:
            from pyglet.window import mouse  # noqa: PLC0415

            self._mouse_codes = cast("PygletMouseCodes", mouse)
        return self._mouse_codes

    def _key_symbol(self, symbol: int) -> str:
        value = self._key_codes_or_load().symbol_string(symbol).upper()
        if value.startswith("_") and value[1:].isdigit():
            return value[1:]
        return value

    def _modifier_names(self, modifiers: int) -> frozenset[str]:
        keys = self._key_codes_or_load()
        modifier_names = (
            (keys.MOD_CTRL, "CTRL"),
            (keys.MOD_SHIFT, "SHIFT"),
            (keys.MOD_ALT, "ALT"),
            (keys.MOD_COMMAND, "COMMAND"),
            (keys.MOD_OPTION, "OPTION"),
        )
        return frozenset(name for mask, name in modifier_names if modifiers & mask)

    def _mouse_button(self, button: int) -> str:
        mouse = self._mouse_codes_or_load()
        mouse_button_names = {
            mouse.LEFT: "LEFT",
            mouse.MIDDLE: "MIDDLE",
            mouse.RIGHT: "RIGHT",
        }
        if button in mouse_button_names:
            return mouse_button_names[button]
        if button > 0 and button & (button - 1) == 0:
            return f"BUTTON_{button.bit_length()}"
        return f"BUTTON_{button}"
