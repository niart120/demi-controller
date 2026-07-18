"""Capture PySide6 widget states from a task-local scenario."""

# ruff: noqa: TRY003 - CLI errors include the rejected scenario or output path.

import argparse
import re
import runpy
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, cast

from PySide6.QtCore import QCoreApplication, QEvent, QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QWidget

_FRAME_NAME = re.compile(r"[a-z0-9][a-z0-9_-]*\Z")


class CaptureContext:
    """Settle Qt events and save ordered widget images for one scenario."""

    def __init__(self, application: QApplication, output_dir: Path) -> None:
        """Create one capture run in a PNG-free output directory."""
        if output_dir.exists() and any(output_dir.glob("*.png")):
            raise FileExistsError(f"output directory already contains PNG files: {output_dir}")
        output_dir.mkdir(parents=True, exist_ok=True)
        self._application = application
        self._output_dir = output_dir
        self._paths: list[Path] = []
        self._names: set[str] = set()

    @property
    def application(self) -> QApplication:
        """Return the process-wide Qt application."""
        return self._application

    @property
    def paths(self) -> tuple[Path, ...]:
        """Return PNG paths in capture order."""
        return tuple(self._paths)

    def settle(self) -> None:
        """Process one queued Qt event-loop turn."""
        event_loop = QEventLoop()
        QTimer.singleShot(0, event_loop.quit)
        event_loop.exec()
        self._application.processEvents()

    def frame(self, name: str, widget: QWidget) -> Path:
        """Show one widget and save its rendered client area as an ordered PNG."""
        if not _FRAME_NAME.fullmatch(name):
            raise ValueError("frame name must match [a-z0-9][a-z0-9_-]*")
        if name in self._names:
            raise ValueError(f"duplicate frame name: {name}")
        if not isinstance(widget, QWidget):
            raise TypeError("frame widget must be a QWidget")

        widget.show()
        self.settle()
        pixmap = widget.grab()
        if pixmap.isNull():
            raise RuntimeError(f"captured a null pixmap: {name}")

        path = self._output_dir / f"{len(self._paths):02d}-{name}.png"
        if path.exists():
            raise FileExistsError(f"capture path already exists: {path}")
        if not pixmap.save(str(path), "PNG"):
            raise OSError(f"failed to save capture: {path}")

        self._names.add(name)
        self._paths.append(path)
        print(path.resolve())  # noqa: T201 - CLI reports each generated artifact.
        return path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture ordered PySide6 widget images from a Python scenario."
    )
    parser.add_argument("--scenario", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def _load_scenario(path: Path) -> Callable[[CaptureContext], None]:
    if not path.is_file():
        raise FileNotFoundError(f"scenario file does not exist: {path}")
    namespace = runpy.run_path(str(path))
    candidate: Any = namespace.get("run")
    if not callable(candidate):
        raise TypeError("scenario must define callable run(capture)")
    return cast("Callable[[CaptureContext], None]", candidate)


def _application() -> QApplication:
    existing = QApplication.instance()
    if existing is None:
        return QApplication([])
    if not isinstance(existing, QApplication):
        raise TypeError("a non-GUI QCoreApplication already exists")
    return existing


def _dispose_widgets(application: QApplication) -> None:
    for widget in reversed(application.topLevelWidgets()):
        widget.hide()
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    application.processEvents()


def main(argv: Sequence[str] | None = None) -> int:
    """Run one scenario and require at least one captured frame."""
    args = _parser().parse_args(argv)
    application = _application()
    if application.platformName().casefold() != "windows":
        raise RuntimeError(
            "native Windows Qt rendering is required; unset QT_QPA_PLATFORM and retry"
        )

    capture = CaptureContext(application, args.output)
    scenario = _load_scenario(args.scenario)
    try:
        scenario(capture)
        if not capture.paths:
            raise RuntimeError("scenario completed without capturing a frame")
        return 0
    finally:
        _dispose_widgets(application)


if __name__ == "__main__":
    raise SystemExit(main())
