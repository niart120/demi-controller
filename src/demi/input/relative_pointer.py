"""Framework-independent relative-pointer capability and fallback motion."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import Protocol


class RelativePointerQuality(StrEnum):
    """Describe whether a relative-pointer value is raw, accelerated, or absent."""

    RAW_UNACCELERATED = "raw_unaccelerated"
    RELATIVE_ACCELERATED = "relative_accelerated"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class RelativePointerCapability:
    """Describe the quality and availability of one pointer backend."""

    quality: RelativePointerQuality

    @property
    def is_available(self) -> bool:
        """Return whether the backend can currently produce relative motion."""
        return self.quality is not RelativePointerQuality.UNAVAILABLE


@dataclass(frozen=True, slots=True)
class RelativeMotion:
    """Represent one backend-normalized relative pointer movement.

    Args:
        dx: Horizontal relative movement.
        dy: Vertical relative movement.
        quality: Provenance of the movement values.

    Raises:
        ValueError: If either movement value is not finite.
    """

    dx: float
    dy: float
    quality: RelativePointerQuality

    def __post_init__(self) -> None:
        """Reject movement values that cannot be evaluated deterministically."""
        if not isfinite(self.dx) or not isfinite(self.dy):
            raise ValueError


type RelativeMotionCallback = Callable[[RelativeMotion], object]


class RelativePointerBackend(Protocol):
    """Provide relative pointer lifecycle, quality, and normalized movement."""

    @property
    def capability(self) -> RelativePointerCapability:
        """Return the current relative-pointer quality without guessing raw support."""

    def start_relative_pointer_capture(self, capture_epoch: int) -> None:
        """Start accepting movement for one capture epoch."""

    def stop_relative_pointer_capture(self) -> None:
        """Stop accepting movement and discard any pending position reference."""


class QtRelativePointerBackend:
    """Turn Qt-derived positions into explicitly accelerated fallback movement."""

    def __init__(
        self,
        *,
        on_relative_motion: RelativeMotionCallback,
        available: bool = True,
    ) -> None:
        """Create a fallback backend without claiming unverified raw input.

        Args:
            on_relative_motion: Receives current-epoch normalized movement.
            available: Whether the current Qt platform path can supply positions.
        """
        self._on_relative_motion = on_relative_motion
        quality = (
            RelativePointerQuality.RELATIVE_ACCELERATED
            if available
            else RelativePointerQuality.UNAVAILABLE
        )
        self._capability = RelativePointerCapability(quality)
        self._capture_epoch: int | None = None
        self._last_position: tuple[float, float] | None = None

    @property
    def capability(self) -> RelativePointerCapability:
        """Return accelerated or unavailable fallback capability."""
        return self._capability

    def start_relative_pointer_capture(self, capture_epoch: int) -> None:
        """Begin one fallback capture epoch and establish a fresh position reference."""
        self._capture_epoch = capture_epoch
        self._last_position = None

    def stop_relative_pointer_capture(self) -> None:
        """Discard the active fallback capture epoch and its position reference."""
        self._capture_epoch = None
        self._last_position = None

    def handle_position(self, x: float, y: float, *, capture_epoch: int) -> bool:
        """Emit one accelerated delta when a current finite position advances.

        Args:
            x: Current horizontal Qt position.
            y: Current vertical Qt position.
            capture_epoch: Epoch that owned the originating Qt event.

        Returns:
            ``True`` when a nonzero accelerated motion was emitted.
        """
        if (
            not self._capability.is_available
            or capture_epoch != self._capture_epoch
            or not isfinite(x)
            or not isfinite(y)
        ):
            return False
        position = (x, y)
        last_position = self._last_position
        self._last_position = position
        if last_position is None:
            return False
        dx = x - last_position[0]
        dy = y - last_position[1]
        if dx == 0.0 and dy == 0.0:
            return False
        self._on_relative_motion(
            RelativeMotion(
                dx=dx,
                dy=dy,
                quality=RelativePointerQuality.RELATIVE_ACCELERATED,
            )
        )
        return True
