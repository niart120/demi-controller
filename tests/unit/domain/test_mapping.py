import pytest

from demi.domain.controller import LogicalButton
from demi.domain.errors import DomainValueError
from demi.domain.mapping import (
    Binding,
    BindingTarget,
    default_profile,
    logical_button_for_target,
)


def test_default_profile_contains_the_documented_bindings_in_order() -> None:
    profile = default_profile()

    assert profile.id == "default"
    assert profile.name == "Default"
    assert profile.builtin is True
    assert [(binding.source, binding.target.value) for binding in profile.bindings] == [
        ("KEY:F", "BUTTON:A"),
        ("KEY:V", "BUTTON:B"),
        ("KEY:SPACE", "BUTTON:B"),
        ("KEY:E", "BUTTON:X"),
        ("MOUSE:MIDDLE", "BUTTON:Y"),
        ("KEY:R", "BUTTON:R"),
        ("KEY:Q", "BUTTON:L"),
        ("MOUSE:LEFT", "BUTTON:ZR"),
        ("MOUSE:RIGHT", "BUTTON:ZL"),
        ("KEY:TAB", "BUTTON:ZL"),
        ("KEY:LEFT_SHIFT", "BUTTON:ZL"),
        ("KEY:Z", "BUTTON:MINUS"),
        ("KEY:X", "BUTTON:PLUS"),
        ("KEY:F1", "BUTTON:HOME"),
        ("KEY:T", "BUTTON:RIGHT_STICK"),
        ("KEY:G", "BUTTON:LEFT_STICK"),
        ("KEY:W", "LEFT_STICK:UP"),
        ("KEY:A", "LEFT_STICK:LEFT"),
        ("KEY:S", "LEFT_STICK:DOWN"),
        ("KEY:D", "LEFT_STICK:RIGHT"),
        ("KEY:UP", "RIGHT_STICK:UP"),
        ("KEY:LEFT", "RIGHT_STICK:LEFT"),
        ("KEY:DOWN", "RIGHT_STICK:DOWN"),
        ("KEY:RIGHT", "RIGHT_STICK:RIGHT"),
        ("KEY:1", "BUTTON:DPAD_UP"),
        ("KEY:2", "BUTTON:DPAD_RIGHT"),
        ("KEY:3", "BUTTON:DPAD_DOWN"),
        ("KEY:4", "BUTTON:DPAD_LEFT"),
        ("KEY:U", "GYRO:X_POSITIVE"),
        ("KEY:O", "GYRO:X_NEGATIVE"),
        ("KEY:K", "GYRO:Y_POSITIVE"),
        ("KEY:J", "GYRO:Z_POSITIVE"),
        ("KEY:L", "GYRO:Z_NEGATIVE"),
        ("KEY:P", "IMU:NEUTRAL"),
    ]
    assert all(binding.inverted is False for binding in profile.bindings)


def test_button_binding_can_be_inverted_and_maps_to_a_logical_button() -> None:
    binding = Binding(
        source="MOUSE:RIGHT",
        target=BindingTarget.BUTTON_ZL,
        inverted=True,
    )

    assert binding.inverted is True
    assert binding.amount == 1.0
    assert logical_button_for_target(binding.target) is LogicalButton.ZL


def test_stick_binding_rejects_inversion_and_out_of_range_amount() -> None:
    with pytest.raises(DomainValueError):
        Binding(source="KEY:W", target=BindingTarget.LEFT_STICK_UP, inverted=True)
    with pytest.raises(DomainValueError):
        Binding(source="KEY:W", target=BindingTarget.LEFT_STICK_UP, amount=1.001)


@pytest.mark.parametrize(
    "target",
    [
        BindingTarget.GYRO_X_POSITIVE,
        BindingTarget.GYRO_X_NEGATIVE,
        BindingTarget.GYRO_Y_NEGATIVE,
        BindingTarget.GYRO_Y_POSITIVE,
        BindingTarget.GYRO_Z_POSITIVE,
        BindingTarget.GYRO_Z_NEGATIVE,
        BindingTarget.IMU_NEUTRAL,
    ],
)
def test_diagnostic_binding_requires_fixed_amount_without_inversion(
    target: BindingTarget,
) -> None:
    assert Binding(source="KEY:O", target=target).amount == 1.0
    with pytest.raises(DomainValueError):
        Binding(source="KEY:O", target=target, amount=0.5)
    with pytest.raises(DomainValueError):
        Binding(source="KEY:O", target=target, inverted=True)


def test_binding_accepts_normalized_modifier_source() -> None:
    binding = Binding(source="KEY:CTRL+F", target=BindingTarget.BUTTON_A)

    assert binding.source == "KEY:CTRL+F"


@pytest.mark.parametrize(
    "source",
    ["KEY", "KEY:f"],
)
def test_binding_rejects_non_canonical_source(source: str) -> None:
    with pytest.raises(DomainValueError):
        Binding(source=source, target=BindingTarget.BUTTON_A)
