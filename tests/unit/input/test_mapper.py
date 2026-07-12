from typing import Literal, cast

import pytest

from demi.domain.controller import LogicalButton, StickVector
from demi.domain.errors import DomainValueError
from demi.domain.mapping import Binding, BindingTarget, InputProfile, default_profile
from demi.domain.physical_input import PhysicalInputState
from demi.input.mapper import aggregate_buttons, synthesize_stick


def test_default_button_sources_are_aggregated_and_release_is_independent() -> None:
    profile = default_profile()
    state = PhysicalInputState()

    state.press_key("F")
    assert aggregate_buttons(profile, state, capture_active=True) == frozenset({LogicalButton.A})

    state.press_key("V")
    state.press_key("SPACE")
    state.release_key("V")
    assert aggregate_buttons(profile, state, capture_active=True) == frozenset(
        {LogicalButton.A, LogicalButton.B}
    )


def test_inverted_binding_uses_xor_for_any_button_target() -> None:
    profile = InputProfile(
        id="custom",
        name="Custom",
        builtin=False,
        bindings=(Binding(source="MOUSE:RIGHT", target=BindingTarget.BUTTON_HOME, inverted=True),),
    )
    state = PhysicalInputState()

    assert aggregate_buttons(profile, state, capture_active=True) == frozenset({LogicalButton.HOME})
    state.press_mouse_button("RIGHT")
    assert aggregate_buttons(profile, state, capture_active=True) == frozenset()


def test_capture_outside_always_returns_a_neutral_button_set() -> None:
    state = PhysicalInputState()
    state.press_key("F")
    state.press_mouse_button("RIGHT")

    assert aggregate_buttons(default_profile(), state, capture_active=False) == frozenset()


def test_stick_directions_cancel_and_combine_into_axes() -> None:
    state = PhysicalInputState()
    state.press_key("W")
    state.press_key("D")

    assert synthesize_stick(default_profile(), state, "left", circular_limit=False) == StickVector(
        x=1.0,
        y=1.0,
    )

    state.press_key("S")
    assert synthesize_stick(default_profile(), state, "left", circular_limit=False) == StickVector(
        x=1.0,
        y=0.0,
    )


def test_stick_amount_and_circular_limit_are_applied() -> None:
    profile = InputProfile(
        id="custom",
        name="Custom",
        builtin=False,
        bindings=(
            Binding(source="KEY:W", target=BindingTarget.LEFT_STICK_UP, amount=1.0),
            Binding(source="KEY:D", target=BindingTarget.LEFT_STICK_RIGHT, amount=1.0),
        ),
    )
    state = PhysicalInputState()
    state.press_key("W")
    state.press_key("D")

    assert synthesize_stick(profile, state, "left", circular_limit=False) == StickVector(
        x=1.0,
        y=1.0,
    )
    vector = synthesize_stick(profile, state, "left", circular_limit=True)
    assert vector.x == pytest.approx(2**-0.5)
    assert vector.y == pytest.approx(2**-0.5)


def test_unknown_stick_selector_is_rejected() -> None:
    selector = cast('Literal["left", "right"]', "middle")
    with pytest.raises(DomainValueError):
        synthesize_stick(default_profile(), PhysicalInputState(), selector, circular_limit=False)


def test_stick_capture_outside_is_neutral() -> None:
    state = PhysicalInputState()
    state.press_key("W")

    assert synthesize_stick(
        default_profile(), state, "left", circular_limit=False, capture_active=False
    ) == StickVector(x=0.0, y=0.0)
