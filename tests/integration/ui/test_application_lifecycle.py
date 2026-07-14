from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer
from PySide6.QtGui import QCloseEvent

from demi.app import ApplicationDependencies, SystemClock, WindowSpec, run_application
from demi.application.shutdown import ApplicationShutdownCoordinator
from demi.application.state import ConnectionState
from demi.config.paths import SettingsPaths
from demi.config.repository import SettingsLoadResult, SettingsLoadStatus
from demi.controller.commands import ConnectSaved, DiscoverAdapters, StartPairing
from demi.controller.events import (
    AdapterDescriptor,
    AdaptersDiscovered,
    ConnectionChanged,
    ControllerError,
    ControllerErrorCategory,
)
from demi.domain.settings import AppSettings, WindowSettings
from demi.ui.application import QtApplicationRunner

if TYPE_CHECKING:
    from collections.abc import Callable

    from PySide6.QtWidgets import QApplication

    from demi.app import RuntimePort
    from demi.controller.adapter import ControllerAdapterFactory, RuntimeEventSink
    from demi.controller.commands import ControllerCommand
    from demi.controller.events import RuntimeEvent
    from demi.controller.watchdog import WatchdogClock
    from demi.domain.controller import ControllerFrame
    from demi.ui.main_window import MainWindow


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


@dataclass
class ShellRuntime:
    """Runtime fake sufficient for a first empty Qt shell."""

    started: int = 0
    closed: int = 0
    commands: list[ControllerCommand] = field(default_factory=list)

    def start(self) -> None:
        """Record worker startup."""
        self.started += 1

    def post(self, command: ControllerCommand) -> None:
        """Record an ordered runtime command."""
        self.commands.append(command)

    def offer_frame(self, frame: ControllerFrame) -> bool:
        """Accept an initial neutral frame without a real worker."""
        del frame
        return True

    def close(self) -> None:
        """Record worker shutdown."""
        self.closed += 1


@dataclass
class StartupEventRuntime(ShellRuntime):
    """Runtime fake that emits its startup events through the production sink."""

    startup_events: tuple[RuntimeEvent, ...] = ()
    event_sink: RuntimeEventSink | None = None

    def start(self) -> None:
        """Record startup and emit deterministic worker events."""
        super().start()
        sink = self.event_sink
        if sink is None:
            raise RuntimeError
        for event in self.startup_events:
            sink.emit(event)


@dataclass
class ShellRepository:
    """Settings fake sufficient for a first empty Qt shell."""

    loaded: SettingsLoadResult
    saved: list[AppSettings] = field(default_factory=list)

    def load(self) -> SettingsLoadResult:
        """Return the selected first-run settings."""
        return self.loaded

    def save(self, settings: AppSettings) -> None:
        """Record one saved settings snapshot."""
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


def test_application_runner_starts_an_empty_qt_shell_and_returns_zero(
    qt_application: object,
) -> None:
    settings = AppSettings.default()
    repository = ShellRepository(SettingsLoadResult(settings, SettingsLoadStatus.FIRST_RUN))
    runtime = ShellRuntime()
    runner = QtApplicationRunner()
    paths = SettingsPaths(Path("config"), Path("data"), Path("log"))

    def create_gui(
        *,
        window: MainWindow,
        on_shutdown_requested: Callable[[WindowSettings | None], bool],
        **_kwargs: object,
    ) -> QtApplicationRunner:
        runner.configure(window=window, on_shutdown_requested=on_shutdown_requested)
        QTimer.singleShot(0, window.close)
        return runner

    def create_runtime(
        *,
        adapter_factory: ControllerAdapterFactory,
        event_sink: RuntimeEventSink,
        clock: WatchdogClock,
    ) -> RuntimePort:
        del adapter_factory, event_sink, clock
        return runtime

    dependencies = ApplicationDependencies(
        paths_resolver=lambda: paths,
        repository_factory=lambda _paths: repository,
        runtime_factory=create_runtime,
        window_factory=runner.create_main_window,
        gui_factory=create_gui,
        clock=SystemClock(),
        logger_configurer=lambda _paths, _level: logging.getLogger("demi-test-qt-shell"),
    )

    assert run_application(dependencies) == 0
    assert runner.application is qt_application
    assert runtime.started == 1
    assert runtime.commands == [DiscoverAdapters()]
    assert runtime.closed == 1
    assert repository.saved == [replace(settings, window=WindowSettings(width=960, height=640))]


