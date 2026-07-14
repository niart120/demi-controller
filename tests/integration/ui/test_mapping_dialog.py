from dataclasses import dataclass

from PySide6.QtCore import QCoreApplication, QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QMessageBox

from demi.application.coordinator import CaptureCoordinator
from demi.application.dialogs import DialogKind, DialogManager
from demi.application.settings_editor import SettingsEditor
from demi.application.settings_modal import SettingsModalController
from demi.application.state import AppState
from demi.config.errors import SettingsPersistenceError
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


@dataclass
class FakeRepository:
    """Keep the saved snapshot intact when the configured save fails."""

    saved: AppSettings
    fail_save: bool = False
    save_calls: int = 0

    def save(self, settings: AppSettings) -> None:
        """Persist a replacement snapshot unless the failure switch is set."""
        self.save_calls += 1
        if self.fail_save:
            raise SettingsPersistenceError
        self.saved = settings


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


def test_mapping_dialog_keeps_a_failed_draft_and_cancel_does_not_save(
    qt_application: QApplication,
) -> None:
    original = AppSettings.default()
    repository = FakeRepository(saved=original, fail_save=True)
    coordinator = CaptureCoordinator(
        publisher=InputPublisher(clock=FakeClock(), sink=FakeSink(frames=[])),
        pointer_capture=FakeWindow(),
    )
    modal = SettingsModalController(repository, coordinator, DialogManager())
    assert modal.open(DialogKind.MAPPING, original) is True
    editor = modal.editor
    assert editor is not None
    editor.update_binding(0, source="KEY:K")

    def save_modal() -> bool:
        try:
            modal.save()
        except SettingsPersistenceError:
            return False
        return True

    dialog = MappingDialog(editor, on_save=save_modal, on_cancel=modal.cancel)
    dialog.show()
    qt_application.processEvents()
    save_button = dialog.button_box.button(QDialogButtonBox.StandardButton.Save)
    assert save_button is not None
    save_button.click()
    qt_application.processEvents()

    assert dialog.isVisible()
    assert dialog.save_error_label.text() == "設定を保存できませんでした"
    assert modal.editor is editor
    assert editor.draft.profiles[0].bindings[0].source == "KEY:K"
    assert repository.saved == original
    assert repository.save_calls == 1

    cancel_button = dialog.button_box.button(QDialogButtonBox.StandardButton.Cancel)
    assert cancel_button is not None
    cancel_button.click()
    qt_application.processEvents()

    assert not dialog.isVisible()
    assert modal.editor is None
    assert repository.saved == original
    assert repository.save_calls == 1


def test_mapping_dialog_exposes_and_saves_an_inverted_binding(
    qt_application: QApplication,
) -> None:
    editor = SettingsEditor(AppSettings.default())
    saved_drafts: list[AppSettings] = []

    def save() -> bool:
        saved_drafts.append(editor.draft)
        return True

    dialog = MappingDialog(editor, on_save=save)
    dialog.show()
    qt_application.processEvents()
    dialog.table.selectRow(0)
    qt_application.processEvents()

    assert dialog.inverted_checkbox.isEnabled()
    assert not dialog.inverted_checkbox.isChecked()

    dialog.inverted_checkbox.click()
    qt_application.processEvents()

    assert editor.draft.profiles[0].bindings[0].inverted is True
    model = dialog.table.model()
    assert model is not None
    assert model.data(model.index(0, 2), Qt.ItemDataRole.DisplayRole) == "はい"

    save_button = dialog.button_box.button(QDialogButtonBox.StandardButton.Save)
    assert save_button is not None
    save_button.click()
    qt_application.processEvents()

    assert saved_drafts[-1].profiles[0].bindings[0].inverted is True
    assert dialog.result() == int(QDialog.DialogCode.Accepted)
