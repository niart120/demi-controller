"""Qt application lifecycle boundary."""

import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication


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
