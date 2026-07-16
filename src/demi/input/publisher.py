"""Evaluate normalized input state and publish controller frames."""

from typing import ClassVar, Protocol

from demi.domain.controller import AccelG, ControllerFrame, GyroRate, StickVector
from demi.domain.errors import DomainValueError
from demi.domain.mapping import InputProfile, default_profile
from demi.domain.physical_input import PhysicalInputState
from demi.domain.settings import MouseSettings

from .mapper import aggregate_buttons, synthesize_stick
from .timing import InputEvaluationMetrics, InputTimingSnapshot
from .yaw_pitch_model import YawPitchModel


class Clock(Protocol):
    """Monotonic clock required by the input evaluation boundary."""

    def monotonic_ns(self) -> int:
        """Return the current monotonic time in nanoseconds."""


class FrameSink(Protocol):
    """Destination for the latest evaluated controller frame."""

    def offer_frame(self, frame: ControllerFrame) -> bool | None:
        """Accept one immutable controller frame."""


class InputPublisher:
    """Evaluate input state at an injected-clock boundary.

    The publisher does not schedule itself or wait for real time. The caller
    invokes :meth:`publish` at the configured evaluation boundary.
    """

    default_evaluation_interval_ms: ClassVar[int] = 8

    def __init__(
        self,
        *,
        clock: Clock,
        sink: FrameSink,
        profile: InputProfile | None = None,
        mouse_settings: MouseSettings | None = None,
        circular_limit: bool = False,
        evaluation_interval_ms: int = default_evaluation_interval_ms,
    ) -> None:
        """Initialize an input publisher.

        Args:
            clock: Monotonic clock used to derive elapsed evaluation time.
            sink: Destination that receives each generated frame.
            profile: Input profile to evaluate, defaulting to the built-in
                profile.
            mouse_settings: Mouse-to-IMU settings, defaulting to application
                defaults.
            circular_limit: Whether diagonal stick values are normalized.
            evaluation_interval_ms: Interval between scheduled input evaluations,
                in milliseconds.
        """
        self._clock = clock
        self._sink = sink
        self._profile = profile if profile is not None else default_profile()
        self._model = YawPitchModel(
            mouse_settings if mouse_settings is not None else MouseSettings()
        )
        self._circular_limit = circular_limit
        self._evaluation_interval_ms = self._validate_interval(evaluation_interval_ms)
        self._state = PhysicalInputState()
        self._sequence = 0
        self._last_monotonic_ns: int | None = None
        self._capture_epoch: int | None = None
        self._previous_mouse_x_per_second = 0.0
        self._previous_mouse_y_per_second = 0.0
        self._unemitted_mouse_x_units = 0.0
        self._unemitted_mouse_y_units = 0.0
        self._timing_metrics = InputEvaluationMetrics()

    @property
    def state(self) -> PhysicalInputState:
        """Return the mutable physical input state updated by event handlers."""
        return self._state

    @property
    def evaluation_interval_ms(self) -> int:
        """Return the configured input evaluation interval in milliseconds."""
        return self._evaluation_interval_ms

    @property
    def timing_metrics(self) -> InputTimingSnapshot:
        """Return recent input evaluation interval metrics."""
        return self._timing_metrics.snapshot

    def reconfigure(
        self,
        *,
        profile: InputProfile,
        mouse_settings: MouseSettings,
        circular_limit: bool,
        evaluation_interval_ms: int,
    ) -> None:
        """Apply saved input settings and reset state across the new boundary.

        Args:
            profile: Active input profile used by subsequent evaluations.
            mouse_settings: Mouse-to-IMU settings for a new yaw/pitch model.
            circular_limit: Whether diagonal sticks are normalized.
            evaluation_interval_ms: Scheduled evaluation interval from settings.
        """
        self._profile = profile
        self._model = YawPitchModel(mouse_settings)
        self._circular_limit = circular_limit
        self._evaluation_interval_ms = self._validate_interval(evaluation_interval_ms)
        self._state.clear()
        self._last_monotonic_ns = None
        self._capture_epoch = None
        self._reset_mouse_resampling()

    def publish(self, *, capture_active: bool, capture_epoch: int) -> ControllerFrame:
        """Evaluate current input and offer one controller frame.

        Args:
            capture_active: Whether keyboard and mouse mappings are enabled.
            capture_epoch: Session identifier attached to the generated frame.

        Returns:
            The same frame offered to the configured sink.
        """
        now_ns = self._clock.monotonic_ns()
        self._timing_metrics.note_evaluation(now_ns)
        epoch_changed = self._capture_epoch is not None and capture_epoch != self._capture_epoch
        first_evaluation = self._last_monotonic_ns is None
        if epoch_changed:
            self._state.clear()
            self._model.reset()
            self._reset_mouse_resampling()
        if not capture_active:
            self._state.clear()
            self._model.reset()
            self._reset_mouse_resampling()

        if first_evaluation or epoch_changed:
            dt_seconds = 0.0
        else:
            elapsed_ns = now_ns - self._last_monotonic_ns
            dt_seconds = (
                self._evaluation_interval_ms / 1_000.0
                if elapsed_ns == 0
                else elapsed_ns / 1_000_000_000.0
            )

        dx, dy = self._state.consume_mouse_motion()
        if capture_active:
            if dt_seconds > 0.0:
                dx, dy = self._resample_mouse_motion(dx, dy, dt_seconds)
            buttons = aggregate_buttons(self._profile, self._state, capture_active=True)
            left_stick = synthesize_stick(
                self._profile,
                self._state,
                "left",
                circular_limit=self._circular_limit,
            )
            right_stick = synthesize_stick(
                self._profile,
                self._state,
                "right",
                circular_limit=self._circular_limit,
            )
            gyro_rate, accel_g = self._model.update(
                dx=dx,
                dy=dy,
                dt_seconds=dt_seconds,
            )
        else:
            buttons = frozenset()
            left_stick = StickVector(x=0.0, y=0.0)
            right_stick = StickVector(x=0.0, y=0.0)
            gyro_rate = GyroRate(0.0, 0.0, 0.0)
            accel_g = AccelG(0.0, 0.0, 1.0)

        self._sequence += 1
        frame = ControllerFrame(
            sequence=self._sequence,
            capture_epoch=capture_epoch,
            monotonic_ns=now_ns,
            buttons=buttons,
            left_stick=left_stick,
            right_stick=right_stick,
            gyro_rate=gyro_rate,
            accel_g=accel_g,
            capture_active=capture_active,
        )
        self._last_monotonic_ns = now_ns
        self._capture_epoch = capture_epoch
        self._sink.offer_frame(frame)
        return frame

    @staticmethod
    def _validate_interval(value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or not 4 <= value <= 32:
            raise DomainValueError
        return value

    def _resample_mouse_motion(
        self,
        dx: float,
        dy: float,
        dt_seconds: float,
    ) -> tuple[float, float]:
        current_x_per_second = dx / dt_seconds
        current_y_per_second = dy / dt_seconds
        resampled_x_per_second = (self._previous_mouse_x_per_second + current_x_per_second) * 0.5
        resampled_y_per_second = (self._previous_mouse_y_per_second + current_y_per_second) * 0.5
        resampled_dx = resampled_x_per_second * dt_seconds
        resampled_dy = resampled_y_per_second * dt_seconds
        self._unemitted_mouse_x_units += dx
        self._unemitted_mouse_y_units += dy
        if dx == 0.0 or self._can_emit_reversed_motion(
            current_x_per_second,
            self._previous_mouse_x_per_second,
            self._unemitted_mouse_x_units,
        ):
            resampled_dx = self._unemitted_mouse_x_units
            self._unemitted_mouse_x_units = 0.0
        else:
            resampled_dx = self._limit_to_unemitted_motion(
                resampled_dx,
                self._unemitted_mouse_x_units,
            )
            self._unemitted_mouse_x_units -= resampled_dx
        if dy == 0.0 or self._can_emit_reversed_motion(
            current_y_per_second,
            self._previous_mouse_y_per_second,
            self._unemitted_mouse_y_units,
        ):
            resampled_dy = self._unemitted_mouse_y_units
            self._unemitted_mouse_y_units = 0.0
        else:
            resampled_dy = self._limit_to_unemitted_motion(
                resampled_dy,
                self._unemitted_mouse_y_units,
            )
            self._unemitted_mouse_y_units -= resampled_dy
        self._previous_mouse_x_per_second = current_x_per_second
        self._previous_mouse_y_per_second = current_y_per_second
        return resampled_dx, resampled_dy

    @staticmethod
    def _can_emit_reversed_motion(
        current_per_second: float,
        previous_per_second: float,
        unemitted: float,
    ) -> bool:
        return (
            current_per_second * previous_per_second < 0.0 and current_per_second * unemitted > 0.0
        )

    @staticmethod
    def _limit_to_unemitted_motion(candidate: float, unemitted: float) -> float:
        if candidate * unemitted <= 0.0:
            return 0.0
        if abs(candidate) > abs(unemitted):
            return unemitted
        return candidate

    def _reset_mouse_resampling(self) -> None:
        self._previous_mouse_x_per_second = 0.0
        self._previous_mouse_y_per_second = 0.0
        self._unemitted_mouse_x_units = 0.0
        self._unemitted_mouse_y_units = 0.0
