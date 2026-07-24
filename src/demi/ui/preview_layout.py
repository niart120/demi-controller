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
    "zl": (0.19, 0.02, 0.078, 0.065),
    "l": (0.275, 0.02, 0.078, 0.065),
    "r": (0.647, 0.02, 0.078, 0.065),
    "zr": (0.732, 0.02, 0.078, 0.065),
    "dpad_up": (0.34, 0.37, 0.04, 0.096),
    "dpad_left": (0.30, 0.434, 0.06, 0.064),
    "dpad_right": (0.36, 0.434, 0.06, 0.064),
    "dpad_down": (0.34, 0.466, 0.04, 0.096),
    "x": (0.6725, 0.14, 0.055, 0.07),
    "y": (0.6225, 0.22, 0.055, 0.07),
    "a": (0.7225, 0.22, 0.055, 0.07),
    "b": (0.6725, 0.30, 0.055, 0.07),
    "minus": (0.409, 0.17, 0.042, 0.05),
    "plus": (0.549, 0.17, 0.042, 0.05),
    "home": (0.449, 0.235, 0.042, 0.05),
    "capture": (0.509, 0.235, 0.042, 0.05),
    "left_stick": (0.225, 0.15, 0.15, 0.18),
    "left_stick_click": (0.275, 0.21, 0.05, 0.06),
    "right_stick": (0.545, 0.39, 0.15, 0.18),
    "right_stick_click": (0.595, 0.45, 0.05, 0.06),
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
        "minus",
        "plus",
        "home",
        "capture",
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
        body_bounds=_scaled_rect(content_bounds, 0.18, 0.00, 0.64, 0.65),
        left_grip_bounds=_scaled_rect(content_bounds, 0.18, 0.30, 0.16, 0.39),
        right_grip_bounds=_scaled_rect(content_bounds, 0.66, 0.30, 0.16, 0.39),
        status_bounds=_scaled_rect(content_bounds, 0.18, 0.71, 0.64, 0.045),
        gyro_bounds=_scaled_rect(content_bounds, 0.18, 0.78, 0.30, 0.20),
        accel_bounds=_scaled_rect(content_bounds, 0.52, 0.78, 0.30, 0.20),
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
