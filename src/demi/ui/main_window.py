"""Minimal Qt main window used by the application shell."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMainWindow, QWidget

from demi.domain.errors import DomainValueError
from demi.domain.settings import WindowSettings

if TYPE_CHECKING:
    from PySide6.QtGui import QCloseEvent

    from demi.app import WindowSpec


type ShutdownCallback = Callable[[WindowSettings | None], bool]


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
        self._shutdown_callback: ShutdownCallback | None = None
        self._close_accepted = False
        self._quit_action = QAction(self)
        self._quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self._quit_action.triggered.connect(self.close)
        self.addAction(self._quit_action)
        if spec.maximized:
            self.showMaximized()

    @property
    def quit_action(self) -> QAction:
        """Return the standard Ctrl+Q action routed through closeEvent."""
        return self._quit_action

    def set_shutdown_callback(self, callback: ShutdownCallback) -> None:
        """Set the application-owned callback required before native close.

        Args:
            callback: Receives the state captured before the native window is
                destroyed and returns whether native close is safe.
        """
        self._shutdown_callback = callback

    def set_exclusive_mouse(self, exclusive: bool = True) -> None:
        """Accept capture requests until unit_015 supplies a Qt adapter.

        Args:
            exclusive: Requested capture state. The minimal shell does not yet
                alter pointer capture.
        """
        del exclusive

    def window_state(self) -> WindowSettings | None:
        """Return a valid saved state without losing a maximized normal size."""
        size = self.normalGeometry().size() if self.isMaximized() else self.size()
        try:
            return WindowSettings(
                width=size.width(),
                height=size.height(),
                maximized=self.isMaximized(),
            )
        except DomainValueError:
            return None

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt override name.
        """Route native close and Ctrl+Q through one ordered callback."""
        if self._close_accepted:
            event.accept()
            return
        callback = self._shutdown_callback
        if callback is None:
            event.ignore()
            return
        if callback(self.window_state()):
            self._close_accepted = True
            event.accept()
            return
        event.ignore()
