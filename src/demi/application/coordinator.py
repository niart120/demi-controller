"""Main-thread capture lifecycle coordination."""

from contextlib import suppress
from typing import Protocol

from demi.domain.controller import ControllerFrame
from demi.input.publisher import InputPublisher

from .state import AppState


class WindowPort(Protocol):
    """Window operation required by capture lifecycle transitions."""

    def set_exclusive_mouse(self, exclusive: bool = True) -> None:
        """Enable or disable relative mouse capture."""


class CaptureCoordinator:
    """Own capture state, epoch changes, and neutral frame transitions."""

    def __init__(self, *, publisher: InputPublisher, window: WindowPort) -> None:
        """Initialize a coordinator in the focused idle state."""
        self._publisher = publisher
        self._window = window
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
            self._window.set_exclusive_mouse(True)
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

    def _leave_capture(self, next_state: AppState) -> ControllerFrame:
        self._app_state = next_state
        self._capture_epoch += 1
        with suppress(OSError, RuntimeError):
            self._window.set_exclusive_mouse(False)
        self._publisher.state.clear()
        return self._publish_frame(capture_active=False)
