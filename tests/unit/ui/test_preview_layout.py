import itertools

import pytest

from demi.ui.preview_layout import normalized_stick_position, preview_layout


@pytest.mark.parametrize("size", [(800, 520), (960, 640), (1440, 900)])
def test_preview_layout_keeps_all_controls_in_bounds_without_unintended_overlap(
    size: tuple[int, int],
) -> None:
    layout = preview_layout(*size)
    allowed_intersections = {
        frozenset({"left_stick", "left_stick_click"}),
        frozenset({"right_stick", "right_stick_click"}),
    }
    directional_pad_ids = frozenset({"dpad_up", "dpad_right", "dpad_down", "dpad_left"})

    assert layout.controls
    for bounds in layout.controls.values():
        assert bounds.left >= 0.0
        assert bounds.top >= 0.0
        assert bounds.right <= size[0]
        assert bounds.bottom <= size[1]

    for (first_id, first), (second_id, second) in itertools.combinations(
        layout.controls.items(), 2
    ):
        control_pair = frozenset({first_id, second_id})
        if control_pair in allowed_intersections or control_pair <= directional_pad_ids:
            continue
        assert not first.intersects(second), f"{first_id} overlaps {second_id}"


@pytest.mark.parametrize(
    ("size", "expected_bounds"),
    [
        ((480, 300), (0.0, 0.0, 480.0, 300.0)),
        ((1200, 520), (184.0, 0.0, 832.0, 520.0)),
        ((600, 900), (0.0, 262.5, 600.0, 375.0)),
    ],
)
def test_preview_layout_centers_an_eight_by_five_content_region(
    size: tuple[int, int],
    expected_bounds: tuple[float, float, float, float],
) -> None:
    content = preview_layout(*size).content_bounds

    assert (content.left, content.top, content.width, content.height) == expected_bounds
    assert content.width / content.height == pytest.approx(8 / 5)


@pytest.mark.parametrize("size", [(480, 300), (1200, 520), (600, 900)])
def test_preview_layout_keeps_round_controls_circular(size: tuple[int, int]) -> None:
    controls = preview_layout(*size).controls
    round_control_ids = {
        "a",
        "b",
        "x",
        "y",
        "left_stick",
        "left_stick_click",
        "right_stick",
        "right_stick_click",
    }

    for control_id in round_control_ids:
        bounds = controls[control_id]
        assert bounds.width == pytest.approx(bounds.height), control_id


@pytest.mark.parametrize("size", [(480, 300), (960, 640), (1200, 520), (600, 900)])
def test_preview_layout_keeps_major_regions_inside_content_without_overlap(
    size: tuple[int, int],
) -> None:
    layout = preview_layout(*size)
    content = layout.content_bounds
    regions = {
        "body": layout.body_bounds,
        "status": layout.status_bounds,
        "gyro": layout.gyro_bounds,
        "accel": layout.accel_bounds,
        **layout.controls,
    }

    for region_id, bounds in regions.items():
        assert bounds.left >= content.left, region_id
        assert bounds.top >= content.top, region_id
        assert bounds.right <= content.right, region_id
        assert bounds.bottom <= content.bottom, region_id

    assert not layout.body_bounds.intersects(layout.gyro_bounds)
    assert not layout.body_bounds.intersects(layout.accel_bounds)
    assert not layout.gyro_bounds.intersects(layout.accel_bounds)
    for control_id, bounds in layout.controls.items():
        assert not bounds.intersects(layout.status_bounds), control_id
        assert not bounds.intersects(layout.gyro_bounds), control_id
        assert not bounds.intersects(layout.accel_bounds), control_id


def test_preview_layout_reserves_readable_height_for_imu_at_minimum_window_size() -> None:
    layout = preview_layout(800, 480)

    assert layout.gyro_bounds.height >= 48.0
    assert layout.accel_bounds.height >= 48.0


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ((0.25, -0.75), (0.25, -0.75)),
        ((2.0, -2.0), (1.0, -1.0)),
        ((-1.5, 1.5), (-1.0, 1.0)),
    ],
)
def test_stick_display_position_clamps_each_axis(
    value: tuple[float, float], expected: tuple[float, float]
) -> None:
    assert normalized_stick_position(*value) == expected
