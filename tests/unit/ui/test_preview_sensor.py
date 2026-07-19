import pytest

from demi.domain.controller import GyroRate
from demi.ui.preview_sensor import GYRO_DISPLAY_LIMIT, gyro_display


@pytest.mark.parametrize("axis", ["x", "y", "z"])
def test_gyro_axes_encode_sign_as_opposite_rotation_directions(axis: str) -> None:
    positive = gyro_display(_gyro(axis, 1.0))
    negative = gyro_display(_gyro(axis, -1.0))

    assert getattr(positive, axis).direction == 1
    assert getattr(negative, axis).direction == -1
    assert getattr(positive, axis).magnitude == getattr(negative, axis).magnitude


def test_gyro_display_magnitude_is_monotonic_and_clamped() -> None:
    small = gyro_display(GyroRate(0.25, 0.0, 0.0)).x.magnitude
    medium = gyro_display(GyroRate(1.0, 0.0, 0.0)).x.magnitude
    large = gyro_display(GyroRate(GYRO_DISPLAY_LIMIT * 2.0, 0.0, 0.0)).x.magnitude

    assert 0.0 < small < medium < large
    assert large == 1.0


def _gyro(axis: str, value: float) -> GyroRate:
    values = {"x": 0.0, "y": 0.0, "z": 0.0}
    values[axis] = value
    return GyroRate(values["x"], values["y"], values["z"])
