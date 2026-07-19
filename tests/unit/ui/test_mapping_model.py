from PySide6.QtCore import Qt

from demi.application.settings_editor import SettingsEditor
from demi.domain.settings import AppSettings
from demi.ui.dialogs.mapping import MappingTableModel


def test_mapping_model_exposes_bindings_conflicts_and_draft_edits(qt_application: object) -> None:
    assert qt_application is not None
    editor = SettingsEditor(AppSettings.default())
    editor.update_binding(1, source="KEY:F")
    model = MappingTableModel(editor)

    assert model.rowCount() == 33
    assert model.columnCount() == 5
    assert model.data(model.index(0, 0), Qt.ItemDataRole.DisplayRole) == "BUTTON:A"
    assert model.data(model.index(0, 1), Qt.ItemDataRole.DisplayRole) == "KEY:F"
    assert model.data(model.index(0, 2), Qt.ItemDataRole.DisplayRole) == "No"
    assert model.data(model.index(0, 3), Qt.ItemDataRole.DisplayRole) == "Duplicate: KEY:F"
    assert model.data(model.index(1, 3), Qt.ItemDataRole.DisplayRole) == "Duplicate: KEY:F"
    assert model.data(model.index(28, 0), Qt.ItemDataRole.DisplayRole) == "GYRO:Y_NEGATIVE"
    assert model.data(model.index(28, 1), Qt.ItemDataRole.DisplayRole) == "KEY:I"
    assert model.data(model.index(32, 0), Qt.ItemDataRole.DisplayRole) == "ACCEL:ZERO"
    assert model.data(model.index(32, 1), Qt.ItemDataRole.DisplayRole) == "KEY:O"

    model.update_source(0, "KEY:1")

    assert editor.draft.profiles[0].bindings[0].source == "KEY:1"
    assert model.data(model.index(0, 1), Qt.ItemDataRole.DisplayRole) == "KEY:1"

    model.update_source(32, "KEY:P")

    assert editor.draft.profiles[0].bindings[32].source == "KEY:P"

    model.restore_default_profile()

    assert model.data(model.index(0, 1), Qt.ItemDataRole.DisplayRole) == "KEY:F"
    assert model.data(model.index(32, 1), Qt.ItemDataRole.DisplayRole) == "KEY:O"


def test_mapping_model_changes_only_the_armed_row_to_instruction_and_cancel(
    qt_application: object,
) -> None:
    assert qt_application is not None
    model = MappingTableModel(SettingsEditor(AppSettings.default()))
    unchanged_source = model.data(model.index(1, 1), Qt.ItemDataRole.DisplayRole)

    model.begin_capture(0)

    assert (
        model.data(model.index(0, 1), Qt.ItemDataRole.DisplayRole) == "Press a key or mouse button"
    )
    assert model.data(model.index(0, 4), Qt.ItemDataRole.DisplayRole) == "Cancel"
    assert model.data(model.index(1, 1), Qt.ItemDataRole.DisplayRole) == unchanged_source
    assert model.data(model.index(1, 4), Qt.ItemDataRole.DisplayRole) == "Remap"
