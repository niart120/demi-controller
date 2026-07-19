from PySide6.QtCore import QEvent, QObject, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent

from demi.domain.physical_input import KeySource, MouseButtonSource, PhysicalInputState
from demi.input.qt_adapter import QtInputAdapter


def test_qt_input_adapter_normalizes_held_sources_only_while_captured(
    qt_application: object,
) -> None:
    assert qt_application is not None
    captured = False
    state = PhysicalInputState()
    adapter = QtInputAdapter(state=state, is_captured=lambda: captured)
    target = QObject()

    assert adapter.eventFilter(target, _key_event(QEvent.Type.KeyPress, Qt.Key.Key_F)) is False
    assert (
        adapter.eventFilter(
            target,
            _mouse_event(QEvent.Type.MouseButtonPress, Qt.MouseButton.BackButton),
        )
        is False
    )
    assert state.held_keys == set()
    assert state.held_mouse_buttons == set()

    captured = True

    assert adapter.eventFilter(target, _key_event(QEvent.Type.KeyPress, Qt.Key.Key_F)) is False
    assert (
        adapter.eventFilter(
            target,
            _key_event(QEvent.Type.KeyPress, Qt.Key.Key_F, auto_repeat=True),
        )
        is False
    )
    assert (
        adapter.eventFilter(
            target,
            _mouse_event(QEvent.Type.MouseButtonPress, Qt.MouseButton.BackButton),
        )
        is False
    )
    assert (
        adapter.eventFilter(
            target,
            _mouse_event(QEvent.Type.MouseButtonRelease, Qt.MouseButton.RightButton),
        )
        is False
    )

    assert state.held_keys == {KeySource("F")}
    assert state.held_mouse_buttons == {MouseButtonSource("BUTTON_4")}
    assert state.revision == 2

    adapter.eventFilter(target, _key_event(QEvent.Type.KeyRelease, Qt.Key.Key_F))
    adapter.eventFilter(
        target,
        _mouse_event(QEvent.Type.MouseButtonRelease, Qt.MouseButton.BackButton),
    )

    assert state.held_keys == set()
    assert state.held_mouse_buttons == set()
    assert state.revision == 4


def test_qt_input_adapter_routes_keyboard_without_pointer_capture() -> None:
    state = PhysicalInputState()
    adapter = QtInputAdapter(
        state=state,
        is_captured=lambda: False,
        is_keyboard_active=lambda: True,
    )
    target = QObject()

    adapter.eventFilter(target, _key_event(QEvent.Type.KeyPress, Qt.Key.Key_F))
    adapter.eventFilter(
        target,
        _mouse_event(QEvent.Type.MouseButtonPress, Qt.MouseButton.LeftButton),
    )

    assert state.held_keys == {KeySource("F")}
    assert state.held_mouse_buttons == set()


def _key_event(event_type: QEvent.Type, key: Qt.Key, *, auto_repeat: bool = False) -> QKeyEvent:
    return QKeyEvent(event_type, key, Qt.KeyboardModifier.NoModifier, "", auto_repeat)


def _mouse_event(event_type: QEvent.Type, button: Qt.MouseButton) -> QMouseEvent:
    buttons = button if event_type is QEvent.Type.MouseButtonPress else Qt.MouseButton.NoButton
    return QMouseEvent(
        event_type,
        QPointF(),
        QPointF(),
        button,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )
