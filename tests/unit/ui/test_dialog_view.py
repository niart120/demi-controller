from dataclasses import replace

from demi.application.dialogs import DialogKind, DialogManager
from demi.application.presentation import AdapterOption
from demi.application.settings_editor import SettingsEditor
from demi.domain.settings import AppSettings
from demi.ui.dialogs import ModalAction, ModalRenderer, build_dialog_view_model


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


def test_modal_renderer_exposes_enabled_save_and_cancel_hit_targets() -> None:
    dialogs = DialogManager()
    assert dialogs.open(DialogKind.COLORS) is True
    renderer = ModalRenderer()
    model = build_dialog_view_model(dialogs, SettingsEditor(AppSettings.default()))

    controls = renderer.controls(model, width=960, height=640)
    cancel = next(control for control in controls if control.action is ModalAction.CANCEL)
    save = next(control for control in controls if control.action is ModalAction.SAVE)

    assert cancel.enabled is True
    assert save.enabled is True
    assert renderer.hit_test(cancel.x + 1, cancel.y + 1, width=960, height=640) == cancel
    assert renderer.hit_test(save.x + 1, save.y + 1, width=960, height=640) == save


def test_mapping_model_exposes_binding_mouse_and_paged_edit_controls() -> None:
    dialogs = DialogManager()
    assert dialogs.open(DialogKind.MAPPING) is True
    editor = SettingsEditor(AppSettings.default())

    model = build_dialog_view_model(dialogs, editor)
    fields = {field.key: field for field in model.fields}

    assert fields["binding.0"].label == "A"
    assert fields["binding.0"].value == "KEY:F"
    assert fields["binding.0"].action is ModalAction.CAPTURE_BINDING
    assert fields["binding.0"].secondary_action is ModalAction.TOGGLE_BINDING_INVERSION
    assert fields["mouse.gyro_enabled"].value == "有効"
    assert fields["mouse.horizontal_sensitivity"].value == "1 倍"
    assert fields["mouse.vertical_sensitivity"].value == "1 倍"
    assert fields["mouse.invert_y"].value == "無効"

    renderer = ModalRenderer()
    controls = renderer.controls(model, width=960, height=640)
    capture = next(
        control
        for control in controls
        if control.action is ModalAction.CAPTURE_BINDING and control.target == "0"
    )
    invert = next(
        control
        for control in controls
        if control.action is ModalAction.TOGGLE_BINDING_INVERSION and control.target == "0"
    )
    next_page = next(control for control in controls if control.action is ModalAction.NEXT_PAGE)

    assert capture.enabled is True
    assert invert.enabled is True
    assert any(control.action is ModalAction.RESET_PROFILE for control in controls)
    assert renderer.hit_test(next_page.x + 1, next_page.y + 1, width=960, height=640) == next_page
    assert renderer.fields_for_page(model)[0].key == "binding.4"


def test_connection_and_pairing_models_expose_adapter_selection_and_confirmation() -> None:
    settings = replace(
        AppSettings.default(),
        connection=replace(AppSettings.default().connection, adapter_id="usb:1"),
    )
    adapters = (
        AdapterOption(id="usb:0", label="内蔵アダプター"),
        AdapterOption(id="usb:1", label="専用アダプター"),
    )
    dialogs = DialogManager()
    assert dialogs.open(DialogKind.CONNECTION) is True
    editor = SettingsEditor(settings)

    model = build_dialog_view_model(dialogs, editor, adapters=adapters)
    fields = {field.key: field for field in model.fields}
    renderer = ModalRenderer()
    controls = renderer.controls(model, width=960, height=640)

    assert fields["connection.adapter_id"].value == "専用アダプター (usb:1)"
    assert fields["adapter.usb:1"].action_label == "選択中"
    assert model.pairing_enabled is True
    assert any(
        control.action is ModalAction.SELECT_ADAPTER and control.target == "usb:0"
        for control in controls
    )
    assert next(
        control for control in controls if control.action is ModalAction.RESCAN_ADAPTERS
    ).enabled
    assert next(
        control for control in controls if control.action is ModalAction.REQUEST_PAIRING
    ).enabled

    assert dialogs.replace(DialogKind.PAIRING_CONFIRMATION) is True
    pairing_model = build_dialog_view_model(dialogs, editor, adapters=adapters)
    pairing_controls = renderer.controls(pairing_model, width=960, height=640)

    assert pairing_model.instructions[0] == "対象機器側でコントローラー登録画面を開いてください。"
    assert next(
        control for control in pairing_controls if control.action is ModalAction.CANCEL_PAIRING
    ).enabled
    assert next(
        control for control in pairing_controls if control.action is ModalAction.CONFIRM_PAIRING
    ).enabled


def test_colors_and_pending_reconnect_prompt_expose_separate_actions() -> None:
    dialogs = DialogManager()
    assert dialogs.open(DialogKind.COLORS) is True
    renderer = ModalRenderer()
    model = build_dialog_view_model(dialogs, SettingsEditor(AppSettings.default()))
    controls = renderer.controls(model, width=960, height=640)
    fields = {field.key: field for field in model.fields}

    assert fields["color.body"].value == "#323232"
    assert fields["color.buttons"].value == "#0F0F0F"
    assert any(
        control.action is ModalAction.EDIT_FIELD and control.target == "color.left_grip"
        for control in controls
    )

    dialogs.close()
    prompt = build_dialog_view_model(dialogs, color_reconnect_pending=True)
    prompt_controls = renderer.controls(prompt, width=960, height=640)
    reconnect = next(
        control
        for control in prompt_controls
        if control.action is ModalAction.REQUEST_COLOR_RECONNECT
    )

    assert prompt.visible is True
    assert prompt.kind is DialogKind.NONE
    assert prompt.color_reconnect_prompt is True
    assert prompt.instructions == (
        "表示色は更新済みです。",
        "対象機器へ反映するにはコントローラーを再接続します。",
    )
    assert any(control.action is ModalAction.DEFER_COLOR_RECONNECT for control in prompt_controls)
    assert renderer.hit_test(reconnect.x + 1, reconnect.y + 1, width=960, height=640) == reconnect
