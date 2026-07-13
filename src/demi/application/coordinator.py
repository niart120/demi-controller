"""Main-thread capture lifecycle coordination."""

from contextlib import suppress
from typing import Protocol

from demi.domain.controller import ControllerFrame
from demi.input.publisher import InputPublisher

from .state import AppState


class PointerCapturePort(Protocol):
    """Framework-independent pointer capture operation."""

    def set_pointer_capture(self, enabled: bool) -> None:
        """Enable or disable pointer capture for the foreground window."""


class CaptureCoordinator:
    """Own capture state, epoch changes, and neutral frame transitions."""

    def __init__(
        self,
        *,
        publisher: InputPublisher,
        pointer_capture: PointerCapturePort,
    ) -> None:
        """Initialize a coordinator in the focused idle state."""
        self._publisher = publisher
        self._pointer_capture = pointer_capture
        self._app_state = AppState.IDLE
        self._capture_epoch = 0
        self._focused = True
        self._last_frame: ControllerFrame | None = None

    @property
    def app_state(self) -> AppState:
        """Return the current application lifecycle state."""
        return self._app_state

    @property
    def capture_epoch(self) -> int:
        """Return the current capture session identifier."""
        return self._capture_epoch

    @property
    def focused(self) -> bool:
        """Return whether the window is currently focused."""
        return self._focused

    @property
    def publisher(self) -> InputPublisher:
        """Return the input publisher owned by the coordinator."""
        return self._publisher

    @property
    def is_captured(self) -> bool:
        """Return whether controller input capture is active."""
        return self._app_state is AppState.CAPTURED

    @property
    def last_frame(self) -> ControllerFrame | None:
        """Return the latest frame published by this coordinator."""
        return self._last_frame

    def start_capture(self) -> bool:
        """Start capture and publish an initial active neutral frame.

        Returns:
            ``True`` when exclusive mouse capture and the initial frame were
            established; otherwise ``False`` and the state remains idle.
        """
        if self._app_state is not AppState.IDLE or not self._focused:
            return False

        self._capture_epoch += 1
        self._publisher.state.clear()
        try:
            self._pointer_capture.set_pointer_capture(True)
        except (OSError, RuntimeError):
            self._publisher.state.clear()
            self._app_state = AppState.IDLE
            return False

        self._app_state = AppState.CAPTURED
        self._publish_frame(capture_active=True)
        return True

    def evaluate(self) -> ControllerFrame:
        """Publish the current capture state at one scheduled clock tick."""
        return self._publish_frame(capture_active=self.is_captured)

    def _publish_frame(self, *, capture_active: bool) -> ControllerFrame:
        self._last_frame = self._publisher.publish(
            capture_active=capture_active,
            capture_epoch=self._capture_epoch,
        )
        return self._last_frame

    def stop_capture(self) -> ControllerFrame | None:
        """Stop capture and publish a capture-inactive neutral frame.

        Returns:
            The neutral frame when capture was active, or ``None`` for an
            idempotent stop request outside capture.
        """
        if not self.is_captured:
            return None
        return self._leave_capture(AppState.IDLE)

    def open_configuration(self) -> bool:
        """Enter configuration state after publishing a neutral frame."""
        if self._app_state is AppState.CAPTURED:
            self._leave_capture(AppState.CONFIGURING)
            return True
        if self._app_state is not AppState.IDLE:
            return False
        self._app_state = AppState.CONFIGURING
        self._publish_frame(capture_active=False)
        return True

    def close_configuration(self) -> bool:
        """Leave configuration state without automatically recapturing input."""
        if self._app_state is not AppState.CONFIGURING:
            return False
        self._app_state = AppState.IDLE
        return True

    def toggle_capture(self) -> bool:
        """Start capture from idle or stop it when already captured.

        Returns:
            ``True`` when the requested transition was carried out.
        """
        if self.is_captured:
            return self.stop_capture() is not None
        return self.start_capture()

    def on_focus_lost(self) -> ControllerFrame | None:
        """Suspend capture on focus loss and neutralize immediately."""
        self._focused = False
        if not self.is_captured:
            return None
        return self._leave_capture(AppState.SUSPENDED)

    def on_focus_gained(self) -> None:
        """Return a suspended application to idle without recapturing."""
        self._focused = True
        if self._app_state is AppState.SUSPENDED:
            self._app_state = AppState.IDLE

    def begin_shutdown(self) -> ControllerFrame | None:
        """Neutralize input and reject further capture transitions once.

        Returns:
            A capture-inactive neutral frame on the first shutdown request, or
            ``None`` after shutdown has already started.
        """
        if self._app_state in {AppState.SHUTTING_DOWN, AppState.STOPPED}:
            return None
        self._app_state = AppState.SHUTTING_DOWN
        self._capture_epoch += 1
        with suppress(OSError, RuntimeError):
            self._pointer_capture.set_pointer_capture(False)
        self._publisher.state.clear()
        return self._publish_frame(capture_active=False)

    def finish_shutdown(self) -> None:
        """Mark a completed shutdown after all outer resources have closed."""
        self._app_state = AppState.STOPPED

    def _leave_capture(self, next_state: AppState) -> ControllerFrame:
        self._app_state = next_state
        self._capture_epoch += 1
        with suppress(OSError, RuntimeError):
            self._pointer_capture.set_pointer_capture(False)
        self._publisher.state.clear()
        return self._publish_frame(capture_active=False)
