from PySide6.QtCore import Qt

from demi.application.settings_editor import SettingsEditor
from demi.domain.settings import AppSettings
from demi.ui.dialogs.mapping import MappingTableModel


def test_mapping_model_exposes_bindings_conflicts_and_draft_edits(qt_application: object) -> None:
    assert qt_application is not None
    editor = SettingsEditor(AppSettings.default())
    editor.update_binding(1, source="KEY:F")
    model = MappingTableModel(editor)

    assert model.rowCount() == 28
    assert model.columnCount() == 4
    assert model.data(model.index(0, 0), Qt.ItemDataRole.DisplayRole) == "BUTTON:A"
    assert model.data(model.index(0, 1), Qt.ItemDataRole.DisplayRole) == "KEY:F"
    assert model.data(model.index(0, 2), Qt.ItemDataRole.DisplayRole) == "いいえ"
    assert model.data(model.index(0, 3), Qt.ItemDataRole.DisplayRole) == "重複: KEY:F"
    assert model.data(model.index(1, 3), Qt.ItemDataRole.DisplayRole) == "重複: KEY:F"

    model.update_source(0, "KEY:1")

    assert editor.draft.profiles[0].bindings[0].source == "KEY:1"
    assert model.data(model.index(0, 1), Qt.ItemDataRole.DisplayRole) == "KEY:1"

    model.restore_default_profile()

    assert model.data(model.index(0, 1), Qt.ItemDataRole.DisplayRole) == "KEY:F"
