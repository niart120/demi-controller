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
    assert model.data(model.index(0, 1), Qt.ItemDataRole.DisplayRole) == "F"
    assert model.data(model.index(0, 1), Qt.ItemDataRole.UserRole) == "KEY:F"
    assert model.data(model.index(0, 1), Qt.ItemDataRole.ToolTipRole) == "KEY:F"
    assert model.data(model.index(4, 1), Qt.ItemDataRole.DisplayRole) == "Middle mouse"
    assert model.data(model.index(0, 2), Qt.ItemDataRole.DisplayRole) is None
    assert model.data(model.index(0, 3), Qt.ItemDataRole.DisplayRole) == "Duplicate: KEY:F"
    assert model.data(model.index(1, 3), Qt.ItemDataRole.DisplayRole) == "Duplicate: KEY:F"
    assert model.data(model.index(28, 0), Qt.ItemDataRole.DisplayRole) == "GYRO:Y_NEGATIVE"
    assert model.data(model.index(28, 1), Qt.ItemDataRole.DisplayRole) == "I"
    assert model.data(model.index(32, 0), Qt.ItemDataRole.DisplayRole) == "ACCEL:ZERO"
    assert model.data(model.index(32, 1), Qt.ItemDataRole.DisplayRole) == "O"

    model.update_source(0, "KEY:1")

    assert editor.draft.profiles[0].bindings[0].source == "KEY:1"
    assert model.data(model.index(0, 1), Qt.ItemDataRole.DisplayRole) == "1"

    model.update_source(32, "KEY:P")

    assert editor.draft.profiles[0].bindings[32].source == "KEY:P"

    model.restore_default_profile()

    assert model.data(model.index(0, 1), Qt.ItemDataRole.DisplayRole) == "F"
    assert model.data(model.index(32, 1), Qt.ItemDataRole.DisplayRole) == "O"


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


def test_mapping_model_clears_transient_status_when_capture_moves_or_stops(
    qt_application: object,
) -> None:
    assert qt_application is not None
    model = MappingTableModel(SettingsEditor(AppSettings.default()))
    status_index = model.index(0, 3)

    model.begin_capture(0)
    model.set_row_status(0, "F4 is reserved")
    model.begin_capture(1)

    assert model.data(status_index, Qt.ItemDataRole.DisplayRole) == ""

    model.set_row_status(1, "Input cannot be assigned")
    model.cancel_capture()

    assert model.data(model.index(1, 3), Qt.ItemDataRole.DisplayRole) == ""


def test_mapping_model_toggles_inverted_in_the_table_only_for_button_targets(
    qt_application: object,
) -> None:
    assert qt_application is not None
    editor = SettingsEditor(AppSettings.default())
    model = MappingTableModel(editor)
    button_inverted = model.index(0, 2)
    diagnostic_inverted = model.index(28, 2)

    assert model.data(button_inverted, Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Unchecked
    assert model.flags(button_inverted) & Qt.ItemFlag.ItemIsUserCheckable
    assert model.data(diagnostic_inverted, Qt.ItemDataRole.CheckStateRole) is None
    assert not model.flags(diagnostic_inverted) & Qt.ItemFlag.ItemIsUserCheckable

    assert model.setData(
        button_inverted,
        Qt.CheckState.Checked,
        Qt.ItemDataRole.CheckStateRole,
    )

    assert editor.draft.profiles[0].bindings[0].inverted is True
    assert model.data(button_inverted, Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked
    assert not model.setData(
        diagnostic_inverted,
        Qt.CheckState.Checked,
        Qt.ItemDataRole.CheckStateRole,
    )
