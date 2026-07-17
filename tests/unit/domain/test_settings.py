from collections.abc import Callable
from typing import cast

import pytest

from demi.domain.controller import LogicalButton
from demi.domain.errors import DomainValueError
from demi.domain.mapping import Binding, BindingTarget, InputProfile
from demi.domain.settings import (
    AppSettings,
    ConnectionSettings,
    ControllerColorSettings,
    ControllerType,
    DiagnosticLevel,
    InputSettings,
    MouseSettings,
    WindowSettings,
)


def test_default_settings_match_the_initial_configuration() -> None:
    settings = AppSettings.default()

    assert settings.schema == "demi.settings/v1"
    assert settings.active_profile == "default"
    assert settings.window == WindowSettings(width=960, height=640, maximized=False)
    assert settings.connection.adapter_id == ""
    assert settings.connection.controller is ControllerType.PRO_CONTROLLER
    assert settings.connection.bond_slot == "default"
    assert settings.connection.timeout_seconds == 30.0
    assert settings.connection.reconnect_on_start is False
    assert settings.connection.diagnostic_level is DiagnosticLevel.INFO
    assert settings.controller_colors == ControllerColorSettings(
        body="#323232",
        buttons="#0F0F0F",
        left_grip="#323232",
        right_grip="#323232",
    )
    assert settings.input.evaluation_interval_ms == 8
    assert settings.input.circular_stick_limit is False
    assert settings.input.mouse == MouseSettings(
        gyro_enabled=True,
        horizontal_sensitivity=1.0,
        vertical_sensitivity=1.0,
        invert_y=False,
        pitch_limit_degrees=75.0,
    )
    assert settings.local_actions.connection == ("CTRL+RETURN", "CTRL+ENTER")
    assert settings.profiles[0].name == "Default"
    assert len(settings.profiles[0].bindings) == 33


def test_color_values_are_normalized_to_uppercase_hex() -> None:
    colors = ControllerColorSettings(
        body="#abcdef",
        buttons="#000000",
        left_grip="#123456",
        right_grip="#FFFFFF",
    )

    assert colors.body == "#ABCDEF"
    assert colors.left_grip == "#123456"


@pytest.mark.parametrize(
    "factory",
    [
        lambda: WindowSettings(width=799),
        lambda: WindowSettings(height=4321),
        lambda: ConnectionSettings(timeout_seconds=0.9),
        lambda: ConnectionSettings(bond_slot="../escape"),
        lambda: ControllerColorSettings(body="#12345"),
        lambda: MouseSettings(horizontal_sensitivity=0.09),
        lambda: MouseSettings(pitch_limit_degrees=89.1),
        lambda: InputSettings(evaluation_interval_ms=33),
        lambda: ConnectionSettings(controller=cast("ControllerType", "joy_con")),
    ],
)
def test_settings_reject_values_outside_the_schema_constraints(
    factory: Callable[[], object],
) -> None:
    with pytest.raises(DomainValueError):
        factory()


def test_app_settings_rejects_unknown_active_profile_or_duplicate_profile_ids() -> None:
    profile = InputProfile(
        id="alternate",
        name="Alternate",
        builtin=False,
        bindings=(Binding(source="KEY:F", target=BindingTarget.BUTTON_A),),
    )

    with pytest.raises(DomainValueError):
        AppSettings(active_profile="missing", profiles=(profile,))
    with pytest.raises(DomainValueError):
        AppSettings(profiles=(profile, profile))


def test_profile_binding_targets_are_independent_from_logical_button_values() -> None:
    settings = AppSettings.default()
    button_targets = {
        binding.target.value
        for binding in settings.profiles[0].bindings
        if binding.target.value.startswith("BUTTON:")
    }

    assert "BUTTON:A" in button_targets
    assert LogicalButton.A.value not in button_targets
