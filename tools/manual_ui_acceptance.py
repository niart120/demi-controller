"""Launch a Windows-only probe for unit_015's Raw Input acceptance checks.

The probe composes the production ``MainWindow``, ``CaptureCoordinator``,
``InputPublisher``, and ``WindowsRawInputBackend``.  It deliberately keeps
the toolbar, dialog, and on-screen counters outside the distributable UI so
unit_016 remains the owner of the production controls.
"""

from __future__ import annotations

import sys
import time
from argparse import ArgumentParser
from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolBar,
    QVBoxLayout,
)

from demi.app import WindowSpec
from demi.application.coordinator import CaptureCoordinator
from demi.input.publisher import InputPublisher
from demi.platform.windows_raw_input import WindowsRawInputBackend
from demi.ui.main_window import MainWindow

if TYPE_CHECKING:
    from argparse import Namespace

    from demi.application.coordinator import CaptureFailure
    from demi.domain.controller import ControllerFrame


@dataclass(slots=True)
class _ProbeCounters:
    """Keep manual acceptance measurements outside the production UI."""

    raw_packet_count: int = 0
    raw_dx: float = 0.0
    raw_dy: float = 0.0
    frame_count: int = 0
    last_frame_ns: int | None = None
    last_frame_interval_ms: float | None = None
    maximum_frame_interval_ms: float = 0.0
    capture_failure: CaptureFailure | None = None

    def record_raw_motion(self, dx: float, dy: float) -> None:
        """Record one decoded Raw Input packet before input evaluation."""
        self.raw_packet_count += 1
        self.raw_dx += dx
        self.raw_dy += dy

    def record_frame(self, frame: ControllerFrame) -> None:
        """Record one evaluated frame and its preceding observed interval."""
        previous_ns = self.last_frame_ns
        if previous_ns is not None:
            interval_ms = (frame.monotonic_ns - previous_ns) / 1_000_000.0
            self.last_frame_interval_ms = interval_ms
            self.maximum_frame_interval_ms = max(self.maximum_frame_interval_ms, interval_ms)
        self.last_frame_ns = frame.monotonic_ns
        self.frame_count += 1


class _SystemClock:
    """Provide the monotonic clock required by ``InputPublisher``."""

    def monotonic_ns(self) -> int:
        """Return the current monotonic timestamp in nanoseconds."""
        return time.monotonic_ns()


class _FrameObserver:
    """Forward each evaluated frame to the preview and acceptance counters."""

    def __init__(self, *, window: MainWindow, counters: _ProbeCounters) -> None:
        """Create the manual probe's frame destination.

        Args:
            window: Production window that renders the shared frame.
            counters: Mutable acceptance observations.
        """
        self._window = window
        self._counters = counters

    def offer_frame(self, frame: ControllerFrame) -> None:
        """Render and record the same frame without creating a second evaluation."""
        self._window.set_frame(frame)
        self._counters.record_frame(frame)


def _parse_arguments() -> Namespace:
    """Parse the optional automatic-close interval for this manual probe."""
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=0,
        help="0なら自動終了せず、正の値なら指定秒数で閉じます。",
    )
    arguments = parser.parse_args()
    if arguments.timeout_seconds < 0:
        parser.error("--timeout-seconds は 0 以上で指定してください。")
    return arguments


def _format_status(
    *,
    coordinator: CaptureCoordinator,
    counters: _ProbeCounters,
    backend: WindowsRawInputBackend,
) -> str:
    """Format only measured probe values for the status bar."""
    latest_interval = (
        "未計測"
        if counters.last_frame_interval_ms is None
        else f"{counters.last_frame_interval_ms:.1f} ms"
    )
    failure = "なし" if counters.capture_failure is None else counters.capture_failure.value
    return (
        f"状態: {coordinator.app_state.value} | "
        f"Raw: {backend.capability.quality.value} | "
        f"packet: {counters.raw_packet_count} | "
        f"delta: ({counters.raw_dx:.0f}, {counters.raw_dy:.0f}) | "
        f"frame: {counters.frame_count} | "
        f"間隔: {latest_interval} / 最大 {counters.maximum_frame_interval_ms:.1f} ms | "
        f"読出し失敗: {failure}"
    )


