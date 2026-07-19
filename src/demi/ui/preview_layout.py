"""Pure relative geometry for the controller preview."""

from collections.abc import Mapping
from dataclasses import dataclass

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

    controls: Mapping[str, PreviewRect]


_RELATIVE_CONTROLS = {
    "zl": (0.08, 0.06, 0.12, 0.07),
    "l": (0.22, 0.06, 0.12, 0.07),
    "r": (0.66, 0.06, 0.12, 0.07),
    "zr": (0.80, 0.06, 0.12, 0.07),
    "dpad_up": (0.17, 0.28, 0.055, 0.07),
    "dpad_left": (0.105, 0.36, 0.055, 0.07),
    "dpad_right": (0.235, 0.36, 0.055, 0.07),
    "dpad_down": (0.17, 0.44, 0.055, 0.07),
    "x": (0.775, 0.28, 0.055, 0.07),
    "y": (0.71, 0.36, 0.055, 0.07),
    "a": (0.84, 0.36, 0.055, 0.07),
    "b": (0.775, 0.44, 0.055, 0.07),
    "minus": (0.40, 0.28, 0.06, 0.06),
    "plus": (0.54, 0.28, 0.06, 0.06),
    "home": (0.40, 0.40, 0.06, 0.06),
    "capture": (0.54, 0.40, 0.06, 0.06),
    "left_stick": (0.23, 0.58, 0.16, 0.18),
    "left_stick_click": (0.285, 0.64, 0.05, 0.06),
    "right_stick": (0.61, 0.58, 0.16, 0.18),
    "right_stick_click": (0.665, 0.64, 0.05, 0.06),
}


def preview_layout(width: int, height: int) -> PreviewLayout:
    """Return relative control bounds scaled to one positive canvas size."""
    if width <= 0 or height <= 0:
        raise DomainValueError
    return PreviewLayout(
        controls={
            control_id: PreviewRect(
                left * width,
                top * height,
                relative_width * width,
                relative_height * height,
            )
            for control_id, (
                left,
                top,
                relative_width,
                relative_height,
            ) in _RELATIVE_CONTROLS.items()
        }
    )
