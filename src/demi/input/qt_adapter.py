"""Normalize Qt key and mouse events for the capture input boundary."""

from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent

from demi.domain.physical_input import PhysicalInputState

type CaptureActivity = Callable[[], bool]


class QtInputAdapter(QObject):
    """Translate captured Qt key and mouse events into held input sources."""

    def __init__(
        self,
        *,
        state: PhysicalInputState,
        is_captured: CaptureActivity,
    ) -> None:
        """Create an adapter with framework-independent state storage.

        Args:
            state: Mutable held-source state for the current capture session.
            is_captured: Returns whether controller input capture is active.
        """
        super().__init__()
        self._state = state
        self._is_captured = is_captured

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt override name.
        """Normalize an eligible event without consuming Qt's normal handling."""
        del watched
        if not self._is_captured():
            return False

        if isinstance(event, QKeyEvent):
            self._handle_key_event(event)
        elif isinstance(event, QMouseEvent):
            self._handle_mouse_event(event)
        return False

    def _handle_key_event(self, event: QKeyEvent) -> None:
        symbol = _key_symbol(event.key())
        if symbol is None:
            return
        modifiers = _key_modifiers(event, symbol)
        if event.type() is QEvent.Type.KeyPress:
            self._state.press_key(symbol, modifiers)
        elif event.type() is QEvent.Type.KeyRelease:
            self._state.release_key(symbol, modifiers)

    def _handle_mouse_event(self, event: QMouseEvent) -> None:
        button = _mouse_button_symbol(event.button())
        if button is None:
            return
        if event.type() is QEvent.Type.MouseButtonPress:
            self._state.press_mouse_button(button)
        elif event.type() is QEvent.Type.MouseButtonRelease:
            self._state.release_mouse_button(button)


def _key_symbol(value: int) -> str | None:
    key = Qt.Key(value)
    name = key.name.removeprefix("Key_")
    aliases = {
        "Space": "SPACE",
        "Escape": "ESCAPE",
        "Tab": "TAB",
        "Backspace": "BACKSPACE",
        "Return": "RETURN",
        "Enter": "ENTER",
        "Left": "LEFT",
        "Right": "RIGHT",
        "Up": "UP",
        "Down": "DOWN",
        "Shift": "SHIFT",
        "Control": "CTRL",
        "Alt": "ALT",
        "Meta": "META",
    }
    if name in aliases:
        return aliases[name]
    if len(name) == 1 and name.isalnum():
        return name.upper()
    if name.startswith("F") and name[1:].isdigit():
        return name
    return None


def _key_modifiers(event: QKeyEvent, symbol: str) -> frozenset[str]:
    modifiers: set[str] = set()
    active = event.modifiers()
    if active & Qt.KeyboardModifier.ShiftModifier:
        modifiers.add("SHIFT")
    if active & Qt.KeyboardModifier.ControlModifier:
        modifiers.add("CTRL")
    if active & Qt.KeyboardModifier.AltModifier:
        modifiers.add("ALT")
    if active & Qt.KeyboardModifier.MetaModifier:
        modifiers.add("META")
    modifiers.discard(symbol)
    return frozenset(modifiers)


def _mouse_button_symbol(button: Qt.MouseButton) -> str | None:
    standard_buttons = {
        Qt.MouseButton.LeftButton: "LEFT",
        Qt.MouseButton.MiddleButton: "MIDDLE",
        Qt.MouseButton.RightButton: "RIGHT",
        Qt.MouseButton.BackButton: "BUTTON_4",
        Qt.MouseButton.ForwardButton: "BUTTON_5",
        Qt.MouseButton.TaskButton: "BUTTON_6",
    }
    return standard_buttons.get(button)
