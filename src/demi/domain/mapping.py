"""Input binding values and built-in profiles."""

import re
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from .controller import LogicalButton
from .errors import DomainValueError


class BindingTarget(StrEnum):
    """Canonical configuration targets for controller and diagnostic inputs."""

    BUTTON_A = "BUTTON:A"
    BUTTON_B = "BUTTON:B"
    BUTTON_X = "BUTTON:X"
    BUTTON_Y = "BUTTON:Y"
    BUTTON_L = "BUTTON:L"
    BUTTON_R = "BUTTON:R"
    BUTTON_ZL = "BUTTON:ZL"
    BUTTON_ZR = "BUTTON:ZR"
    BUTTON_PLUS = "BUTTON:PLUS"
    BUTTON_MINUS = "BUTTON:MINUS"
    BUTTON_HOME = "BUTTON:HOME"
    BUTTON_CAPTURE = "BUTTON:CAPTURE"
    BUTTON_LEFT_STICK = "BUTTON:LEFT_STICK"
    BUTTON_RIGHT_STICK = "BUTTON:RIGHT_STICK"
    BUTTON_DPAD_UP = "BUTTON:DPAD_UP"
    BUTTON_DPAD_DOWN = "BUTTON:DPAD_DOWN"
    BUTTON_DPAD_LEFT = "BUTTON:DPAD_LEFT"
    BUTTON_DPAD_RIGHT = "BUTTON:DPAD_RIGHT"
    LEFT_STICK_UP = "LEFT_STICK:UP"
    LEFT_STICK_DOWN = "LEFT_STICK:DOWN"
    LEFT_STICK_LEFT = "LEFT_STICK:LEFT"
    LEFT_STICK_RIGHT = "LEFT_STICK:RIGHT"
    RIGHT_STICK_UP = "RIGHT_STICK:UP"
    RIGHT_STICK_DOWN = "RIGHT_STICK:DOWN"
    RIGHT_STICK_LEFT = "RIGHT_STICK:LEFT"
    RIGHT_STICK_RIGHT = "RIGHT_STICK:RIGHT"
    GYRO_Y_NEGATIVE = "GYRO:Y_NEGATIVE"
    GYRO_Y_POSITIVE = "GYRO:Y_POSITIVE"
    GYRO_Z_POSITIVE = "GYRO:Z_POSITIVE"
    GYRO_Z_NEGATIVE = "GYRO:Z_NEGATIVE"
    ACCEL_ZERO = "ACCEL:ZERO"


_SOURCE_PATTERN = re.compile(r"(?:KEY:[A-Z0-9_]+(?:\+[A-Z0-9_]+)*|MOUSE:[A-Z0-9_]+)")
_PROFILE_ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}")
_BUTTON_TARGETS: dict[BindingTarget, LogicalButton] = {
    BindingTarget.BUTTON_A: LogicalButton.A,
    BindingTarget.BUTTON_B: LogicalButton.B,
    BindingTarget.BUTTON_X: LogicalButton.X,
    BindingTarget.BUTTON_Y: LogicalButton.Y,
    BindingTarget.BUTTON_L: LogicalButton.L,
    BindingTarget.BUTTON_R: LogicalButton.R,
    BindingTarget.BUTTON_ZL: LogicalButton.ZL,
    BindingTarget.BUTTON_ZR: LogicalButton.ZR,
    BindingTarget.BUTTON_PLUS: LogicalButton.PLUS,
    BindingTarget.BUTTON_MINUS: LogicalButton.MINUS,
    BindingTarget.BUTTON_HOME: LogicalButton.HOME,
    BindingTarget.BUTTON_CAPTURE: LogicalButton.CAPTURE,
    BindingTarget.BUTTON_LEFT_STICK: LogicalButton.LEFT_STICK,
    BindingTarget.BUTTON_RIGHT_STICK: LogicalButton.RIGHT_STICK,
    BindingTarget.BUTTON_DPAD_UP: LogicalButton.DPAD_UP,
    BindingTarget.BUTTON_DPAD_DOWN: LogicalButton.DPAD_DOWN,
    BindingTarget.BUTTON_DPAD_LEFT: LogicalButton.DPAD_LEFT,
    BindingTarget.BUTTON_DPAD_RIGHT: LogicalButton.DPAD_RIGHT,
}
_DIAGNOSTIC_TARGETS = frozenset(
    {
        BindingTarget.GYRO_Y_NEGATIVE,
        BindingTarget.GYRO_Y_POSITIVE,
        BindingTarget.GYRO_Z_POSITIVE,
        BindingTarget.GYRO_Z_NEGATIVE,
        BindingTarget.ACCEL_ZERO,
    }
)


def logical_button_for_target(target: BindingTarget) -> LogicalButton:
    """Return the logical button represented by a button target."""
    try:
        return _BUTTON_TARGETS[target]
    except KeyError:
        raise DomainValueError from None


def is_button_target(target: BindingTarget) -> bool:
    """Return whether a binding target represents a logical button."""
    return target in _BUTTON_TARGETS


