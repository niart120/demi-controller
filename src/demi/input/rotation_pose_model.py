"""Unified yaw/pitch pose model for input-device-independent rotation."""

from math import cos, isfinite, sin

from demi.domain.controller import AccelG, GyroRate
from demi.domain.errors import DomainValueError

from .rotation_intent import RotationIntent


def _require_finite(value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise DomainValueError


class RotationPoseModel:
    """Apply angular displacement to a pitch-limited virtual pose."""

    def __init__(self, pitch_limit_radians: float) -> None:
        """Initialize a horizontal pose with one symmetric pitch limit."""
        _require_finite(pitch_limit_radians)
        if pitch_limit_radians <= 0.0:
            raise DomainValueError
        self._pitch_limit_radians = pitch_limit_radians
        self._pitch_radians = 0.0

    @property
    def pitch_radians(self) -> float:
        """Return the current virtual pitch in radians."""
        return self._pitch_radians

    def reset(self) -> None:
        """Return the virtual pose to horizontal pitch zero."""
        self._pitch_radians = 0.0

    def update(
        self,
        *,
        intent: RotationIntent,
        dt_seconds: float,
    ) -> tuple[GyroRate, AccelG]:
        """Apply one rotation intent and derive pose-consistent IMU values.

        Args:
            intent: Requested yaw and pitch displacement for this evaluation.
            dt_seconds: Monotonic elapsed time since the previous evaluation.

        Returns:
            Effective gyro rate and static acceleration in domain units.

        Raises:
            DomainValueError: The elapsed time is non-finite.
        """
        _require_finite(dt_seconds)
        if dt_seconds <= 0.0:
            return self._zero_gyro(), self._acceleration()

        previous_pitch = self._pitch_radians
        next_pitch = max(
            -self._pitch_limit_radians,
            min(
                self._pitch_limit_radians,
                previous_pitch + intent.pitch_delta_radians,
            ),
        )
        applied_pitch_delta = next_pitch - previous_pitch
        middle_pitch = (previous_pitch + next_pitch) * 0.5
        self._pitch_radians = next_pitch

        return (
            GyroRate(
                x_radians_per_second=(-sin(middle_pitch) * intent.yaw_delta_radians / dt_seconds),
                y_radians_per_second=applied_pitch_delta / dt_seconds,
                z_radians_per_second=(cos(middle_pitch) * intent.yaw_delta_radians / dt_seconds),
            ),
            self._acceleration(),
        )

    @staticmethod
    def _zero_gyro() -> GyroRate:
        return GyroRate(0.0, 0.0, 0.0)

    def _acceleration(self) -> AccelG:
        return AccelG(
            x_g=-sin(self._pitch_radians),
            y_g=0.0,
            z_g=cos(self._pitch_radians),
        )
