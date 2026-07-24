"""Normalize Qt key and mouse events for the capture input boundary."""

from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent

from demi.domain.physical_input import KeySource, MouseButtonSource, PhysicalInputState

type CaptureActivity = Callable[[], bool]
type CaptureTransition = Callable[[], object]
type CaptureEpoch = Callable[[], int]
type RelativePositionSink = Callable[[float, float, int], object]
type FocusEventTarget = Callable[[QObject], bool]


class QtInputAdapter(QObject):
    """Translate captured Qt key and mouse events into held input sources."""

    def __init__(
        self,
        *,
        state: PhysicalInputState,
        is_captured: CaptureActivity,
        is_keyboard_active: CaptureActivity | None = None,
        on_toggle_capture: CaptureTransition | None = None,
        on_focus_lost: CaptureTransition | None = None,
        on_focus_gained: CaptureTransition | None = None,
        on_dialog_opened: CaptureTransition | None = None,
        capture_epoch: CaptureEpoch | None = None,
        on_relative_position: RelativePositionSink | None = None,
        is_focus_event_target: FocusEventTarget | None = None,
    ) -> None:
        """Create an adapter with framework-independent state storage.

        Args:
            state: Mutable held-source state for the current capture session.
            is_captured: Returns whether pointer capture is active.
            is_keyboard_active: Returns whether operational keyboard input is
                active. Defaults to ``is_captured`` for legacy callers.
            on_toggle_capture: Handles an F5 pointer-capture toggle request.
            on_focus_lost: Handles a window or application focus loss.
            on_focus_gained: Handles a window or application focus gain.
            on_dialog_opened: Neutralizes capture before a dialog opens.
            capture_epoch: Returns the epoch that owns a Qt pointer position.
            on_relative_position: Receives a captured Qt position and its epoch.
            is_focus_event_target: Limits focus transitions when the adapter
                is installed application-wide.
        """
        super().__init__()
        self._state = state
        self._is_captured = is_captured
        self._is_keyboard_active = is_captured if is_keyboard_active is None else is_keyboard_active
        self._on_toggle_capture = on_toggle_capture
        self._on_focus_lost = on_focus_lost
        self._on_focus_gained = on_focus_gained
        self._on_dialog_opened = on_dialog_opened
        self._capture_epoch = capture_epoch
        self._on_relative_position = on_relative_position
        self._is_focus_event_target = is_focus_event_target

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt override name.
        """Normalize an eligible event without consuming Qt's normal handling."""
        event_type = event.type()
        if event_type in _FOCUS_LOSS_EVENTS and self._accepts_focus_event(watched):
            _invoke(self._on_focus_lost)
            return False
        if event_type in _FOCUS_GAIN_EVENTS and self._accepts_focus_event(watched):
            _invoke(self._on_focus_gained)
            return False
        if isinstance(event, QKeyEvent) and event.key() == Qt.Key.Key_F5:
            _invoke(self._on_toggle_capture)
            return False

        if isinstance(event, QKeyEvent):
            if self._is_keyboard_active():
                self._handle_key_event(event)
            return False
        if not self._is_captured():
            return False
        if isinstance(event, QMouseEvent):
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
        if event.type() is QEvent.Type.MouseMove:
            self._handle_mouse_position(event)
            return
        button = _mouse_button_symbol(event.button())
        if button is None:
            return
        if event.type() is QEvent.Type.MouseButtonPress:
            self._state.press_mouse_button(button)
        elif event.type() is QEvent.Type.MouseButtonRelease:
            self._state.release_mouse_button(button)

    def _handle_mouse_position(self, event: QMouseEvent) -> None:
        capture_epoch = self._capture_epoch
        on_relative_position = self._on_relative_position
        if capture_epoch is None or on_relative_position is None:
            return
        position = event.globalPosition()
        on_relative_position(position.x(), position.y(), capture_epoch())

    def _accepts_focus_event(self, watched: QObject) -> bool:
        focus_event_target = self._is_focus_event_target
        return focus_event_target is None or focus_event_target(watched)

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


def key_source_for_event(event: QKeyEvent) -> str | None:
    """Return the canonical settings source for a supported Qt key event.

    Args:
        event: Qt key event whose key and modifiers are normalized.

    Returns:
        The persisted ``KEY:...`` source, or ``None`` when the Qt key has no
        supported mapping.
    """
    symbol = _key_symbol(event.key())
    if symbol is None:
        return None
    return KeySource(symbol, _key_modifiers(event, symbol)).canonical


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


def mouse_source_for_event(event: QMouseEvent) -> str | None:
    """Return the canonical settings source for a supported Qt mouse button.

    Args:
        event: Qt mouse event whose button is normalized.

    Returns:
        The persisted ``MOUSE:...`` source, or ``None`` when the button has no
        supported mapping.
    """
    button = _mouse_button_symbol(event.button())
    if button is None:
        return None
    return MouseButtonSource(button).canonical
