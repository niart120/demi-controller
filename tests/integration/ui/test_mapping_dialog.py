from dataclasses import dataclass, replace

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QMessageBox

from demi.application.coordinator import CaptureCoordinator
from demi.application.dialogs import DialogKind, DialogManager
from demi.application.settings_editor import SettingsEditor
from demi.application.settings_modal import SettingsModalController
from demi.application.state import AppState
from demi.config.errors import SettingsPersistenceError
from demi.domain.controller import ControllerFrame
from demi.domain.settings import AppSettings, InputSettings, MouseSettings
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
        assert dialog.capture_label.text() == "Input: KEY:A"
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

    assert model.data(model.index(0, 3), Qt.ItemDataRole.DisplayRole) == "Duplicate: KEY:F"
    assert model.data(model.index(2, 3), Qt.ItemDataRole.DisplayRole) == "Local action: CTRL+C"

    save_button = dialog.button_box.button(QDialogButtonBox.StandardButton.Save)
    assert save_button is not None
    save_button.click()
    qt_application.processEvents()

    confirmation = dialog.conflict_confirmation
    assert confirmation is not None
    assert confirmation.text() == "Mappings conflict with duplicates or local actions."
    assert confirmation.informativeText() == "Duplicate: KEY:F\nLocal action: CTRL+C"
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
    editor.update_binding(0, source="KEY:P")

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
    assert dialog.save_error_label.text() == "Could not save settings"
    assert modal.editor is editor
    assert editor.draft.profiles[0].bindings[0].source == "KEY:P"
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
    assert model.data(model.index(0, 2), Qt.ItemDataRole.DisplayRole) == "Yes"

    save_button = dialog.button_box.button(QDialogButtonBox.StandardButton.Save)
    assert save_button is not None
    save_button.click()
    qt_application.processEvents()

    assert saved_drafts[-1].profiles[0].bindings[0].inverted is True
    assert dialog.result() == int(QDialog.DialogCode.Accepted)


def test_mapping_dialog_exposes_configurable_imu_diagnostics(
    qt_application: QApplication,
) -> None:
    editor = SettingsEditor(AppSettings.default())
    dialog = MappingDialog(editor)
    dialog.show()
    qt_application.processEvents()
    model = dialog.table.model()
    assert model is not None

    assert model.rowCount() == 33
    assert model.data(model.index(28, 0), Qt.ItemDataRole.DisplayRole) == "GYRO:Y_NEGATIVE"
    assert model.data(model.index(28, 1), Qt.ItemDataRole.DisplayRole) == "KEY:I"
    assert model.data(model.index(32, 0), Qt.ItemDataRole.DisplayRole) == "ACCEL:ZERO"
    assert model.data(model.index(32, 1), Qt.ItemDataRole.DisplayRole) == "KEY:O"

    dialog.table.selectRow(32)
    qt_application.processEvents()

    assert not dialog.inverted_checkbox.isEnabled()
    assert dialog.set_source(32, "KEY:P") is True
    assert editor.draft.profiles[0].bindings[32].source == "KEY:P"

    dialog.close()
    qt_application.processEvents()


