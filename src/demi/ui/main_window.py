"""Minimal Qt main window used by the application shell."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMainWindow, QWidget

if TYPE_CHECKING:
    from demi.app import WindowSpec


class MainWindow(QMainWindow):
    """Own the top-level Qt window and its minimum shell layout."""

    def __init__(self, spec: WindowSpec) -> None:
        """Create a resizable main window from validated saved dimensions.

        Args:
            spec: Requested dimensions and maximized state from settings.
        """
        super().__init__()
        self.setWindowTitle("Project_Demi")
        self.setMinimumSize(800, 520)
        self.resize(max(spec.width, self.minimumWidth()), max(spec.height, self.minimumHeight()))
        self.setCentralWidget(QWidget(self))