def is_diagnostic_target(target: BindingTarget) -> bool:
    """Return whether a binding target controls a fixed IMU diagnostic."""
    return target in _DIAGNOSTIC_TARGETS


@dataclass(frozen=True, slots=True)
class Binding:
    """A normalized physical input binding.

    Raises:
        DomainValueError: The source, target, amount, or inversion combination
            is not supported by the configuration schema.
    """

    source: str
    target: BindingTarget
    amount: float = 1.0
    inverted: bool = False

    def __post_init__(self) -> None:
        """Validate and normalize the binding fields."""
        if not isinstance(self.source, str) or _SOURCE_PATTERN.fullmatch(self.source) is None:
            raise DomainValueError
        if not isinstance(self.target, BindingTarget):
            raise DomainValueError from None
        if isinstance(self.amount, bool) or not isinstance(self.amount, (int, float)):
            raise DomainValueError
        if not isfinite(self.amount):
            raise DomainValueError
        if not isinstance(self.inverted, bool):
            raise DomainValueError
        amount = float(self.amount)
        if (is_button_target(self.target) or is_diagnostic_target(self.target)) and amount != 1.0:
            raise DomainValueError
        if not is_button_target(self.target) and (self.inverted or not 0.0 <= amount <= 1.0):
            raise DomainValueError
        object.__setattr__(self, "amount", amount)


@dataclass(frozen=True, slots=True)
class InputProfile:
    """Named collection of bindings available to the application.

    Raises:
        DomainValueError: The profile identity or binding collection is
            invalid.
    """

    id: str
    name: str
    builtin: bool
    bindings: tuple[Binding, ...]

    def __post_init__(self) -> None:
        """Validate profile identity and binding values."""
        if not isinstance(self.id, str) or _PROFILE_ID_PATTERN.fullmatch(self.id) is None:
            raise DomainValueError
        if not isinstance(self.name, str) or not self.name.strip():
            raise DomainValueError
        if not isinstance(self.builtin, bool):
            raise DomainValueError
        if not isinstance(self.bindings, tuple) or not all(
            isinstance(binding, Binding) for binding in self.bindings
        ):
            raise DomainValueError


def default_profile() -> InputProfile:
    """Return the immutable built-in ``Default`` input profile.

    Returns:
        The 33-binding profile defined by the initial configuration.
    """
    return InputProfile(
        id="default",
        name="Default",
        builtin=True,
        bindings=(
            Binding("KEY:F", BindingTarget.BUTTON_A),
            Binding("KEY:V", BindingTarget.BUTTON_B),
            Binding("KEY:SPACE", BindingTarget.BUTTON_B),
            Binding("KEY:E", BindingTarget.BUTTON_X),
            Binding("MOUSE:MIDDLE", BindingTarget.BUTTON_Y),
            Binding("KEY:R", BindingTarget.BUTTON_R),
            Binding("KEY:Q", BindingTarget.BUTTON_L),
            Binding("MOUSE:LEFT", BindingTarget.BUTTON_ZR),
            Binding("MOUSE:RIGHT", BindingTarget.BUTTON_ZL),
            Binding("KEY:TAB", BindingTarget.BUTTON_ZL),
            Binding("KEY:LEFT_SHIFT", BindingTarget.BUTTON_ZL),
            Binding("KEY:Z", BindingTarget.BUTTON_MINUS),
            Binding("KEY:X", BindingTarget.BUTTON_PLUS),
            Binding("KEY:ESCAPE", BindingTarget.BUTTON_HOME),
            Binding("KEY:T", BindingTarget.BUTTON_RIGHT_STICK),
            Binding("KEY:G", BindingTarget.BUTTON_LEFT_STICK),
            Binding("KEY:W", BindingTarget.LEFT_STICK_UP),
            Binding("KEY:A", BindingTarget.LEFT_STICK_LEFT),
            Binding("KEY:S", BindingTarget.LEFT_STICK_DOWN),
            Binding("KEY:D", BindingTarget.LEFT_STICK_RIGHT),
            Binding("KEY:UP", BindingTarget.RIGHT_STICK_UP),
            Binding("KEY:LEFT", BindingTarget.RIGHT_STICK_LEFT),
            Binding("KEY:DOWN", BindingTarget.RIGHT_STICK_DOWN),
            Binding("KEY:RIGHT", BindingTarget.RIGHT_STICK_RIGHT),
            Binding("KEY:1", BindingTarget.BUTTON_DPAD_UP),
            Binding("KEY:2", BindingTarget.BUTTON_DPAD_RIGHT),
            Binding("KEY:3", BindingTarget.BUTTON_DPAD_DOWN),
            Binding("KEY:4", BindingTarget.BUTTON_DPAD_LEFT),
            Binding("KEY:I", BindingTarget.GYRO_Y_NEGATIVE),
            Binding("KEY:K", BindingTarget.GYRO_Y_POSITIVE),
            Binding("KEY:J", BindingTarget.GYRO_Z_POSITIVE),
            Binding("KEY:L", BindingTarget.GYRO_Z_NEGATIVE),
            Binding("KEY:O", BindingTarget.ACCEL_ZERO),
        ),
    )
