from dataclasses import dataclass, field, replace

from PySide6.QtGui import QCloseEvent

from demi.app import WindowSpec
from demi.application.shutdown import ApplicationShutdownCoordinator
from demi.domain.settings import AppSettings, WindowSettings
from demi.ui.application import QtApplicationRunner


@dataclass
class FakeCapture:
    """Capture boundary that records ordered shutdown calls."""

    timeline: list[str]

    def begin_shutdown(self) -> None:
        """Record neutralization before runtime shutdown."""
        self.timeline.append("capture.begin_shutdown")

    def finish_shutdown(self) -> None:
        """Record completion after persistence."""
        self.timeline.append("capture.finish_shutdown")


@dataclass
class FakeRuntime:
    """Runtime boundary that records close requests."""

    timeline: list[str]

    def close(self) -> None:
        """Record worker shutdown."""
        self.timeline.append("runtime.close")


@dataclass
class FakeRepository:
    """Settings boundary that records persisted snapshots."""

    timeline: list[str]
    saved: list[AppSettings] = field(default_factory=list)

    def save(self, settings: AppSettings) -> None:
        """Record one saved settings snapshot."""
        self.timeline.append("repository.save")
        self.saved.append(settings)


def test_qt_quit_runs_ordered_shutdown_once(qt_application: object) -> None:
    timeline: list[str] = []
    settings = AppSettings.default()
    capture = FakeCapture(timeline)
    runtime = FakeRuntime(timeline)
    repository = FakeRepository(timeline)
    shutdown = ApplicationShutdownCoordinator(
        capture=capture,
        runtime=runtime,
        repository=repository,
        settings_provider=lambda: settings,
        window_state_provider=lambda: None,
    )
    runner = QtApplicationRunner()
    window = runner.create_main_window(WindowSpec(width=1200, height=800, maximized=False))

    def request_shutdown(state: WindowSettings | None) -> bool:
        shutdown.request(state)
        return not shutdown.failed

    window.set_shutdown_callback(request_shutdown)

    window.quit_action.trigger()
    duplicate_event = QCloseEvent()
    duplicate_event.ignore()
    window.closeEvent(duplicate_event)

    assert runner.application is qt_application
    assert timeline == [
        "capture.begin_shutdown",
        "runtime.close",
        "repository.save",
        "capture.finish_shutdown",
    ]
    assert repository.saved == [
        replace(settings, window=WindowSettings(width=1200, height=800, maximized=False))
    ]
    assert duplicate_event.isAccepted() is True
