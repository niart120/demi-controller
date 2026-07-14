"""Qt application lifecycle boundary."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from demi.controller.events import RuntimeStopped
from demi.ui.main_window import MainWindow

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from demi.app import ApplicationSession, WindowPort, WindowSpec
    from demi.controller.events import RuntimeEvent
    from demi.domain.settings import WindowSettings


class QtApplicationRunner:
    """Own one process-wide QApplication and its event-loop status."""

    def __init__(self, argv: Sequence[str] | None = None) -> None:
        """Create or reuse the process-wide Qt application.

        Args:
            argv: Arguments supplied to a newly created QApplication. The
                process arguments are used when omitted.
        """
        existing = QApplication.instance()
        self._application = (
            existing
            if isinstance(existing, QApplication)
            else QApplication(list(sys.argv if argv is None else argv))
        )
        self._window: MainWindow | None = None

    @property
    def application(self) -> QApplication:
        """Return the process-wide QApplication owned or reused by this runner."""
        return self._application

    def run(self) -> int:
        """Enter the Qt event loop and return its exit status."""
        window = self._window
        if window is None:
            raise RuntimeError
        window.show()
        try:
            return self._application.exec()
        finally:
            self._dispose_window(window)

    def _dispose_window(self, window: MainWindow) -> None:
        """Delete the runner-owned top-level window on the GUI thread."""
        if window.isVisible():
            window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(window, QEvent.Type.DeferredDelete)
        self._window = None

    def configure(
        self,
        *,
        window: WindowPort,
        on_shutdown_requested: Callable[[WindowSettings | None], bool],
    ) -> None:
        """Connect the application-owned shutdown callback to one window.

        Args:
            window: The sole top-level window owned by this runner.
            on_shutdown_requested: Ordered shutdown callback that decides
                whether native close may continue.
        """
        if not isinstance(window, MainWindow):
            raise TypeError
        self._window = window
        window.set_shutdown_callback(on_shutdown_requested)

    def create_main_window(self, spec: WindowSpec) -> MainWindow:
        """Create the process main window after QApplication exists.

        Args:
            spec: Validated saved dimensions selected by the application layer.
        """
        return MainWindow(spec)


class QtApplicationEventRouter:
    """Apply queued runtime events to one session and its main window."""

    def __init__(self, window: MainWindow) -> None:
        """Create an unbound GUI-thread event receiver.

        Args:
            window: Main window updated after each reduced runtime event.
        """
        self._window = window
        self._session: ApplicationSession | None = None
        self._runtime_stopped_handler: Callable[[], object] | None = None
        self._active = True

    def bind(self, session: ApplicationSession) -> None:
        """Bind the assembled application session and render its current state.

        Args:
            session: Main-thread application state that receives runtime events.
        """
        if not self._active:
            return
        self._session = session
        self.refresh()

    def deactivate(self) -> None:
        """Drop queued runtime callbacks after application shutdown begins."""
        self._active = False
        self._session = None
        self._runtime_stopped_handler = None

    def set_runtime_stopped_handler(self, handler: Callable[[], object] | None) -> None:
        """Set the application-owned completion callback for RuntimeStopped.

        Args:
            handler: Callback that completes application shutdown after the
                session has rendered a runtime-stopped snapshot, or ``None``
                to leave the router passive.
        """
        if self._active:
            self._runtime_stopped_handler = handler

    def handle_runtime_event(self, event: RuntimeEvent) -> None:
        """Reduce one bridge-delivered event and refresh the main window.

        Args:
            event: Immutable runtime event delivered on the GUI thread.
        """
        if not self._active:
            return
        session = self._session
        if session is None:
            return
        session.handle_runtime_event(event)
        self.refresh()
        if isinstance(event, RuntimeStopped):
            handler = self._runtime_stopped_handler
            if handler is not None:
                handler()

    def refresh(self) -> None:
        """Render the current session snapshot when a session is bound."""
        if not self._active:
            return
        session = self._session
        if session is not None:
            self._window.refresh(session.ui_snapshot)