def test_qt_startup_without_saved_settings_or_adapters_keeps_window_interactive(
    qt_application: QApplication,
) -> None:
    assert qt_application is not None
    settings = AppSettings.default()
    repository = ShellRepository(SettingsLoadResult(settings, SettingsLoadStatus.FIRST_RUN))
    runtime = StartupEventRuntime(
        startup_events=(AdaptersDiscovered(()), ConnectionChanged(ConnectionState.READY)),
    )
    runner = QtApplicationRunner()
    paths = SettingsPaths(Path("config"), Path("data"), Path("log"))
    observed: list[tuple[bool, bool, str]] = []

    def create_gui(
        *,
        window: MainWindow,
        on_shutdown_requested: Callable[[WindowSettings | None], bool],
        **_kwargs: object,
    ) -> QtApplicationRunner:
        runner.configure(window=window, on_shutdown_requested=on_shutdown_requested)

        def observe_and_close() -> None:
            observed.append(
                (
                    window.main_toolbar.mapping_action.isEnabled(),
                    window.main_toolbar.connection_settings_action.isEnabled(),
                    window.status_bar.notice_label.text(),
                )
            )
            window.close()

        QTimer.singleShot(0, observe_and_close)
        return runner

    def create_runtime(
        *,
        adapter_factory: ControllerAdapterFactory,
        event_sink: RuntimeEventSink,
        clock: WatchdogClock,
    ) -> RuntimePort:
        del adapter_factory, clock
        runtime.event_sink = event_sink
        return runtime

    dependencies = ApplicationDependencies(
        paths_resolver=lambda: paths,
        repository_factory=lambda _paths: repository,
        runtime_factory=create_runtime,
        window_factory=runner.create_main_window,
        gui_factory=create_gui,
        clock=SystemClock(),
        logger_configurer=lambda _paths, _level: logging.getLogger("demi-test-qt-first-run"),
    )

    assert run_application(dependencies) == 0
    assert runner.application is qt_application
    assert runtime.started == 1
    assert runtime.commands == [DiscoverAdapters()]
    assert observed == [(True, True, "通知: なし")]


def test_qt_reconnect_failure_keeps_window_interactive_and_safe(
    qt_application: QApplication,
) -> None:
    assert qt_application is not None
    settings = replace(
        AppSettings.default(),
        connection=replace(
            AppSettings.default().connection,
            adapter_id="usb:0",
            reconnect_on_start=True,
        ),
    )
    repository = ShellRepository(SettingsLoadResult(settings, SettingsLoadStatus.LOADED))
    runtime = StartupEventRuntime(
        startup_events=(
            AdaptersDiscovered((AdapterDescriptor("usb:0", "USB Adapter", "usb"),)),
            ConnectionChanged(ConnectionState.READY),
            ControllerError(
                category=ControllerErrorCategory.RECONNECT_FAILED,
                summary="bond=/private/secret.json",
                retryable=True,
                diagnostic_id="test-0001",
            ),
        ),
    )
    runner = QtApplicationRunner()
    paths = SettingsPaths(Path("config"), Path("data"), Path("log"))
    observed: list[tuple[bool, bool, str]] = []

    def create_gui(
        *,
        window: MainWindow,
        on_shutdown_requested: Callable[[WindowSettings | None], bool],
        **_kwargs: object,
    ) -> QtApplicationRunner:
        runner.configure(window=window, on_shutdown_requested=on_shutdown_requested)

        def observe_and_close() -> None:
            observed.append(
                (
                    window.main_toolbar.connection_action.isEnabled(),
                    window.main_toolbar.connection_settings_action.isEnabled(),
                    window.status_bar.notice_label.text(),
                )
            )
            window.close()

        QTimer.singleShot(0, observe_and_close)
        return runner

    def create_runtime(
        *,
        adapter_factory: ControllerAdapterFactory,
        event_sink: RuntimeEventSink,
        clock: WatchdogClock,
    ) -> RuntimePort:
        del adapter_factory, clock
        runtime.event_sink = event_sink
        return runtime

    dependencies = ApplicationDependencies(
        paths_resolver=lambda: paths,
        repository_factory=lambda _paths: repository,
        runtime_factory=create_runtime,
        window_factory=runner.create_main_window,
        gui_factory=create_gui,
        clock=SystemClock(),
        logger_configurer=lambda _paths, _level: logging.getLogger(
            "demi-test-qt-reconnect-failure"
        ),
    )

    assert run_application(dependencies) == 0
    assert runtime.started == 1
    assert [command for command in runtime.commands if isinstance(command, ConnectSaved)]
    assert not any(isinstance(command, StartPairing) for command in runtime.commands)
    assert observed == [(True, True, "エラー: 保存済み接続に失敗しました")]
