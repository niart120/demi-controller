from math import cos, radians, sin

import pytest

from demi.domain.controller import AccelG, GyroRate
from demi.domain.mapping import default_profile
from demi.domain.physical_input import PhysicalInputState
from demi.domain.settings import MouseSettings
from demi.input.mapper import synthesize_diagnostic_rotation_intent
from demi.input.mouse_rotation_mapper import (
    BASE_PITCH_RADIANS_PER_INPUT_UNIT,
    BASE_YAW_RADIANS_PER_INPUT_UNIT,
    MouseRotationMapper,
)
from demi.input.rotation_intent import RotationIntent
from demi.input.rotation_pose_model import RotationPoseModel


def test_mouse_rotation_intent_produces_pose_consistent_gyro_and_acceleration() -> None:
    settings = MouseSettings(
        horizontal_sensitivity=1.5,
        vertical_sensitivity=0.75,
    )
    mapper = MouseRotationMapper(settings)
    model = RotationPoseModel(radians(settings.pitch_limit_degrees))

    intent = mapper.map(dx=48.0, dy=24.0)
    gyro, accel = model.update(intent=intent, dt_seconds=0.008)

    yaw_delta = -48.0 * BASE_YAW_RADIANS_PER_INPUT_UNIT * 1.5
    pitch_delta = 24.0 * BASE_PITCH_RADIANS_PER_INPUT_UNIT * 0.75
    assert intent == RotationIntent(
        yaw_delta_radians=yaw_delta,
        pitch_delta_radians=pitch_delta,
    )
    assert gyro.x_radians_per_second == pytest.approx(-sin(pitch_delta * 0.5) * yaw_delta / 0.008)
    assert gyro.y_radians_per_second == pytest.approx(pitch_delta / 0.008)
    assert gyro.z_radians_per_second == pytest.approx(cos(pitch_delta * 0.5) * yaw_delta / 0.008)
    assert accel.x_g == pytest.approx(-sin(pitch_delta))
    assert accel.y_g == 0.0
    assert accel.z_g == pytest.approx(cos(pitch_delta))


def test_keyboard_pitch_intent_is_independent_of_interval_partitioning() -> None:
    profile = default_profile()
    state = PhysicalInputState()
    state.press_key("K")
    whole_interval_model = RotationPoseModel(radians(75.0))
    partitioned_model = RotationPoseModel(radians(75.0))

    whole_intent = synthesize_diagnostic_rotation_intent(
        profile,
        state,
        dt_seconds=0.2,
    )
    _, whole_accel = whole_interval_model.update(
        intent=whole_intent,
        dt_seconds=0.2,
    )
    for _ in range(2):
        partitioned_intent = synthesize_diagnostic_rotation_intent(
            profile,
            state,
            dt_seconds=0.1,
        )
        _, partitioned_accel = partitioned_model.update(
            intent=partitioned_intent,
            dt_seconds=0.1,
        )

    assert whole_intent == RotationIntent(
        yaw_delta_radians=0.0,
        pitch_delta_radians=0.2,
    )
    assert partitioned_intent == RotationIntent(
        yaw_delta_radians=0.0,
        pitch_delta_radians=0.1,
    )
    assert partitioned_model.pitch_radians == pytest.approx(whole_interval_model.pitch_radians)
    assert partitioned_accel.x_g == pytest.approx(whole_accel.x_g)
    assert partitioned_accel.z_g == pytest.approx(whole_accel.z_g)


def test_mouse_and_keyboard_rotation_intents_combine_before_pose_update() -> None:
    profile = default_profile()
    state = PhysicalInputState()
    state.press_key("J")
    state.press_key("K")
    mouse_intent = MouseRotationMapper(MouseSettings()).map(dx=10.0, dy=5.0)
    keyboard_intent = synthesize_diagnostic_rotation_intent(
        profile,
        state,
        dt_seconds=0.008,
    )

    mouse_then_keyboard = mouse_intent + keyboard_intent
    keyboard_then_mouse = keyboard_intent + mouse_intent
    first_model = RotationPoseModel(radians(75.0))
    second_model = RotationPoseModel(radians(75.0))
    first_imu = first_model.update(intent=mouse_then_keyboard, dt_seconds=0.008)
    second_imu = second_model.update(intent=keyboard_then_mouse, dt_seconds=0.008)

    assert mouse_then_keyboard == keyboard_then_mouse
    assert mouse_then_keyboard.yaw_delta_radians == pytest.approx(
        mouse_intent.yaw_delta_radians + keyboard_intent.yaw_delta_radians
    )
    assert mouse_then_keyboard.pitch_delta_radians == pytest.approx(
        mouse_intent.pitch_delta_radians + keyboard_intent.pitch_delta_radians
    )
    assert first_imu == second_imu


