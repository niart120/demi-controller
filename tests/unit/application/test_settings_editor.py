import pytest

from demi.application.settings_editor import SettingsEditor
from demi.domain.errors import DomainValueError
from demi.domain.mapping import BindingTarget, default_profile
from demi.domain.settings import AppSettings, DiagnosticLevel


def test_editor_updates_binding_connection_and_color_as_a_new_draft() -> None:
    editor = SettingsEditor(AppSettings.default())

    editor.update_binding(0, source="KEY:1", inverted=False)
    editor.update_connection(
        adapter_id="usb:0",
        bond_slot="office",
        timeout_seconds=45.0,
        reconnect_on_start=True,
        diagnostic_level=DiagnosticLevel.DEBUG,
    )
    editor.update_color("body", "#abcdef")

    draft = editor.draft
    assert draft.profiles[0].bindings[0].source == "KEY:1"
    assert draft.connection.adapter_id == "usb:0"
    assert draft.connection.bond_slot == "office"
    assert draft.connection.timeout_seconds == 45.0
    assert draft.connection.reconnect_on_start is True
    assert draft.connection.diagnostic_level is DiagnosticLevel.DEBUG
    assert draft.controller_colors.body == "#ABCDEF"


def test_editor_rejects_f4_allows_f12_and_restores_the_default_profile() -> None:
    editor = SettingsEditor(AppSettings.default())
    editor.update_binding(0, source="KEY:1", target=BindingTarget.BUTTON_B)

    with pytest.raises(DomainValueError):
        editor.update_binding(0, source="KEY:F4")

    editor.update_binding(0, source="KEY:F12")
    assert editor.draft.profiles[0].bindings[0].source == "KEY:F12"

    editor.reset_profile()

    assert editor.draft.profiles == (default_profile(),)
    assert editor.draft.active_profile == "default"


def test_editor_reports_duplicate_source_and_local_action_conflicts_only() -> None:
    editor = SettingsEditor(AppSettings.default())
    editor.update_binding(1, source="KEY:F")
    editor.update_binding(2, source="KEY:CTRL+C")

    conflicts = editor.conflicts()

    assert conflicts[0].source == "KEY:F"
    assert conflicts[0].binding_indices == (0, 1)
    assert conflicts[0].local_action is None
    assert conflicts[1].source == "KEY:CTRL+C"
    assert conflicts[1].binding_indices == (2,)
    assert conflicts[1].local_action == "CTRL+C"
    assert all(conflict.source != "KEY:V" for conflict in conflicts)


def test_editor_replaces_a_duplicate_source_and_unassigns_the_old_row() -> None:
    editor = SettingsEditor(AppSettings.default())

    editor.replace_binding_source(0, "KEY:V")

    assert editor.draft.profiles[0].bindings[0].source == "KEY:V"
    assert editor.draft.profiles[0].bindings[1].source == "KEY:UNASSIGNED"


def test_editor_adds_and_removes_binding_rows_without_treating_unassigned_as_a_conflict() -> None:
    editor = SettingsEditor(AppSettings.default())
    original_bindings = editor.draft.profiles[0].bindings

    editor.add_binding(BindingTarget.BUTTON_A)
    editor.add_binding(BindingTarget.RIGHT_STICK_UP)

    added_bindings = editor.draft.profiles[0].bindings
    assert added_bindings[:-2] == original_bindings
    assert added_bindings[-2].source == "KEY:UNASSIGNED"
    assert added_bindings[-2].target is BindingTarget.BUTTON_A
    assert added_bindings[-2].amount == 1.0
    assert added_bindings[-2].inverted is False
    assert added_bindings[-1].target is BindingTarget.RIGHT_STICK_UP
    assert all(conflict.source != "KEY:UNASSIGNED" for conflict in editor.conflicts())

    editor.remove_binding(len(original_bindings))

    assert editor.draft.profiles[0].bindings == (*original_bindings, added_bindings[-1])


@pytest.mark.parametrize("index", [-1, len(default_profile().bindings)])
def test_editor_rejects_removing_a_binding_outside_the_active_profile(index: int) -> None:
    editor = SettingsEditor(AppSettings.default())
    original = editor.draft

    with pytest.raises(DomainValueError):
        editor.remove_binding(index)

    assert editor.draft == original


@pytest.mark.parametrize("source", ["KEY:CTRL+RETURN", "KEY:CTRL+ENTER"])
def test_editor_reports_connection_shortcut_conflicts(source: str) -> None:
    editor = SettingsEditor(AppSettings.default())
    editor.update_binding(0, source=source)

    conflicts = editor.conflicts()

    assert len(conflicts) == 1
    assert conflicts[0].source == source
    assert conflicts[0].binding_indices == (0,)
    assert conflicts[0].local_action == source.removeprefix("KEY:")


def test_editor_updates_mouse_settings_without_changing_other_mouse_fields() -> None:
    editor = SettingsEditor(AppSettings.default())

    editor.update_mouse(
        gyro_enabled=False,
        horizontal_sensitivity=2.5,
        invert_x=True,
        invert_y=True,
    )

    mouse = editor.draft.input.mouse
    assert mouse.gyro_enabled is False
    assert mouse.horizontal_sensitivity == 2.5
    assert mouse.vertical_sensitivity == 1.0
    assert mouse.invert_x is True
    assert mouse.invert_y is True
    assert mouse.pitch_limit_degrees == 75.0


def test_editor_updates_input_settings_without_changing_mouse_settings() -> None:
    editor = SettingsEditor(AppSettings.default())
    editor.update_mouse(
        gyro_enabled=False,
        horizontal_sensitivity=2.5,
        vertical_sensitivity=1.5,
        invert_x=True,
        invert_y=True,
        pitch_limit_degrees=60.0,
    )
    existing_mouse = editor.draft.input.mouse

    editor.update_input(evaluation_interval_ms=16, circular_stick_limit=True)

    input_settings = editor.draft.input
    assert input_settings.evaluation_interval_ms == 16
    assert input_settings.circular_stick_limit is True
    assert input_settings.mouse == existing_mouse


def test_editor_rejects_invalid_input_settings_without_replacing_the_draft() -> None:
    editor = SettingsEditor(AppSettings.default())
    original_input = editor.draft.input

    with pytest.raises(DomainValueError):
        editor.update_input(evaluation_interval_ms=3)

    assert editor.draft.input == original_input
