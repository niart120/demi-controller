"""Convert resampled relative mouse motion into a rotation intent."""

from math import isfinite, pi

from demi.domain.errors import DomainValueError
from demi.domain.settings import MouseSettings

from .rotation_intent import RotationIntent

BASE_YAW_RADIANS_PER_INPUT_UNIT = pi / 6000.0
BASE_PITCH_RADIANS_PER_INPUT_UNIT = pi / 6000.0


def _require_finite(value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise DomainValueError


class MouseRotationMapper:
    """Map resampled mouse displacement using the active mouse settings."""

    def __init__(self, settings: MouseSettings) -> None:
        """Store the settings used for subsequent mouse evaluations."""
        self._settings = settings

    def map(self, *, dx: float, dy: float) -> RotationIntent:
        """Convert one resampled mouse displacement into angular displacement.

        Args:
            dx: Horizontal relative mouse movement for this evaluation.
            dy: Vertical relative mouse movement for this evaluation.

        Returns:
            Input-device-independent yaw and pitch displacement.

        Raises:
            DomainValueError: A movement component is non-finite.
        """
        _require_finite(dx)
        _require_finite(dy)
        if not self._settings.gyro_enabled:
            return RotationIntent(0.0, 0.0)

        yaw_direction = 1.0 if self._settings.invert_x else -1.0
        pitch_direction = -1.0 if self._settings.invert_y else 1.0
        return RotationIntent(
            yaw_delta_radians=(
                dx
                * BASE_YAW_RADIANS_PER_INPUT_UNIT
                * self._settings.horizontal_sensitivity
                * yaw_direction
            ),
            pitch_delta_radians=(
                dy
                * BASE_PITCH_RADIANS_PER_INPUT_UNIT
                * self._settings.vertical_sensitivity
                * pitch_direction
            ),
        )
