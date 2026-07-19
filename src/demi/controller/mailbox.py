"""Thread-safe latest-frame view and constant-size send coalescer."""

import logging
from dataclasses import replace
from threading import Lock

from demi.domain.controller import ControllerFrame, GyroRate

_LOGGER = logging.getLogger(__name__)


class LatestFrameMailbox:
    """Keep the newest view while coalescing pending angular displacement."""

    def __init__(self) -> None:
        """Initialize an empty mailbox."""
        self._lock = Lock()
        self._latest: ControllerFrame | None = None
        self._pending: ControllerFrame | None = None
        self._pending_impulse = (0.0, 0.0, 0.0)
        self._pending_count = 0
        self._pending_first_sequence: int | None = None
        self._current_epoch: int | None = None
        self._last_sequence = -1

    @property
    def current_epoch(self) -> int | None:
        """Return the newest accepted capture epoch."""
        with self._lock:
            return self._current_epoch

    @property
    def last_sequence(self) -> int:
        """Return the newest accepted sequence number."""
        with self._lock:
            return self._last_sequence

    def offer(self, frame: ControllerFrame) -> bool:
        """Offer one frame and return whether it became the latest value.

        A frame is rejected when its sequence is not newer than the last
        accepted frame or when its capture epoch is older than the current
        session. A newer epoch advances the session boundary.
        """
        with self._lock:
            if frame.sequence <= self._last_sequence:
                return False
            if self._current_epoch is not None and frame.capture_epoch < self._current_epoch:
                return False
            if self._current_epoch is not None and frame.capture_epoch > self._current_epoch:
                self._clear_pending()
            self._current_epoch = frame.capture_epoch
            self._last_sequence = frame.sequence
            self._latest = frame
            self._append_pending(frame)
            return True

    def peek(self) -> ControllerFrame | None:
        """Return the latest frame without consuming it."""
        with self._lock:
            return self._latest

    def take(self) -> ControllerFrame | None:
        """Return and clear the next coalesced frame to send."""
        with self._lock:
            frame = self._pending
            count = self._pending_count
            first_sequence = self._pending_first_sequence
            self._clear_pending()
        if frame is not None and count > 1:
            _LOGGER.debug(
                "Coalesced controller frames",
                extra={
                    "frame_count": count,
                    "first_sequence": first_sequence,
                    "last_sequence": frame.sequence,
                    "sample_duration_ns": frame.sample_duration_ns,
                },
            )
        return frame

    def discard_pending(self, *, reason: str) -> bool:
        """Discard unsent input at a safety boundary and record its reason."""
        with self._lock:
            frame = self._pending
            self._clear_pending()
        if frame is None:
            return False
        _LOGGER.debug(
            "Discarded coalesced controller frame",
            extra={
                "reason": reason,
                "sequence": frame.sequence,
                "capture_epoch": frame.capture_epoch,
                "sample_duration_ns": frame.sample_duration_ns,
            },
        )
        return True

    def _append_pending(self, frame: ControllerFrame) -> None:
        if self._pending is None:
            self._pending = frame
            self._pending_impulse = self._impulse_for(frame)
            self._pending_count = 1
            self._pending_first_sequence = frame.sequence
            return
        previous = self._pending
        impulse = tuple(
            current + added
            for current, added in zip(self._pending_impulse, self._impulse_for(frame), strict=True)
        )
        duration_ns = previous.sample_duration_ns + frame.sample_duration_ns
        gyro_rate = (
            GyroRate(*(value * 1_000_000_000 / duration_ns for value in impulse))
            if duration_ns > 0
            else frame.gyro_rate
        )
        self._pending = replace(
            frame,
            gyro_rate=gyro_rate,
            sample_duration_ns=duration_ns,
        )
        self._pending_impulse = impulse
        self._pending_count += 1

    def _clear_pending(self) -> None:
        self._pending = None
        self._pending_impulse = (0.0, 0.0, 0.0)
        self._pending_count = 0
        self._pending_first_sequence = None

    @staticmethod
    def _impulse_for(frame: ControllerFrame) -> tuple[float, float, float]:
        duration_seconds = frame.sample_duration_ns / 1_000_000_000.0
        gyro = frame.gyro_rate
        return (
            gyro.x_radians_per_second * duration_seconds,
            gyro.y_radians_per_second * duration_seconds,
            gyro.z_radians_per_second * duration_seconds,
        )
