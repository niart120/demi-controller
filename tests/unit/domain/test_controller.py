from dataclasses import FrozenInstanceError
from math import inf, nan

import pytest

from demi.domain.controller import (
    AccelG,
    ControllerFrame,
    GyroRate,
    LogicalButton,
    StickVector,
)
from demi.domain.errors import DomainValueError


def test_logical_buttons_cover_the_pro_controller_controls() -> None:
    assert {button.value for button in LogicalButton} == {
        "A",
        "B",
        "X",
        "Y",
        "L",
        "R",
        "ZL",
        "ZR",
        "PLUS",
        "MINUS",
        "HOME",
        "CAPTURE",
        "LEFT_STICK",
        "RIGHT_STICK",
        "DPAD_UP",
        "DPAD_DOWN",
        "DPAD_LEFT",
        "DPAD_RIGHT",
    }


def test_controller_frame_contains_immutable_domain_values() -> None:
    stick = StickVector(x=0.25, y=-1.0)
    gyro = GyroRate(x_radians_per_second=1.0, y_radians_per_second=0.0, z_radians_per_second=-1.0)
    accel = AccelG(x_g=0.0, y_g=0.0, z_g=1.0)
    frame = ControllerFrame(
        sequence=1,
        capture_epoch=2,
        monotonic_ns=3,
        buttons=frozenset({LogicalButton.A}),
        left_stick=stick,
        right_stick=StickVector(x=0.0, y=0.0),
        gyro_rate=gyro,
        accel_g=accel,
        capture_active=True,
    )

    assert frame.left_stick == stick
    assert frame.gyro_rate == gyro
    assert frame.accel_g == accel
    with pytest.raises(FrozenInstanceError):
        frame.__setattr__("sequence", 4)


@pytest.mark.parametrize("value", [nan, inf, -inf])
def test_motion_values_reject_non_finite_numbers(value: float) -> None:
    with pytest.raises(DomainValueError):
        StickVector(x=value, y=0.0)
    with pytest.raises(DomainValueError):
        GyroRate(x_radians_per_second=value, y_radians_per_second=0.0, z_radians_per_second=0.0)
    with pytest.raises(DomainValueError):
        AccelG(x_g=value, y_g=0.0, z_g=0.0)


@pytest.mark.parametrize("value", [-1.000001, 1.000001])
def test_stick_vector_rejects_values_outside_the_normalized_range(value: float) -> None:
    with pytest.raises(DomainValueError):
        StickVector(x=value, y=0.0)


def test_controller_frame_rejects_negative_sequence_metadata() -> None:
    with pytest.raises(DomainValueError):
        ControllerFrame(
            sequence=-1,
            capture_epoch=0,
            monotonic_ns=0,
            buttons=frozenset(),
            left_stick=StickVector(x=0.0, y=0.0),
            right_stick=StickVector(x=0.0, y=0.0),
            gyro_rate=GyroRate(
                x_radians_per_second=0.0,
                y_radians_per_second=0.0,
                z_radians_per_second=0.0,
            ),
            accel_g=AccelG(x_g=0.0, y_g=0.0, z_g=1.0),
            capture_active=False,
        )
