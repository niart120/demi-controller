"""Mouse yaw/pitch model producing physical-unit domain motion values."""

from math import cos, isfinite, pi, radians, sin

from demi.domain.controller import AccelG, GyroRate
from demi.domain.errors import DomainValueError
from demi.domain.settings import MouseSettings

BASE_YAW_RADIANS_PER_INPUT_UNIT = pi / 6000.0
BASE_PITCH_RADIANS_PER_INPUT_UNIT = pi / 6000.0


def _require_finite(value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise DomainValueError


class YawPitchModel:
    """Convert relative mouse movement into yaw/pitch IMU domain values."""

    def __init__(self, settings: MouseSettings) -> None:
        """Initialize the model at horizontal pose using mouse settings."""
        self._settings = settings
        self._pitch_limit_radians = radians(settings.pitch_limit_degrees)
        self._pitch_radians = 0.0

    @property
    def pitch_radians(self) -> float:
        """Return the current virtual pitch in radians."""
        return self._pitch_radians

    def reset(self) -> None:
        """Return the virtual pose to horizontal pitch zero."""
        self._pitch_radians = 0.0

    def update(self, *, dx: float, dy: float, dt_seconds: float) -> tuple[GyroRate, AccelG]:
        """Convert one accumulated mouse delta and elapsed interval.

        Args:
            dx: Horizontal relative mouse movement for this evaluation.
            dy: Vertical relative mouse movement for this evaluation.
            dt_seconds: Monotonic elapsed time since the previous evaluation.

        Returns:
            Gyro rate and pose-consistent static acceleration in domain units.

        Raises:
            DomainValueError: A movement or elapsed time value is non-finite.
        """
        _require_finite(dx)
        _require_finite(dy)
        _require_finite(dt_seconds)
        if dt_seconds <= 0.0 or not self._settings.gyro_enabled:
            return self._zero_gyro(), self._acceleration()

        yaw_delta = -dx * BASE_YAW_RADIANS_PER_INPUT_UNIT * self._settings.horizontal_sensitivity
        pitch_direction = -1.0 if self._settings.invert_y else 1.0
        requested_pitch_delta = (
            dy
            * BASE_PITCH_RADIANS_PER_INPUT_UNIT
            * self._settings.vertical_sensitivity
            * pitch_direction
        )
        previous_pitch = self._pitch_radians
        next_pitch = max(
            -self._pitch_limit_radians,
            min(self._pitch_limit_radians, previous_pitch + requested_pitch_delta),
        )
        pitch_delta = next_pitch - previous_pitch
        middle_pitch = (previous_pitch + next_pitch) * 0.5
        self._pitch_radians = next_pitch

        gyro = GyroRate(
            x_radians_per_second=-sin(middle_pitch) * yaw_delta / dt_seconds,
            y_radians_per_second=pitch_delta / dt_seconds,
            z_radians_per_second=cos(middle_pitch) * yaw_delta / dt_seconds,
        )
        return gyro, self._acceleration()

    def _zero_gyro(self) -> GyroRate:
        return GyroRate(0.0, 0.0, 0.0)

    def _acceleration(self) -> AccelG:
        return AccelG(
            x_g=-sin(self._pitch_radians),
            y_g=0.0,
            z_g=cos(self._pitch_radians),
        )
