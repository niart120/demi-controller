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


def test_mouse_motion_is_accumulated_and_consumed_once() -> None:
    state = PhysicalInputState()
    state.add_mouse_motion(2.0, 1.0)
    state.add_mouse_motion(3.0, -2.0)
    state.add_mouse_motion(-1.0, 4.0)

    assert state.consume_mouse_motion() == (4.0, 3.0)
    assert state.consume_mouse_motion() == (0.0, 0.0)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_mouse_motion_rejects_non_finite_values(value: float) -> None:
    with pytest.raises(DomainValueError):
        PhysicalInputState().add_mouse_motion(value, 0.0)


def test_clear_discards_pending_mouse_motion() -> None:
    state = PhysicalInputState()
    state.add_mouse_motion(4.0, -2.0)

    state.clear()

    assert state.consume_mouse_motion() == (0.0, 0.0)
