"""Qt application lifecycle boundary."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QApplication

from demi.ui.main_window import MainWindow

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from demi.app import WindowPort, WindowSpec
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
        return self._application.exec()

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
