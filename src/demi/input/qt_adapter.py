"""Normalize Qt key and mouse events for the capture input boundary."""

from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent

from demi.domain.physical_input import PhysicalInputState

type CaptureActivity = Callable[[], bool]
type CaptureTransition = Callable[[], object]


class QtInputAdapter(QObject):
    """Translate captured Qt key and mouse events into held input sources."""

    def __init__(
        self,
        *,
        state: PhysicalInputState,
        is_captured: CaptureActivity,
        on_stop_capture: CaptureTransition | None = None,
        on_focus_lost: CaptureTransition | None = None,
        on_focus_gained: CaptureTransition | None = None,
        on_dialog_opened: CaptureTransition | None = None,
    ) -> None:
        """Create an adapter with framework-independent state storage.

        Args:
            state: Mutable held-source state for the current capture session.
            is_captured: Returns whether controller input capture is active.
            on_stop_capture: Handles an F12 capture-release request.
            on_focus_lost: Handles a window or application focus loss.
            on_focus_gained: Handles a window or application focus gain.
            on_dialog_opened: Neutralizes capture before a dialog opens.
        """
        super().__init__()
        self._state = state
        self._is_captured = is_captured
        self._on_stop_capture = on_stop_capture
        self._on_focus_lost = on_focus_lost
        self._on_focus_gained = on_focus_gained
        self._on_dialog_opened = on_dialog_opened

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt override name.
        """Normalize an eligible event without consuming Qt's normal handling."""
        del watched
        event_type = event.type()
        if event_type in _FOCUS_LOSS_EVENTS:
            _invoke(self._on_focus_lost)
            return False
        if event_type in _FOCUS_GAIN_EVENTS:
            _invoke(self._on_focus_gained)
            return False
        if isinstance(event, QKeyEvent) and event.key() == Qt.Key.Key_F12:
            if self._is_captured():
                _invoke(self._on_stop_capture)
            return False

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

    def on_dialog_opened(self) -> None:
        """Request capture neutralization before a modal dialog is shown."""
        _invoke(self._on_dialog_opened)


_FOCUS_LOSS_EVENTS = frozenset(
    {
        QEvent.Type.FocusOut,
        QEvent.Type.WindowDeactivate,
        QEvent.Type.ApplicationDeactivate,
    }
)
_FOCUS_GAIN_EVENTS = frozenset(
    {
        QEvent.Type.FocusIn,
        QEvent.Type.WindowActivate,
        QEvent.Type.ApplicationActivate,
    }
)


def _invoke(callback: CaptureTransition | None) -> None:
    if callback is not None:
        callback()


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
