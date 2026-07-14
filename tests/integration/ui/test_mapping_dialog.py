from dataclasses import dataclass

from PySide6.QtCore import QCoreApplication, QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QMessageBox

from demi.application.coordinator import CaptureCoordinator
from demi.application.settings_editor import SettingsEditor
from demi.application.state import AppState
from demi.domain.controller import ControllerFrame
from demi.domain.settings import AppSettings
from demi.input.publisher import InputPublisher
from demi.input.qt_adapter import QtInputAdapter
from demi.ui.dialogs.mapping import MappingDialog


@dataclass
class FakeClock:
    """Provide a stable clock for capture-neutralization assertions."""

    def monotonic_ns(self) -> int:
        """Return an arbitrary stable timestamp."""
        return 1_000_000_000


@dataclass
class FakeSink:
    """Record frames emitted while the mapping dialog opens."""

    frames: list[ControllerFrame]

    def offer_frame(self, frame: ControllerFrame) -> None:
        """Store one controller frame."""
        self.frames.append(frame)


@dataclass
class FakeWindow:
    """Satisfy pointer capture without manipulating the test display."""

    def set_pointer_capture(self, enabled: bool) -> None:
        """Accept a requested pointer capture transition."""


def test_mapping_dialog_captures_only_an_explicit_next_input_and_reserves_f12(
    qt_application: QApplication,
) -> None:
    editor = SettingsEditor(AppSettings.default())
    sink = FakeSink(frames=[])
    coordinator = CaptureCoordinator(
        publisher=InputPublisher(clock=FakeClock(), sink=sink),
        pointer_capture=FakeWindow(),
    )
    adapter = QtInputAdapter(
        state=coordinator.publisher.state,
        is_captured=lambda: coordinator.is_captured,
        on_stop_capture=coordinator.stop_capture,
        on_dialog_opened=coordinator.open_configuration,
    )
    release_requests: list[bool] = []
    dialog = MappingDialog(
        editor,
        on_dialog_opened=adapter.on_dialog_opened,
        on_release_capture=lambda: release_requests.append(True),
    )
    qt_application.installEventFilter(adapter)
    try:
        assert coordinator.start_capture() is True
        dialog.show()
        qt_application.processEvents()

        assert coordinator.app_state is AppState.CONFIGURING
        assert coordinator.publisher.state.held_keys == set()

        QCoreApplication.sendEvent(
            dialog.table,
            QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier),
        )
        assert editor.draft.profiles[0].bindings[0].source == "KEY:F"
        assert coordinator.publisher.state.held_keys == set()

        dialog.table.selectRow(0)
        dialog.capture_button.click()
        QCoreApplication.sendEvent(
            dialog.table,
            QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier),
        )

        assert editor.draft.profiles[0].bindings[0].source == "KEY:A"
        assert dialog.capture_label.text() == "入力: KEY:A"
        assert coordinator.publisher.state.held_keys == set()

        dialog.capture_button.click()
        QCoreApplication.sendEvent(
            dialog.table,
            QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_F12, Qt.KeyboardModifier.NoModifier),
        )

        assert editor.draft.profiles[0].bindings[0].source == "KEY:A"
        assert release_requests == [True]

        dialog.table.selectRow(1)
        dialog.capture_button.click()
        QCoreApplication.sendEvent(
            dialog.table,
            QMouseEvent(
                QEvent.Type.MouseButtonPress,
                QPointF(10.0, 10.0),
                QPointF(10.0, 10.0),
                Qt.MouseButton.RightButton,
                Qt.MouseButton.RightButton,
                Qt.KeyboardModifier.NoModifier,
            ),
        )

        assert editor.draft.profiles[0].bindings[1].source == "MOUSE:RIGHT"
        assert coordinator.publisher.state.held_mouse_buttons == set()
    finally:
        dialog.close()
        qt_application.processEvents()
        qt_application.removeEventFilter(adapter)


def test_mapping_dialog_requires_explicit_confirmation_for_binding_conflicts(
    qt_application: QApplication,
) -> None:
    editor = SettingsEditor(AppSettings.default())
    editor.update_binding(1, source="KEY:F")
    editor.update_binding(2, source="KEY:CTRL+C")
    dialog = MappingDialog(editor)
    dialog.show()
    qt_application.processEvents()
    model = dialog.table.model()
    assert model is not None

    assert model.data(model.index(0, 3), Qt.ItemDataRole.DisplayRole) == "重複: KEY:F"
    assert model.data(model.index(2, 3), Qt.ItemDataRole.DisplayRole) == "ローカル操作: CTRL+C"

    save_button = dialog.button_box.button(QDialogButtonBox.StandardButton.Save)
    assert save_button is not None
    save_button.click()
    qt_application.processEvents()

    confirmation = dialog.conflict_confirmation
    assert confirmation is not None
    assert confirmation.text() == "重複またはローカル操作との競合があります。"
    assert confirmation.informativeText() == "重複: KEY:F\nローカル操作: CTRL+C"
    assert dialog.isVisible()

    cancel_button = confirmation.button(QMessageBox.StandardButton.Cancel)
    assert cancel_button is not None
    cancel_button.click()
    qt_application.processEvents()

    assert dialog.conflict_confirmation is None
    assert dialog.isVisible()
    assert dialog.result() == int(QDialog.DialogCode.Rejected)

    save_button.click()
    qt_application.processEvents()
    confirmation = dialog.conflict_confirmation
    assert confirmation is not None
    confirmed_save_button = confirmation.button(QMessageBox.StandardButton.Save)
    assert confirmed_save_button is not None
    confirmed_save_button.click()
    qt_application.processEvents()

    assert dialog.result() == int(QDialog.DialogCode.Accepted)
    assert not dialog.isVisible()
