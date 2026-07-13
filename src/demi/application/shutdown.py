"""Idempotent ordered shutdown for the desktop application boundary."""

from collections.abc import Callable
from dataclasses import replace
from typing import Protocol

from demi.domain.settings import AppSettings, WindowSettings

from .coordinator import CaptureCoordinator


class RuntimeCloser(Protocol):
    """Runtime operation needed during application shutdown."""

    def close(self) -> None:
        """Stop the worker and join its owned thread."""


class SettingsSaver(Protocol):
    """Persistence operation needed to retain valid window state."""

    def save(self, settings: AppSettings) -> None:
        """Persist one validated settings snapshot."""


type ErrorReporter = Callable[[str, Exception], None]
type SettingsProvider = Callable[[], AppSettings]
type WindowStateProvider = Callable[[], WindowSettings | None]


class ApplicationShutdownCoordinator:
    """Run neutralization, worker close, and state persistence exactly once."""

    def __init__(
        self,
        *,
        capture: CaptureCoordinator,
        runtime: RuntimeCloser,
        repository: SettingsSaver,
        settings_provider: SettingsProvider,
        window_state_provider: WindowStateProvider,
        report_error: ErrorReporter | None = None,
    ) -> None:
        """Store outer boundaries without starting shutdown work."""
        self._capture = capture
        self._runtime = runtime
        self._repository = repository
        self._settings_provider = settings_provider
        self._window_state_provider = window_state_provider
        self._report_error = report_error
        self._requested = False
        self._failed = False

    @property
    def requested(self) -> bool:
        """Return whether the ordered shutdown has already been requested."""
        return self._requested

    @property
    def failed(self) -> bool:
        """Return whether any best-effort shutdown stage reported an error."""
        return self._failed

    def request(self, window_state: WindowSettings | None = None) -> bool:
        """Perform best-effort ordered shutdown only on the first request.

        Args:
            window_state: Optional state captured by the GUI before its native
                close handler destroys the window.  When omitted, this
                coordinator obtains the state from its provider.

        Returns:
            ``True`` only for the request that performed shutdown work.
        """
        if self._requested:
            return False
        self._requested = True

        try:
            self._capture.begin_shutdown()
        except Exception as error:  # noqa: BLE001 - continue worker shutdown.
            self._report("input neutralization", error)

        snapshot = window_state
        if snapshot is None:
            try:
                snapshot = self._window_state_provider()
            except Exception as error:  # noqa: BLE001 - no invalid state save.
                self._report("window state capture", error)

        try:
            self._runtime.close()
        except Exception as error:  # noqa: BLE001 - persistence still matters.
            self._report("runtime shutdown", error)

        if snapshot is not None:
            try:
                self._repository.save(replace(self._settings_provider(), window=snapshot))
            except Exception as error:  # noqa: BLE001 - completion remains idempotent.
                self._report("window state persistence", error)

        try:
            self._capture.finish_shutdown()
        except Exception as error:  # noqa: BLE001 - all outer cleanup was attempted.
            self._report("input shutdown completion", error)
        return True

    def _report(self, stage: str, error: Exception) -> None:
        self._failed = True
        reporter = self._report_error
        if reporter is not None:
            reporter(stage, error)
