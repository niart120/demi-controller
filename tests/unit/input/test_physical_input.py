from collections.abc import Callable

import pytest

from demi.domain.errors import DomainValueError
from demi.domain.physical_input import KeySource, MouseButtonSource, PhysicalInputState


def test_sources_are_normalized_to_canonical_names() -> None:
    assert KeySource("f").canonical == "KEY:F"
    assert KeySource("space", frozenset({"ctrl"})).canonical == "KEY:CTRL+SPACE"
    assert MouseButtonSource("left").canonical == "MOUSE:LEFT"
    assert MouseButtonSource("button_4").canonical == "MOUSE:BUTTON_4"


@pytest.mark.parametrize(
    "factory",
    [
        lambda: KeySource(""),
        lambda: KeySource("F!"),
        lambda: MouseButtonSource("unknown"),
        lambda: MouseButtonSource("../escape"),
    ],
)
def test_sources_reject_non_canonical_names(factory: Callable[[], object]) -> None:
    with pytest.raises(DomainValueError):
        factory()


def test_physical_input_state_handles_duplicate_press_and_missing_release() -> None:
    state = PhysicalInputState()

    state.press_key("f")
    state.press_key("F")
    state.press_mouse_button("left")
    state.release_key("F")
    state.release_key("unused")
    state.release_mouse_button("right")

    assert state.held_keys == set()
    assert state.held_mouse_buttons == {MouseButtonSource("LEFT")}
    assert state.revision == 3


def test_clear_removes_all_held_sources() -> None:
    state = PhysicalInputState()
    state.press_key("F")
    state.press_mouse_button("LEFT")

    state.clear()

    assert state.held_keys == set()
    assert state.held_mouse_buttons == set()