def test_mapping_dialog_exposes_and_edits_mouse_gyro_settings(
    qt_application: QApplication,
) -> None:
    settings = replace(
        AppSettings.default(),
        input=InputSettings(
            mouse=MouseSettings(
                gyro_enabled=False,
                horizontal_sensitivity=2.5,
                vertical_sensitivity=1.5,
                invert_x=True,
                invert_y=True,
                pitch_limit_degrees=60.0,
            )
        ),
    )
    editor = SettingsEditor(settings)
    dialog = MappingDialog(editor)
    dialog.show()
    qt_application.processEvents()

    assert dialog.mouse_gyro_group.title() == "Mouse gyro settings"
    assert not dialog.mouse_gyro_enabled_checkbox.isChecked()
    assert dialog.horizontal_sensitivity_spinbox.value() == 2.5
    assert dialog.vertical_sensitivity_spinbox.value() == 1.5
    assert dialog.invert_x_checkbox.isChecked()
    assert dialog.invert_y_checkbox.isChecked()
    assert dialog.pitch_limit_spinbox.value() == 60.0
    assert dialog.horizontal_sensitivity_spinbox.minimum() == 0.1
    assert dialog.horizontal_sensitivity_spinbox.maximum() == 10.0
    assert dialog.vertical_sensitivity_spinbox.minimum() == 0.1
    assert dialog.vertical_sensitivity_spinbox.maximum() == 10.0
    assert dialog.pitch_limit_spinbox.minimum() == 1.0
    assert dialog.pitch_limit_spinbox.maximum() == 89.0

    dialog.mouse_gyro_enabled_checkbox.setChecked(True)
    dialog.horizontal_sensitivity_spinbox.setValue(3.0)
    dialog.vertical_sensitivity_spinbox.setValue(4.0)
    dialog.invert_x_checkbox.setChecked(False)
    dialog.invert_y_checkbox.setChecked(False)
    dialog.pitch_limit_spinbox.setValue(45.0)
    qt_application.processEvents()

    assert editor.draft.input.mouse == MouseSettings(
        gyro_enabled=True,
        horizontal_sensitivity=3.0,
        vertical_sensitivity=4.0,
        invert_x=False,
        invert_y=False,
        pitch_limit_degrees=45.0,
    )

    dialog.close()
    qt_application.processEvents()


def test_mapping_dialog_uses_standard_keyboard_navigation_and_dialog_actions(
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
    dialog.inverted_checkbox.setFocus()

    _send_key(dialog.inverted_checkbox, Qt.Key.Key_Tab)
    qt_application.processEvents()
    assert qt_application.focusWidget() is dialog.capture_button

    _send_key(dialog.capture_button, Qt.Key.Key_Backtab, Qt.KeyboardModifier.ShiftModifier)
    qt_application.processEvents()
    assert qt_application.focusWidget() is dialog.inverted_checkbox

    _send_key(dialog.inverted_checkbox, Qt.Key.Key_Space)
    qt_application.processEvents()
    assert editor.draft.profiles[0].bindings[0].inverted is True

    save_button = dialog.button_box.button(QDialogButtonBox.StandardButton.Save)
    assert save_button is not None
    save_button.setFocus()
    _send_key(save_button, Qt.Key.Key_Return)
    qt_application.processEvents()

    assert saved_drafts[-1].profiles[0].bindings[0].inverted is True
    assert dialog.result() == int(QDialog.DialogCode.Accepted)

    escaped = MappingDialog(SettingsEditor(AppSettings.default()))
    escaped.show()
    qt_application.processEvents()
    escaped.table.setFocus()
    _send_key(escaped.table, Qt.Key.Key_Escape)
    qt_application.processEvents()

    assert escaped.result() == int(QDialog.DialogCode.Rejected)


def test_mapping_dialog_shows_default_columns_without_text_clipping(
    qt_application: QApplication,
) -> None:
    """Keep the default mapping columns readable without horizontal scrolling."""
    dialog = MappingDialog(SettingsEditor(AppSettings.default()))
    dialog.show()
    qt_application.processEvents()
    model = dialog.table.model()
    assert model is not None
    header = dialog.table.horizontalHeader()
    font_metrics = dialog.table.fontMetrics()

    for column in range(model.columnCount()):
        visible_text = [
            str(model.headerData(column, Qt.Orientation.Horizontal)),
            *(str(model.data(model.index(row, column))) for row in range(model.rowCount())),
        ]
        required_width = max(font_metrics.horizontalAdvance(text) for text in visible_text)

        assert header.sectionSize(column) >= required_width

    assert dialog.table.horizontalScrollBar().maximum() == 0
    dialog.close()
    qt_application.processEvents()


def _send_key(
    target: QObject,
    key: Qt.Key,
    modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
) -> None:
    QCoreApplication.sendEvent(target, QKeyEvent(QEvent.Type.KeyPress, key, modifiers))
    QCoreApplication.sendEvent(target, QKeyEvent(QEvent.Type.KeyRelease, key, modifiers))
