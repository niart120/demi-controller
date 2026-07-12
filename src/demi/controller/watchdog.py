"""Fake-clock driven input frame watchdog."""

from typing import ClassVar, Protocol

from demi.domain.controller import ControllerFrame


class WatchdogClock(Protocol):
    """Monotonic clock required by the watchdog."""

    def monotonic_ns(self) -> int:
        """Return monotonic time in nanoseconds."""


class FrameWatchdog:
    """Detect a stalled captured frame stream without sleeping in tests."""

    monitor_interval_ms: ClassVar[int] = 50
    timeout_ms: ClassVar[int] = 250

    def __init__(self, *, clock: WatchdogClock) -> None:
        """Initialize an inactive watchdog with an injected clock."""
        self._clock = clock
        self._connected = False
        self._capture_active = False
        self._capture_epoch: int | None = None
        self._last_active_ns: int | None = None
        self._tripped_epoch: int | None = None

    @property
    def watchdog_tripped(self) -> bool:
        """Return whether the current capture epoch has tripped."""
        return self._tripped_epoch is not None and self._tripped_epoch == self._capture_epoch

    @property
    def capture_epoch(self) -> int | None:
        """Return the capture epoch currently being monitored."""
        return self._capture_epoch

    def set_connected(self, connected: bool) -> None:
        """Enable or disable monitoring for an active connection."""
        self._connected = connected
        if not connected:
            self._capture_active = False
            self._last_active_ns = None

    def note_frame(self, frame: ControllerFrame) -> None:
        """Record a received frame and reset the active epoch timer."""
        if self._capture_epoch != frame.capture_epoch:
            self._tripped_epoch = None
        self._capture_epoch = frame.capture_epoch
        self._capture_active = frame.capture_active
        if frame.capture_active:
            self._last_active_ns = self._clock.monotonic_ns()
        else:
            self._last_active_ns = None
            self._tripped_epoch = None

    def check(self) -> bool:
        """Return true once when the active stream exceeds 250ms."""
        if (
            not self._connected
            or not self._capture_active
            or self._last_active_ns is None
            or self.watchdog_tripped
        ):
            return False
        elapsed_ns = self._clock.monotonic_ns() - self._last_active_ns
        if elapsed_ns < self.timeout_ms * 1_000_000:
            return False
        self._tripped_epoch = self._capture_epoch
        return True
