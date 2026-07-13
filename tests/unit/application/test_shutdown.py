"""Unit tests for ordered application shutdown."""

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, cast

from demi.application.shutdown import ApplicationShutdownCoordinator
from demi.domain.errors import DomainValueError
from demi.domain.settings import AppSettings, WindowSettings

if TYPE_CHECKING:
    from demi.application.coordinator import CaptureCoordinator


@dataclass
class FakeCapture:
    """Capture boundary that records shutdown transitions."""

    timeline: list[str]

    def begin_shutdown(self) -> None:
        """Record neutralization before worker shutdown."""
        self.timeline.append("capture.begin_shutdown")

    def finish_shutdown(self) -> None:
        """Record the terminal capture transition."""
        self.timeline.append("capture.finish_shutdown")


@dataclass
class FakeRuntime:
    """Runtime boundary that can fail while closing."""

    timeline: list[str]
    close_error: Exception | None = None

    def close(self) -> None:
        """Record the worker close request and optionally fail."""
        self.timeline.append("runtime.close")
        if self.close_error is not None:
            raise self.close_error


@dataclass
class FakeRepository:
    """Settings persistence boundary that records saved snapshots."""

    timeline: list[str]
    saved: list[AppSettings] = field(default_factory=list)

    def save(self, settings: AppSettings) -> None:
        """Record one persisted settings snapshot."""
        self.timeline.append("repository.save")
        self.saved.append(settings)


def test_shutdown_orders_neutral_runtime_persistence_and_completion() -> None:
    timeline: list[str] = []
    settings = AppSettings.default()
    snapshot = WindowSettings(width=1200, height=800, maximized=True)
    capture = FakeCapture(timeline)
    runtime = FakeRuntime(timeline)
    repository = FakeRepository(timeline)
    shutdown = ApplicationShutdownCoordinator(
        capture=cast("CaptureCoordinator", capture),
        runtime=runtime,
        repository=repository,
        settings_provider=lambda: settings,
        window_state_provider=lambda: None,
    )

    assert shutdown.request(snapshot) is True

    assert timeline == [
        "capture.begin_shutdown",
        "runtime.close",
        "repository.save",
        "capture.finish_shutdown",
    ]
    assert repository.saved == [replace(settings, window=snapshot)]
    assert shutdown.requested is True


def test_shutdown_ignores_a_duplicate_request() -> None:
    timeline: list[str] = []
    settings = AppSettings.default()
    first_snapshot = WindowSettings(width=1200, height=800)
    capture = FakeCapture(timeline)
    runtime = FakeRuntime(timeline)
    repository = FakeRepository(timeline)
    shutdown = ApplicationShutdownCoordinator(
        capture=cast("CaptureCoordinator", capture),
        runtime=runtime,
        repository=repository,
        settings_provider=lambda: settings,
        window_state_provider=lambda: None,
    )

    assert shutdown.request(first_snapshot) is True
    assert shutdown.request(WindowSettings(width=1400, height=900)) is False

    assert timeline == [
        "capture.begin_shutdown",
        "runtime.close",
        "repository.save",
        "capture.finish_shutdown",
    ]
    assert repository.saved == [replace(settings, window=first_snapshot)]


def test_shutdown_skips_persistence_when_window_state_is_none() -> None:
    timeline: list[str] = []
    capture = FakeCapture(timeline)
    runtime = FakeRuntime(timeline)
    repository = FakeRepository(timeline)
    shutdown = ApplicationShutdownCoordinator(
        capture=cast("CaptureCoordinator", capture),
        runtime=runtime,
        repository=repository,
        settings_provider=AppSettings.default,
        window_state_provider=lambda: None,
    )

    assert shutdown.request() is True

    assert timeline == [
        "capture.begin_shutdown",
        "runtime.close",
        "capture.finish_shutdown",
    ]
    assert repository.saved == []


def test_shutdown_skips_persistence_when_window_state_capture_is_invalid() -> None:
    timeline: list[str] = []
    reports: list[tuple[str, Exception]] = []
    capture = FakeCapture(timeline)
    runtime = FakeRuntime(timeline)
    repository = FakeRepository(timeline)

    def invalid_window_state() -> WindowSettings | None:
        """Model a window geometry that cannot produce a valid domain value."""
        raise DomainValueError

    shutdown = ApplicationShutdownCoordinator(
        capture=cast("CaptureCoordinator", capture),
        runtime=runtime,
        repository=repository,
        settings_provider=AppSettings.default,
        window_state_provider=invalid_window_state,
        report_error=lambda stage, error: reports.append((stage, error)),
    )

    assert shutdown.request() is True

    assert timeline == [
        "capture.begin_shutdown",
        "runtime.close",
        "capture.finish_shutdown",
    ]
    assert repository.saved == []
    assert [stage for stage, _ in reports] == ["window state capture"]
    assert isinstance(reports[0][1], DomainValueError)


def test_shutdown_persists_and_finishes_after_runtime_close_failure() -> None:
    timeline: list[str] = []
    reports: list[tuple[str, Exception]] = []
    settings = AppSettings.default()
    snapshot = WindowSettings(width=1200, height=800)
    capture = FakeCapture(timeline)
    runtime_error = RuntimeError()
    runtime = FakeRuntime(timeline, close_error=runtime_error)
    repository = FakeRepository(timeline)
    shutdown = ApplicationShutdownCoordinator(
        capture=cast("CaptureCoordinator", capture),
        runtime=runtime,
        repository=repository,
        settings_provider=lambda: settings,
        window_state_provider=lambda: None,
        report_error=lambda stage, error: reports.append((stage, error)),
    )

    assert shutdown.request(snapshot) is True

    assert timeline == [
        "capture.begin_shutdown",
        "runtime.close",
        "repository.save",
        "capture.finish_shutdown",
    ]
    assert repository.saved == [replace(settings, window=snapshot)]
    assert reports == [("runtime shutdown", runtime_error)]
