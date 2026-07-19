"""Controller state values independent from external controller libraries."""

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from .errors import DomainValueError


class LogicalButton(StrEnum):
    """Logical Pro Controller buttons exposed by the domain."""

    A = "A"
    B = "B"
    X = "X"
    Y = "Y"
    L = "L"
    R = "R"
    ZL = "ZL"
    ZR = "ZR"
    PLUS = "PLUS"
    MINUS = "MINUS"
    HOME = "HOME"
    CAPTURE = "CAPTURE"
    LEFT_STICK = "LEFT_STICK"
    RIGHT_STICK = "RIGHT_STICK"
    DPAD_UP = "DPAD_UP"
    DPAD_DOWN = "DPAD_DOWN"
    DPAD_LEFT = "DPAD_LEFT"
    DPAD_RIGHT = "DPAD_RIGHT"


def _require_finite(value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise DomainValueError


def _require_counter(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DomainValueError


@dataclass(frozen=True, slots=True)
class StickVector:
    """Normalized two-dimensional stick position in the `-1..1` range.

    Raises:
        DomainValueError: A coordinate is non-finite or outside the normalized
            range.
    """

    x: float
    y: float

    def __post_init__(self) -> None:
        """Validate normalized stick coordinates."""
        _require_finite(self.x)
        _require_finite(self.y)
        if not -1.0 <= self.x <= 1.0 or not -1.0 <= self.y <= 1.0:
            raise DomainValueError


@dataclass(frozen=True, slots=True)
class GyroRate:
    """Angular velocity expressed in radians per second.

    Raises:
        DomainValueError: A component is not finite.
    """

    x_radians_per_second: float
    y_radians_per_second: float
    z_radians_per_second: float

    def __post_init__(self) -> None:
        """Validate angular velocity components."""
        _require_finite(self.x_radians_per_second)
        _require_finite(self.y_radians_per_second)
        _require_finite(self.z_radians_per_second)


@dataclass(frozen=True, slots=True)
class AccelG:
    """Acceleration-sensor specific force expressed in G units.

    Raises:
        DomainValueError: A component is not finite.
    """

    x_g: float
    y_g: float
    z_g: float

    def __post_init__(self) -> None:
        """Validate acceleration components."""
        _require_finite(self.x_g)
        _require_finite(self.y_g)
        _require_finite(self.z_g)


@dataclass(frozen=True, slots=True)
class ControllerFrame:
    """Complete immutable controller state for one input evaluation.

    Raises:
        DomainValueError: Metadata or nested values violate the frame
            invariant.
    """

    sequence: int
    capture_epoch: int
    monotonic_ns: int
    buttons: frozenset[LogicalButton]
    left_stick: StickVector
    right_stick: StickVector
    gyro_rate: GyroRate
    accel_g: AccelG
    capture_active: bool
    sample_duration_ns: int = 0
    pointer_capture_active: bool = False

    def __post_init__(self) -> None:
        """Validate frame metadata and nested domain values."""
        _require_counter(self.sequence)
        _require_counter(self.capture_epoch)
        _require_counter(self.monotonic_ns)
        _require_counter(self.sample_duration_ns)
        if not isinstance(self.buttons, frozenset) or not all(
            isinstance(button, LogicalButton) for button in self.buttons
        ):
            raise DomainValueError
        if not isinstance(self.left_stick, StickVector) or not isinstance(
            self.right_stick, StickVector
        ):
            raise DomainValueError
        if not isinstance(self.gyro_rate, GyroRate):
            raise DomainValueError
        if not isinstance(self.accel_g, AccelG):
            raise DomainValueError
        if not isinstance(self.capture_active, bool):
            raise DomainValueError
        if not isinstance(self.pointer_capture_active, bool):
            raise DomainValueError
