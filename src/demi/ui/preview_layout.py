"""Pure relative geometry for the controller preview."""

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite

from demi.domain.errors import DomainValueError


@dataclass(frozen=True, slots=True)
class PreviewRect:
    """One rectangular preview region in widget coordinates."""

    left: float
    top: float
    width: float
    height: float

    @property
    def right(self) -> float:
        """Return the right edge."""
        return self.left + self.width

    @property
    def bottom(self) -> float:
        """Return the bottom edge."""
        return self.top + self.height

    def intersects(self, other: "PreviewRect") -> bool:
        """Return whether this rectangle has positive-area overlap with another."""
        return (
            self.left < other.right
            and other.left < self.right
            and self.top < other.bottom
            and other.top < self.bottom
        )


@dataclass(frozen=True, slots=True)
class PreviewLayout:
    """Named control bounds for one preview canvas size."""

    content_bounds: PreviewRect
    body_bounds: PreviewRect
    left_grip_bounds: PreviewRect
    right_grip_bounds: PreviewRect
    status_bounds: PreviewRect
    gyro_bounds: PreviewRect
    accel_bounds: PreviewRect
    controls: Mapping[str, PreviewRect]


_RELATIVE_CONTROLS = {
    "zl": (0.08, 0.09, 0.12, 0.07),
    "l": (0.22, 0.09, 0.12, 0.07),
    "r": (0.66, 0.09, 0.12, 0.07),
    "zr": (0.80, 0.09, 0.12, 0.07),
    "dpad_up": (0.255, 0.53, 0.09, 0.065),
    "dpad_left": (0.21, 0.59, 0.09, 0.065),
    "dpad_right": (0.30, 0.59, 0.09, 0.065),
    "dpad_down": (0.255, 0.65, 0.09, 0.065),
    "x": (0.775, 0.28, 0.055, 0.07),
    "y": (0.71, 0.36, 0.055, 0.07),
    "a": (0.81, 0.36, 0.055, 0.07),
    "b": (0.775, 0.44, 0.055, 0.07),
    "minus": (0.40, 0.28, 0.06, 0.06),
    "plus": (0.54, 0.28, 0.06, 0.06),
    "home": (0.40, 0.40, 0.06, 0.06),
    "capture": (0.54, 0.40, 0.06, 0.06),
    "left_stick": (0.15, 0.31, 0.16, 0.18),
    "left_stick_click": (0.205, 0.37, 0.05, 0.06),
    "right_stick": (0.57, 0.55, 0.16, 0.18),
    "right_stick_click": (0.625, 0.61, 0.05, 0.06),
}
CONTROL_IDS = frozenset(_RELATIVE_CONTROLS)
_CONTENT_ASPECT_RATIO = 8 / 5
_ROUND_CONTROL_IDS = frozenset(
    {
        "a",
        "b",
        "x",
        "y",
        "left_stick",
        "left_stick_click",
        "right_stick",
        "right_stick_click",
    }
)


def normalized_stick_position(x: float, y: float) -> tuple[float, float]:
    """Clamp finite stick display coordinates to the normalized square."""
    if isinstance(x, bool) or isinstance(y, bool) or not isfinite(x) or not isfinite(y):
        raise DomainValueError
    return max(-1.0, min(1.0, x)), max(-1.0, min(1.0, y))


def preview_layout(width: int, height: int) -> PreviewLayout:
    """Return relative control bounds scaled to one positive canvas size."""
    if width <= 0 or height <= 0:
        raise DomainValueError
    if width / height > _CONTENT_ASPECT_RATIO:
        content_height = float(height)
        content_width = content_height * _CONTENT_ASPECT_RATIO
    else:
        content_width = float(width)
        content_height = content_width / _CONTENT_ASPECT_RATIO
    content_bounds = PreviewRect(
        left=(width - content_width) / 2,
        top=(height - content_height) / 2,
        width=content_width,
        height=content_height,
    )
    controls: dict[str, PreviewRect] = {}
    for control_id, (left, top, relative_width, relative_height) in _RELATIVE_CONTROLS.items():
        control_width = relative_width * content_width
        control_height = relative_height * content_height
        control_left = content_bounds.left + left * content_width
        if control_id in _ROUND_CONTROL_IDS:
            control_left += (control_width - control_height) / 2
            control_width = control_height
        controls[control_id] = PreviewRect(
            left=control_left,
            top=content_bounds.top + top * content_height,
            width=control_width,
            height=control_height,
        )
    return PreviewLayout(
        content_bounds=content_bounds,
        body_bounds=_scaled_rect(content_bounds, 0.13, 0.16, 0.74, 0.60),
        left_grip_bounds=_scaled_rect(content_bounds, 0.04, 0.40, 0.21, 0.47),
        right_grip_bounds=_scaled_rect(content_bounds, 0.75, 0.40, 0.21, 0.47),
        status_bounds=_scaled_rect(content_bounds, 0.18, 0.875, 0.64, 0.04),
        gyro_bounds=_scaled_rect(content_bounds, 0.06, 0.925, 0.40, 0.07),
        accel_bounds=_scaled_rect(content_bounds, 0.54, 0.925, 0.40, 0.07),
        controls=controls,
    )


def _scaled_rect(
    content: PreviewRect,
    left: float,
    top: float,
    width: float,
    height: float,
) -> PreviewRect:
    return PreviewRect(
        left=content.left + left * content.width,
        top=content.top + top * content.height,
        width=width * content.width,
        height=height * content.height,
    )
