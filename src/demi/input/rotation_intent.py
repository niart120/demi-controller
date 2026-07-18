"""Input-device-independent angular displacement for one evaluation."""

from dataclasses import dataclass
from math import isfinite

from demi.domain.errors import DomainValueError


def _require_finite(value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise DomainValueError


@dataclass(frozen=True, slots=True)
class RotationIntent:
    """Requested yaw and pitch displacement expressed in radians."""

    yaw_delta_radians: float
    pitch_delta_radians: float

    def __post_init__(self) -> None:
        """Validate both angular displacement components."""
        _require_finite(self.yaw_delta_radians)
        _require_finite(self.pitch_delta_radians)

    def __add__(self, other: "RotationIntent") -> "RotationIntent":
        """Add another same-period rotation intent axis by axis."""
        return RotationIntent(
            yaw_delta_radians=self.yaw_delta_radians + other.yaw_delta_radians,
            pitch_delta_radians=self.pitch_delta_radians + other.pitch_delta_radians,
        )
