import pytest

from demi.domain.controller import StickVector
from demi.domain.errors import DomainValueError
from demi.domain.gamepad import GamepadButton, GamepadState


def test_gamepad_state_has_explicit_connected_neutral_value() -> None:
    assert GamepadState.neutral() == GamepadState(
        connected=False,
        buttons=frozenset(),
        left_stick=StickVector(0.0, 0.0),
        right_stick=StickVector(0.0, 0.0),
        left_trigger=0.0,
        right_trigger=0.0,
    )


def test_gamepad_state_rejects_out_of_range_triggers() -> None:
    with pytest.raises(DomainValueError):
        GamepadState(
            connected=True,
            buttons=frozenset({GamepadButton.SOUTH}),
            left_stick=StickVector(0.0, 0.0),
            right_stick=StickVector(0.0, 0.0),
            left_trigger=1.1,
            right_trigger=0.0,
        )
