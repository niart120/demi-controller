from demi.domain.controller import LogicalButton
from demi.domain.mapping import Binding, BindingTarget, InputProfile, default_profile
from demi.domain.physical_input import PhysicalInputState
from demi.input.mapper import aggregate_buttons


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
