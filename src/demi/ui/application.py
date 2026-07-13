"""Qt application lifecycle boundary."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QApplication

if TYPE_CHECKING:
    from collections.abc import Sequence

    from demi.app import WindowSpec
    from demi.ui.main_window import MainWindow


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

    @property
    def application(self) -> QApplication:
        """Return the process-wide QApplication owned or reused by this runner."""
        return self._application

    def run(self) -> int:
        """Enter the Qt event loop and return its exit status."""
        return self._application.exec()

    def create_main_window(self, spec: WindowSpec) -> MainWindow:
        """Create the process main window after QApplication exists.

        Args:
            spec: Validated saved dimensions selected by the application layer.
        """
        from demi.ui.main_window import (  # noqa: PLC0415 - GUI起動時だけwidgetをimportする。
            MainWindow,
        )

        return MainWindow(spec)