def _open_dialog(window: MainWindow, coordinator: CaptureCoordinator) -> None:
    """Open a standard Qt dialog after the production neutralization boundary."""
    window.on_dialog_opened()
    dialog = QDialog(window)
    dialog.setWindowTitle("Qt ダイアログ確認")
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel("ここに文字を入力し、閉じる操作が届くことを確認します。"))
    line_edit = QLineEdit(dialog)
    line_edit.setPlaceholderText("Qt の通常入力")
    layout.addWidget(line_edit)
    close_button = QPushButton("閉じる", dialog)
    close_button.clicked.connect(dialog.accept)
    layout.addWidget(close_button)
    dialog.exec()
    coordinator.close_configuration()


def _run() -> int:
    """Run the interactive Windows acceptance probe."""
    arguments = _parse_arguments()
    if sys.platform != "win32":
        sys.stderr.write("この手動受入ランチャーは Windows 専用です。\n")
        return 2

    application = QApplication(sys.argv[:1])
    window = MainWindow(WindowSpec(width=1000, height=680, maximized=False))
    window.setWindowTitle("Project_Demi unit_015 Raw Input 手動受入")
    counters = _ProbeCounters()
    observer = _FrameObserver(window=window, counters=counters)
    publisher = InputPublisher(clock=_SystemClock(), sink=observer)
    coordinator_holder: dict[str, CaptureCoordinator] = {}

    def on_relative_motion(dx: float, dy: float) -> None:
        """Count the decoded packet and pass it to the production input state."""
        counters.record_raw_motion(dx, dy)
        publisher.state.add_mouse_motion(dx, dy)

    def on_read_failure() -> None:
        """Use the production capture failure transition after repeated reads fail."""
        coordinator_holder["coordinator"].on_relative_input_read_failure()

    def on_capture_failure(failure: CaptureFailure) -> None:
        """Expose only the safe failure category in the manual probe."""
        counters.capture_failure = failure

    backend = WindowsRawInputBackend(
        on_relative_motion=on_relative_motion,
        on_read_failure=on_read_failure,
    )
    coordinator = CaptureCoordinator(
        publisher=publisher,
        pointer_capture=window,
        relative_pointer_capture=window,
        on_capture_failure=on_capture_failure,
    )
    coordinator_holder["coordinator"] = coordinator
    window.configure_input(
        publisher=publisher,
        coordinator=coordinator,
        raw_input_backend=backend,
    )

    toolbar = QToolBar("手動受入", window)
    window.addToolBar(toolbar)
    capture_action = toolbar.addAction("入力開始 / 解除")
    capture_action.triggered.connect(lambda _checked=False: coordinator.toggle_capture())
    dialog_action = toolbar.addAction("ダイアログ確認")
    dialog_action.triggered.connect(lambda _checked=False: _open_dialog(window, coordinator))

    def update_status() -> None:
        """Refresh the visual measurement summary without altering input state."""
        window.statusBar().showMessage(
            _format_status(
                coordinator=coordinator,
                counters=counters,
                backend=backend,
            )
        )

    def request_shutdown(_: object) -> bool:
        """Stop capture before the manual window is allowed to close."""
        coordinator.begin_shutdown()
        coordinator.finish_shutdown()
        return True

    window.set_shutdown_callback(request_shutdown)
    status_timer = QTimer(window)
    status_timer.setInterval(100)
    status_timer.timeout.connect(update_status)
    status_timer.start()
    if arguments.timeout_seconds:
        QTimer.singleShot(arguments.timeout_seconds * 1_000, window.close)
    window.show()
    update_status()
    exit_status = application.exec()
    sys.stdout.write(
        _format_status(
            coordinator=coordinator,
            counters=counters,
            backend=backend,
        )
        + "\n"
    )
    return exit_status


if __name__ == "__main__":
    raise SystemExit(_run())
