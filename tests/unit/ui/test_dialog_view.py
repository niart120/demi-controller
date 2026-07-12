from demi.application.dialogs import DialogKind, DialogManager
from demi.application.settings_editor import SettingsEditor
from demi.domain.settings import AppSettings
from demi.ui.dialogs import build_dialog_view_model


def test_dialog_view_model_exposes_conflict_warning_without_display_dependencies() -> None:
    dialogs = DialogManager()
    editor = SettingsEditor(AppSettings.default())
    editor.update_binding(1, source="KEY:F")
    assert dialogs.open(DialogKind.MAPPING) is True

    model = build_dialog_view_model(dialogs, editor)

    assert model.visible is True
    assert model.title == "キー割り当て"
    assert model.save_enabled is True
    assert model.warning == "割り当ての競合: 1件"


def test_closed_dialog_view_model_has_no_save_action_or_warning() -> None:
    model = build_dialog_view_model(DialogManager())

    assert model.kind is DialogKind.NONE
    assert model.visible is False
    assert model.save_enabled is False
    assert model.warning == ""
