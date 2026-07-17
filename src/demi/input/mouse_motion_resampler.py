"""Resample accumulated relative mouse motion at evaluation boundaries."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class _AxisMotionResampler:
    previous_units_per_second: float = 0.0
    unemitted_units: float = 0.0

    def resample(self, units: float, dt_seconds: float) -> float:
        current_units_per_second = units / dt_seconds
        emitted_units = (
            (self.previous_units_per_second + current_units_per_second) * 0.5 * dt_seconds
        )
        self.unemitted_units += units
        if units == 0.0 or self._can_emit_reversed_motion(current_units_per_second):
            emitted_units = self.unemitted_units
            self.unemitted_units = 0.0
        else:
            emitted_units = self._limit_to_unemitted_motion(emitted_units)
            self.unemitted_units -= emitted_units
        self.previous_units_per_second = current_units_per_second
        return emitted_units

    def reset(self) -> None:
        self.previous_units_per_second = 0.0
        self.unemitted_units = 0.0

    def _can_emit_reversed_motion(self, current_units_per_second: float) -> bool:
        return (
            current_units_per_second * self.previous_units_per_second < 0.0
            and current_units_per_second * self.unemitted_units > 0.0
        )

    def _limit_to_unemitted_motion(self, candidate: float) -> float:
        if candidate * self.unemitted_units <= 0.0:
            return 0.0
        if abs(candidate) > abs(self.unemitted_units):
            return self.unemitted_units
        return candidate


@dataclass(slots=True)
class MouseMotionResampler:
    """Preserve relative mouse displacement across evaluation intervals."""

    _x_axis: _AxisMotionResampler = field(default_factory=_AxisMotionResampler)
    _y_axis: _AxisMotionResampler = field(default_factory=_AxisMotionResampler)

    def resample(self, dx: float, dy: float, dt_seconds: float) -> tuple[float, float]:
        """Return X/Y motion resampled for one positive evaluation interval."""
        return (
            self._x_axis.resample(dx, dt_seconds),
            self._y_axis.resample(dy, dt_seconds),
        )

    def reset(self) -> None:
        """Discard velocity history and unemitted relative movement."""
        self._x_axis.reset()
        self._y_axis.reset()