def test_pitch_limit_stops_effective_gyro_and_allows_immediate_return() -> None:
    pitch_limit = radians(10.0)
    model = RotationPoseModel(pitch_limit)

    reaching_gyro, reaching_accel = model.update(
        intent=RotationIntent(0.0, pitch_limit * 2.0),
        dt_seconds=0.1,
    )
    outward_gyro, outward_accel = model.update(
        intent=RotationIntent(0.1, pitch_limit),
        dt_seconds=0.1,
    )
    inward_gyro, inward_accel = model.update(
        intent=RotationIntent(0.0, -pitch_limit * 0.5),
        dt_seconds=0.1,
    )

    assert reaching_gyro.y_radians_per_second == pytest.approx(pitch_limit / 0.1)
    assert reaching_accel.x_g == pytest.approx(-sin(pitch_limit))
    assert outward_gyro.y_radians_per_second == 0.0
    assert outward_gyro.x_radians_per_second == pytest.approx(-sin(pitch_limit))
    assert outward_gyro.z_radians_per_second == pytest.approx(cos(pitch_limit))
    assert outward_accel == reaching_accel
    assert inward_gyro.y_radians_per_second == pytest.approx(-pitch_limit * 0.5 / 0.1)
    assert inward_accel.x_g == pytest.approx(-sin(pitch_limit * 0.5))
    assert model.pitch_radians == pytest.approx(pitch_limit * 0.5)


def test_mouse_and_keyboard_yaw_share_the_same_pitched_axis_projection() -> None:
    dt_seconds = 0.01
    yaw_delta = dt_seconds
    mouse_dx = -yaw_delta / BASE_YAW_RADIANS_PER_INPUT_UNIT
    mouse_intent = MouseRotationMapper(MouseSettings()).map(dx=mouse_dx, dy=0.0)
    state = PhysicalInputState()
    state.press_key("J")
    keyboard_intent = synthesize_diagnostic_rotation_intent(
        default_profile(),
        state,
        dt_seconds=dt_seconds,
    )
    mouse_model = RotationPoseModel(radians(75.0))
    keyboard_model = RotationPoseModel(radians(75.0))
    pitch_intent = RotationIntent(0.0, radians(30.0))
    mouse_model.update(intent=pitch_intent, dt_seconds=0.1)
    keyboard_model.update(intent=pitch_intent, dt_seconds=0.1)

    mouse_gyro, mouse_accel = mouse_model.update(
        intent=mouse_intent,
        dt_seconds=dt_seconds,
    )
    keyboard_gyro, keyboard_accel = keyboard_model.update(
        intent=keyboard_intent,
        dt_seconds=dt_seconds,
    )

    assert mouse_intent.yaw_delta_radians == pytest.approx(yaw_delta)
    assert keyboard_intent.yaw_delta_radians == pytest.approx(yaw_delta)
    assert mouse_gyro.x_radians_per_second == pytest.approx(keyboard_gyro.x_radians_per_second)
    assert mouse_gyro.z_radians_per_second == pytest.approx(keyboard_gyro.z_radians_per_second)
    assert mouse_gyro.y_radians_per_second == 0.0
    assert keyboard_gyro.y_radians_per_second == 0.0
    assert mouse_accel == keyboard_accel


def test_non_positive_time_preserves_pose_and_reset_returns_horizontal() -> None:
    model = RotationPoseModel(radians(75.0))
    _, tilted_accel = model.update(
        intent=RotationIntent(0.0, 0.25),
        dt_seconds=0.25,
    )
    still_gyro, still_accel = model.update(
        intent=RotationIntent(0.0, 0.0),
        dt_seconds=0.1,
    )

    assert still_gyro == GyroRate(0.0, 0.0, 0.0)
    assert still_accel == tilted_accel

    for dt_seconds in (0.0, -0.1):
        gyro, accel = model.update(
            intent=RotationIntent(1.0, 1.0),
            dt_seconds=dt_seconds,
        )
        assert gyro == GyroRate(0.0, 0.0, 0.0)
        assert accel == tilted_accel
        assert model.pitch_radians == pytest.approx(0.25)

    model.reset()

    assert model.pitch_radians == 0.0
    _, horizontal_accel = model.update(
        intent=RotationIntent(0.0, 0.0),
        dt_seconds=0.0,
    )
    assert horizontal_accel == AccelG(0.0, 0.0, 1.0)
