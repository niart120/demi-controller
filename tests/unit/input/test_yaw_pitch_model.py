from math import cos, radians, sin

import pytest

from demi.domain.controller import AccelG, GyroRate
from demi.domain.settings import MouseSettings
from demi.input.yaw_pitch_model import (
    BASE_PITCH_RADIANS_PER_INPUT_UNIT,
    BASE_YAW_RADIANS_PER_INPUT_UNIT,
    YawPitchModel,
)


def test_zero_motion_returns_zero_gyro_and_horizontal_one_g() -> None:
    model = YawPitchModel(MouseSettings())

    gyro, accel = model.update(dx=0.0, dy=0.0, dt_seconds=0.008)

    assert gyro == GyroRate(0.0, 0.0, 0.0)
    assert accel == AccelG(0.0, 0.0, 1.0)


def test_horizontal_motion_is_negative_world_up_yaw() -> None:
    model = YawPitchModel(MouseSettings())

    gyro, accel = model.update(dx=2.0, dy=0.0, dt_seconds=0.01)

    assert gyro == GyroRate(
        x_radians_per_second=0.0,
        y_radians_per_second=0.0,
        z_radians_per_second=-2.0 * BASE_YAW_RADIANS_PER_INPUT_UNIT / 0.01,
    )
    assert accel == AccelG(0.0, 0.0, 1.0)


def test_vertical_motion_updates_pitch_and_pose_consistent_acceleration() -> None:
    model = YawPitchModel(MouseSettings())

    gyro, accel = model.update(dx=0.0, dy=4.0, dt_seconds=0.02)
    pitch = 4.0 * BASE_PITCH_RADIANS_PER_INPUT_UNIT

    assert gyro == GyroRate(0.0, pitch / 0.02, 0.0)
    assert accel.x_g == pytest.approx(-sin(pitch))
    assert accel.y_g == 0.0
    assert accel.z_g == pytest.approx(cos(pitch))
    assert model.pitch_radians == pytest.approx(pitch)


def test_additional_pitch_rate_is_independent_of_interval_partitioning() -> None:
    single_interval = YawPitchModel(MouseSettings(gyro_enabled=False))
    split_intervals = YawPitchModel(MouseSettings(gyro_enabled=False))

    _, single_accel = single_interval.update(
        dx=0.0,
        dy=0.0,
        dt_seconds=0.25,
        additional_pitch_rate_radians_per_second=-1.0,
    )
    for interval in (0.05, 0.075, 0.125):
        _, split_accel = split_intervals.update(
            dx=0.0,
            dy=0.0,
            dt_seconds=interval,
            additional_pitch_rate_radians_per_second=-1.0,
        )

    assert split_intervals.pitch_radians == pytest.approx(-0.25)
    assert split_accel.x_g == pytest.approx(single_accel.x_g)
    assert split_accel.y_g == single_accel.y_g
    assert split_accel.z_g == pytest.approx(single_accel.z_g)


def test_yaw_is_projected_using_the_middle_pitch_of_the_interval() -> None:
    model = YawPitchModel(MouseSettings())
    dt = 0.02
    dy = 4.0
    dx = 2.0
    next_pitch = dy * BASE_PITCH_RADIANS_PER_INPUT_UNIT
    middle_pitch = next_pitch * 0.5
    yaw_delta = -dx * BASE_YAW_RADIANS_PER_INPUT_UNIT

    gyro, _ = model.update(dx=dx, dy=dy, dt_seconds=dt)

    assert gyro.x_radians_per_second == pytest.approx(-sin(middle_pitch) * yaw_delta / dt)
    assert gyro.z_radians_per_second == pytest.approx(cos(middle_pitch) * yaw_delta / dt)


def test_horizontal_and_vertical_sensitivity_are_independent() -> None:
    horizontal = YawPitchModel(MouseSettings(horizontal_sensitivity=2.0))
    vertical = YawPitchModel(MouseSettings(vertical_sensitivity=2.0))

    horizontal_gyro, _ = horizontal.update(dx=1.0, dy=0.0, dt_seconds=0.01)
    vertical_gyro, _ = vertical.update(dx=0.0, dy=1.0, dt_seconds=0.01)

    assert horizontal_gyro.z_radians_per_second == pytest.approx(
        -2.0 * BASE_YAW_RADIANS_PER_INPUT_UNIT / 0.01
    )
    assert vertical_gyro.y_radians_per_second == pytest.approx(
        2.0 * BASE_PITCH_RADIANS_PER_INPUT_UNIT / 0.01
    )


def test_invert_y_reverses_pitch_direction() -> None:
    model = YawPitchModel(MouseSettings(invert_y=True))

    gyro, accel = model.update(dx=0.0, dy=1.0, dt_seconds=0.01)

    assert gyro.y_radians_per_second < 0.0
    assert accel.x_g > 0.0


def test_pitch_limit_stops_pitch_but_does_not_stop_yaw() -> None:
    model = YawPitchModel(MouseSettings(pitch_limit_degrees=1.0))

    vertical_gyro, _ = model.update(dx=0.0, dy=10000.0, dt_seconds=0.01)
    yaw_gyro, _ = model.update(dx=1.0, dy=10000.0, dt_seconds=0.01)

    assert model.pitch_radians == pytest.approx(radians(1.0))
    assert vertical_gyro.y_radians_per_second == pytest.approx(radians(1.0) / 0.01)
    assert yaw_gyro.z_radians_per_second < 0.0
    assert yaw_gyro.y_radians_per_second == pytest.approx(0.0)


def test_non_positive_dt_does_not_update_pose_and_returns_current_acceleration() -> None:
    model = YawPitchModel(MouseSettings())
    model.update(dx=0.0, dy=10.0, dt_seconds=0.01)
    previous_pitch = model.pitch_radians

    gyro, accel = model.update(dx=100.0, dy=100.0, dt_seconds=0.0)

    assert model.pitch_radians == previous_pitch
    assert gyro == GyroRate(0.0, 0.0, 0.0)
    assert accel == AccelG(-sin(previous_pitch), 0.0, cos(previous_pitch))


def test_no_motion_keeps_pose_but_returns_zero_gyro() -> None:
    model = YawPitchModel(MouseSettings())
    model.update(dx=0.0, dy=10.0, dt_seconds=0.01)
    pitch = model.pitch_radians

    gyro, accel = model.update(dx=0.0, dy=0.0, dt_seconds=0.01)

    assert gyro == GyroRate(0.0, 0.0, 0.0)
    assert accel == AccelG(-sin(pitch), 0.0, cos(pitch))


def test_reset_returns_pose_to_horizontal_neutral() -> None:
    model = YawPitchModel(MouseSettings())
    model.update(dx=0.0, dy=10.0, dt_seconds=0.01)

    model.reset()
    gyro, accel = model.update(dx=0.0, dy=0.0, dt_seconds=0.01)

    assert model.pitch_radians == 0.0
    assert gyro == GyroRate(0.0, 0.0, 0.0)
    assert accel == AccelG(0.0, 0.0, 1.0)
