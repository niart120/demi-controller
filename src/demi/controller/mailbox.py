"""Thread-safe latest-controller-frame mailbox."""

from threading import Lock

from demi.domain.controller import ControllerFrame


class LatestFrameMailbox:
    """Keep the newest frame while rejecting stale sequence or epoch values."""

    def __init__(self) -> None:
        """Initialize an empty mailbox."""
        self._lock = Lock()
        self._latest: ControllerFrame | None = None
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
            self._current_epoch = frame.capture_epoch
            self._last_sequence = frame.sequence
            self._latest = frame
            return True

    def peek(self) -> ControllerFrame | None:
        """Return the latest frame without consuming it."""
        with self._lock:
            return self._latest

    def take(self) -> ControllerFrame | None:
        """Return and clear the latest frame slot."""
        with self._lock:
            frame = self._latest
            self._latest = None
            return frame
