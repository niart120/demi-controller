"""Normalized gamepad values independent from SDL or a GUI framework."""

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from .controller import StickVector
from .errors import DomainValueError


class GamepadButton(StrEnum):
    """Physical positions exposed by an SDL GameController."""

    SOUTH = "south"
    EAST = "east"
    WEST = "west"
    NORTH = "north"
    DPAD_UP = "dpad_up"
    DPAD_DOWN = "dpad_down"
    DPAD_LEFT = "dpad_left"
    DPAD_RIGHT = "dpad_right"
    LEFT_SHOULDER = "left_shoulder"
    RIGHT_SHOULDER = "right_shoulder"
    LEFT_STICK = "left_stick"
    RIGHT_STICK = "right_stick"
    BACK = "back"
    START = "start"
    GUIDE = "guide"


def _require_trigger(value: float) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
        or not 0.0 <= value <= 1.0
    ):
        raise DomainValueError


@dataclass(frozen=True, slots=True)
class GamepadState:
    """One normalized gamepad snapshot.

    SDL-specific device handles, axis constants, and raw integer ranges do not
    cross this boundary. Sticks use the same positive-up coordinate system as
    :class:`~demi.domain.controller.StickVector`.
    """

    connected: bool
    buttons: frozenset[GamepadButton]
    left_stick: StickVector
    right_stick: StickVector
    left_trigger: float
    right_trigger: float

    def __post_init__(self) -> None:
        """Validate the normalized snapshot."""
        if not isinstance(self.connected, bool):
            raise DomainValueError
        if not isinstance(self.buttons, frozenset) or not all(
            isinstance(button, GamepadButton) for button in self.buttons
        ):
            raise DomainValueError
        if not isinstance(self.left_stick, StickVector) or not isinstance(
            self.right_stick, StickVector
        ):
            raise DomainValueError
        _require_trigger(self.left_trigger)
        _require_trigger(self.right_trigger)

    @classmethod
    def neutral(cls) -> "GamepadState":
        """Return the disconnected gamepad state with no active controls."""
        return cls(
            connected=False,
            buttons=frozenset(),
            left_stick=StickVector(0.0, 0.0),
            right_stick=StickVector(0.0, 0.0),
            left_trigger=0.0,
            right_trigger=0.0,
        )
