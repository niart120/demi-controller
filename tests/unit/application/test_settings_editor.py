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


def test_editor_rejects_f12_binding_and_restores_the_default_profile() -> None:
    editor = SettingsEditor(AppSettings.default())
    editor.update_binding(0, source="KEY:1", target=BindingTarget.BUTTON_B)

    with pytest.raises(DomainValueError):
        editor.update_binding(0, source="KEY:F12")

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


def test_editor_updates_mouse_settings_without_changing_other_mouse_fields() -> None:
    editor = SettingsEditor(AppSettings.default())

    editor.update_mouse(gyro_enabled=False, horizontal_sensitivity=2.5, invert_y=True)

    mouse = editor.draft.input.mouse
    assert mouse.gyro_enabled is False
    assert mouse.horizontal_sensitivity == 2.5
    assert mouse.vertical_sensitivity == 1.0
    assert mouse.invert_y is True
    assert mouse.pitch_limit_degrees == 75.0


def test_editor_updates_input_settings_without_changing_mouse_settings() -> None:
    editor = SettingsEditor(AppSettings.default())
    editor.update_mouse(
        gyro_enabled=False,
        horizontal_sensitivity=2.5,
        vertical_sensitivity=1.5,
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
