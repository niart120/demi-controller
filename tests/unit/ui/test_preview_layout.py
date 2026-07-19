import itertools

import pytest

from demi.ui.preview_layout import preview_layout


@pytest.mark.parametrize("size", [(800, 520), (960, 640), (1440, 900)])
def test_preview_layout_keeps_all_controls_in_bounds_without_unintended_overlap(
    size: tuple[int, int],
) -> None:
    layout = preview_layout(*size)
    allowed_intersections = {
        frozenset({"left_stick", "left_stick_click"}),
        frozenset({"right_stick", "right_stick_click"}),
    }

    assert layout.controls
    for bounds in layout.controls.values():
        assert bounds.left >= 0.0
        assert bounds.top >= 0.0
        assert bounds.right <= size[0]
        assert bounds.bottom <= size[1]

    for (first_id, first), (second_id, second) in itertools.combinations(
        layout.controls.items(), 2
    ):
        if frozenset({first_id, second_id}) in allowed_intersections:
            continue
        assert not first.intersects(second), f"{first_id} overlaps {second_id}"
