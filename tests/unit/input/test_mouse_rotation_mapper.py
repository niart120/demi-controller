from math import inf, nan

import pytest

from demi.domain.errors import DomainValueError
from demi.domain.settings import MouseSettings
from demi.input.mouse_rotation_mapper import (
    BASE_PITCH_RADIANS_PER_INPUT_UNIT,
    BASE_YAW_RADIANS_PER_INPUT_UNIT,
    MouseRotationMapper,
)
from demi.input.rotation_intent import RotationIntent


def test_disabled_mouse_gyro_returns_zero_rotation_intent() -> None:
    mapper = MouseRotationMapper(MouseSettings(gyro_enabled=False))

    intent = mapper.map(dx=100.0, dy=-100.0)

    assert intent == RotationIntent(0.0, 0.0)


def test_horizontal_and_vertical_sensitivity_are_independent() -> None:
    horizontal = MouseRotationMapper(MouseSettings(horizontal_sensitivity=2.0))
    vertical = MouseRotationMapper(MouseSettings(vertical_sensitivity=2.0))

    horizontal_intent = horizontal.map(dx=1.0, dy=1.0)
    vertical_intent = vertical.map(dx=1.0, dy=1.0)

    assert horizontal_intent.yaw_delta_radians == pytest.approx(
        -2.0 * BASE_YAW_RADIANS_PER_INPUT_UNIT
    )
    assert horizontal_intent.pitch_delta_radians == pytest.approx(BASE_PITCH_RADIANS_PER_INPUT_UNIT)
    assert vertical_intent.yaw_delta_radians == pytest.approx(-BASE_YAW_RADIANS_PER_INPUT_UNIT)
    assert vertical_intent.pitch_delta_radians == pytest.approx(
        2.0 * BASE_PITCH_RADIANS_PER_INPUT_UNIT
    )


def test_x_and_y_inversion_change_only_their_matching_rotation_axis() -> None:
    normal = MouseRotationMapper(MouseSettings()).map(dx=2.0, dy=1.0)
    invert_x = MouseRotationMapper(MouseSettings(invert_x=True)).map(dx=2.0, dy=1.0)
    invert_y = MouseRotationMapper(MouseSettings(invert_y=True)).map(dx=2.0, dy=1.0)

    assert invert_x.yaw_delta_radians == pytest.approx(-normal.yaw_delta_radians)
    assert invert_x.pitch_delta_radians == pytest.approx(normal.pitch_delta_radians)
    assert invert_y.yaw_delta_radians == pytest.approx(normal.yaw_delta_radians)
    assert invert_y.pitch_delta_radians == pytest.approx(-normal.pitch_delta_radians)


@pytest.mark.parametrize(("dx", "dy"), [(nan, 0.0), (0.0, inf)])
def test_non_finite_mouse_motion_is_rejected(dx: float, dy: float) -> None:
    mapper = MouseRotationMapper(MouseSettings())

    with pytest.raises(DomainValueError):
        mapper.map(dx=dx, dy=dy)
