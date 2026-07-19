import pytest

from demi.domain.controller import AccelG, GyroRate
from demi.ui.preview_sensor import (
    ACCEL_DISPLAY_LIMIT,
    GYRO_DISPLAY_LIMIT,
    accel_display,
    gyro_display,
)


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


@pytest.mark.parametrize("axis", ["x", "y", "z"])
def test_accel_axes_encode_vector_direction_and_length(axis: str) -> None:
    positive = accel_display(_accel(axis, 0.5))
    negative = accel_display(_accel(axis, -0.5))

    assert getattr(positive, axis).direction == 1
    assert getattr(negative, axis).direction == -1
    assert getattr(positive, axis).magnitude == pytest.approx(0.5 / ACCEL_DISPLAY_LIMIT)


def test_accel_display_clamps_values_beyond_its_visual_bound() -> None:
    display = accel_display(AccelG(10.0, -10.0, 0.0))

    assert display.x.magnitude == 1.0
    assert display.y.magnitude == 1.0
    assert display.z.magnitude == 0.0


def _gyro(axis: str, value: float) -> GyroRate:
    values = {"x": 0.0, "y": 0.0, "z": 0.0}
    values[axis] = value
    return GyroRate(values["x"], values["y"], values["z"])


def _accel(axis: str, value: float) -> AccelG:
    values = {"x": 0.0, "y": 0.0, "z": 0.0}
    values[axis] = value
    return AccelG(values["x"], values["y"], values["z"])
