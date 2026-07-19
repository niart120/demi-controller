"""Display-only normalization for signed controller sensors."""

from dataclasses import dataclass

from demi.domain.controller import AccelG, GyroRate

GYRO_DISPLAY_LIMIT = 4.0
ACCEL_DISPLAY_LIMIT = 2.0


@dataclass(frozen=True, slots=True)
class SignedAxisDisplay:
    """Signed direction and normalized magnitude for one sensor axis."""

    value: float
    direction: int
    magnitude: float


@dataclass(frozen=True, slots=True)
class SensorDisplay:
    """Display values for signed X, Y, and Z sensor axes."""

    x: SignedAxisDisplay
    y: SignedAxisDisplay
    z: SignedAxisDisplay


def gyro_display(rate: GyroRate) -> SensorDisplay:
    """Normalize angular velocity without integrating an absolute pose."""
    return SensorDisplay(
        x=_signed_axis(rate.x_radians_per_second, GYRO_DISPLAY_LIMIT),
        y=_signed_axis(rate.y_radians_per_second, GYRO_DISPLAY_LIMIT),
        z=_signed_axis(rate.z_radians_per_second, GYRO_DISPLAY_LIMIT),
    )


def accel_display(acceleration: AccelG) -> SensorDisplay:
    """Normalize signed acceleration as bounded axis-vector components."""
    return SensorDisplay(
        x=_signed_axis(acceleration.x_g, ACCEL_DISPLAY_LIMIT),
        y=_signed_axis(acceleration.y_g, ACCEL_DISPLAY_LIMIT),
        z=_signed_axis(acceleration.z_g, ACCEL_DISPLAY_LIMIT),
    )


def _signed_axis(value: float, limit: float) -> SignedAxisDisplay:
    direction = 1 if value > 0.0 else -1 if value < 0.0 else 0
    return SignedAxisDisplay(
        value=value,
        direction=direction,
        magnitude=min(abs(value) / limit, 1.0),
    )
