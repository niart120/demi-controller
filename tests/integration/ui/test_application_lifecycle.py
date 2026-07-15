from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass, field, replace
from itertools import pairwise
from pathlib import Path
from queue import Queue
from threading import Thread, get_ident
from typing import TYPE_CHECKING

import pytest
from PySide6.QtCore import Qt, QThread, QTimer
from PySide6.QtGui import QCloseEvent

from demi.app import ApplicationDependencies, SystemClock, WindowSpec, run_application
from demi.application.shutdown import ApplicationShutdownCoordinator
from demi.application.state import ConnectionState
from demi.config.paths import SettingsPaths
from demi.config.repository import SettingsLoadResult, SettingsLoadStatus
from demi.controller.commands import ConnectSaved, Disconnect, DiscoverAdapters, StartPairing
from demi.controller.events import (
    AdapterDescriptor,
    AdaptersDiscovered,
    ConnectionChanged,
    ControllerError,
    ControllerErrorCategory,
    RuntimeStopped,
)
from demi.domain.settings import AppSettings, WindowSettings
from demi.ui.application import QtApplicationRunner
from demi.ui.main_window import MainWindow

if TYPE_CHECKING:
    from collections.abc import Callable

    from PySide6.QtWidgets import QApplication

    from demi.app import ApplicationSession, RuntimePort
    from demi.application.ui_state import ApplicationUiSnapshot
    from demi.controller.adapter import ControllerAdapterFactory, RuntimeEventSink
    from demi.controller.commands import ControllerCommand
    from demi.controller.events import RuntimeEvent
    from demi.controller.watchdog import WatchdogClock
    from demi.domain.controller import ControllerFrame


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


@dataclass(frozen=True)
class TimingEvent:
    """One monotonic timestamp captured by the responsiveness probe."""

    timestamp: float
    stage: str
    detail: str


def _record_timing_event(
    events: list[TimingEvent],
    *,
    stage: str,
    detail: str,
) -> None:
    events.append(TimingEvent(time.monotonic(), stage, detail))


def _format_timing_events(events: list[TimingEvent]) -> str:
    if not events:
        return "responsiveness timing trace: no events recorded"
    origin = min(event.timestamp for event in events)
    trace = "\n".join(
        f"{event.timestamp - origin:.6f}s {event.stage}: {event.detail}"
        for event in sorted(events, key=lambda event: event.timestamp)
    )
    return f"responsiveness timing trace:\n{trace}"


@dataclass
class ShellRuntime:
    """Runtime fake sufficient for a first empty Qt shell."""

    started: int = 0
    closed: int = 0
    commands: list[ControllerCommand] = field(default_factory=list)
    frames: list[ControllerFrame] = field(default_factory=list)

    def start(self) -> None:
        """Record worker startup."""
        self.started += 1

    def post(self, command: ControllerCommand) -> None:
        """Record an ordered runtime command."""
        self.commands.append(command)

    def offer_frame(self, frame: ControllerFrame) -> bool:
        """Accept an initial neutral frame without a real worker."""
        self.frames.append(frame)
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
class SlowRuntime(ShellRuntime):
    """Runtime fake that processes delayed commands on one worker."""

    delay_seconds: float = 0.03
    event_sink: RuntimeEventSink | None = None
    workers: list[Thread] = field(default_factory=list)
    timing_events: list[TimingEvent] = field(default_factory=list)
    command_queue: Queue[ControllerCommand | None] = field(default_factory=Queue)

    def start(self) -> None:
        """Start the single delayed-command worker before accepting commands."""
        if self.workers:
            return
        super().start()
        worker = Thread(target=self._run_commands)
        self.workers.append(worker)
        worker.start()

    def post(self, command: ControllerCommand) -> None:
        """Record one command and enqueue it for the existing worker."""
        super().post(command)
        sink = self.event_sink
        if sink is None:
            raise RuntimeError
        command_name = type(command).__name__
        _record_timing_event(
            self.timing_events,
            stage="gui.runtime.post",
            detail=command_name,
        )
        self.command_queue.put(command)

    def _run_commands(self) -> None:
        """Process queued commands in order until shutdown."""
        _record_timing_event(
            self.timing_events,
            stage="worker.start",
            detail="SlowRuntime",
        )
        while (command := self.command_queue.get()) is not None:
            sink = self.event_sink
            if sink is None:
                raise RuntimeError
            command_name = type(command).__name__
            _record_timing_event(
                self.timing_events,
                stage="worker.command.begin",
                detail=command_name,
            )
            time.sleep(self.delay_seconds)
            _record_timing_event(
                self.timing_events,
                stage="worker.woke",
                detail=command_name,
            )
            if isinstance(command, DiscoverAdapters):
                self._emit_event(
                    sink,
                    AdaptersDiscovered((AdapterDescriptor("usb:0", "USB Adapter", "usb"),)),
                    "AdaptersDiscovered",
                )
                self._emit_event(
                    sink, ConnectionChanged(ConnectionState.READY), "ConnectionChanged(READY)"
                )
            elif isinstance(command, ConnectSaved):
                self._emit_event(
                    sink,
                    ConnectionChanged(ConnectionState.CONNECTED, adapter_id=command.adapter_id),
                    "ConnectionChanged(CONNECTED)",
                )
            elif isinstance(command, Disconnect):
                self._emit_event(
                    sink, ConnectionChanged(ConnectionState.READY), "ConnectionChanged(READY)"
                )

    def _emit_event(self, sink: RuntimeEventSink, event: RuntimeEvent, detail: str) -> None:
        """Send one result and record its worker-side queue boundary."""
        _record_timing_event(self.timing_events, stage="worker.emit.begin", detail=detail)
        sink.emit(event)
        _record_timing_event(self.timing_events, stage="worker.emit.end", detail=detail)

    def close(self) -> None:
        """Join all delayed workers before recording shutdown."""
        if self.workers:
            self.command_queue.put(None)
        for worker in self.workers:
            worker.join()
        super().close()


@dataclass
class RuntimeStoppedEmitter(ShellRuntime):
    """Runtime fake that emits a worker-owned RuntimeStopped event on demand."""

    event_sink: RuntimeEventSink | None = None
    workers: list[Thread] = field(default_factory=list)

    def emit_runtime_stopped_from_worker(self) -> None:
        """Emit one stopped event from a joined non-GUI worker thread."""
        sink = self.event_sink
        if sink is None:
            raise RuntimeError
        worker = Thread(target=lambda: sink.emit(RuntimeStopped()))
        self.workers.append(worker)
        worker.start()
        worker.join()

    def close(self) -> None:
        """Join event workers before recording one application close request."""
        for worker in self.workers:
            worker.join()
        super().close()


class CountingMainWindow(MainWindow):
    """Main window that records input teardown after native close acceptance."""

    def __init__(self, spec: WindowSpec) -> None:
        """Create a standard window with an input-teardown counter."""
        super().__init__(spec)
        self.input_teardown_calls = 0

    def _remove_input_filters(self) -> None:
        """Count the one input/timer cleanup before using the standard teardown."""
        self.input_teardown_calls += 1
        super()._remove_input_filters()


class TimingMainWindow(MainWindow):
    """Main window that timestamps each refresh in the responsiveness probe."""

    def __init__(self, spec: WindowSpec, *, timing_events: list[TimingEvent]) -> None:
        """Create a window that records refresh timing.

        Args:
            spec: Window dimensions used by the application composition root.
            timing_events: Shared ordered observations for the responsiveness probe.
        """
        self._timing_events = timing_events
        super().__init__(spec)

    def refresh(self, snapshot: ApplicationUiSnapshot) -> None:
        """Record refresh bounds before applying the standard rendering path."""
        detail = snapshot.connection_state.name
        _record_timing_event(self._timing_events, stage="gui.refresh.begin", detail=detail)
        super().refresh(snapshot)
        _record_timing_event(self._timing_events, stage="gui.refresh.end", detail=detail)


class ThreadTrackingMainWindow(MainWindow):
    """Main window that records its Qt lifecycle thread ownership."""

    def __init__(
        self,
        spec: WindowSpec,
        *,
        lifecycle_observations: list[tuple[str, int, bool]],
        destruction_observations: list[tuple[str, int]],
        timer_inactive_after_teardown: list[bool],
    ) -> None:
        """Create a window and retain only primitive lifecycle observations."""
        self._lifecycle_observations = lifecycle_observations
        self._timer_inactive_after_teardown = timer_inactive_after_teardown
        super().__init__(spec)
        self.destroyed.connect(
            lambda _object: destruction_observations.append(("window", get_ident()))
        )
        self._input_evaluation_timer.destroyed.connect(
            lambda _object: destruction_observations.append(("timer", get_ident()))
        )
        self._record_lifecycle("create")

    def refresh(self, snapshot: ApplicationUiSnapshot) -> None:
        """Record the caller thread before applying the standard refresh."""
        self._record_lifecycle("refresh")
        super().refresh(snapshot)

    def begin_shutdown(self) -> None:
        """Record shutdown ownership before stopping UI callbacks."""
        self._record_lifecycle("shutdown")
        super().begin_shutdown()

    def _remove_input_filters(self) -> None:
        """Record timer teardown ownership and the resulting inactive timer."""
        self._record_lifecycle("input-teardown")
        super()._remove_input_filters()
        self._timer_inactive_after_teardown.append(not self._input_evaluation_timer.isActive())

    def _record_lifecycle(self, phase: str) -> None:
        """Append the current Python and Qt thread ownership for one phase."""
        self._lifecycle_observations.append(
            (phase, get_ident(), QThread.currentThread() == self.thread())
        )


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


@dataclass
class StartupFailureWindow:
    """Window fake that records cleanup after a partial startup failure."""

    timeline: list[str]

    def set_pointer_capture(self, enabled: bool) -> None:
        """Accept capture cleanup without a native window."""
        del enabled

    def window_state(self) -> WindowSettings:
        """Return the valid state available before native closure."""
        return WindowSettings(width=960, height=640)

    def close(self) -> None:
        """Record one native window close request."""
        self.timeline.append("window.close")


@dataclass
class StartupFailureRepository:
    """Repository fake that can record persistence during failed startup cleanup."""

    loaded: SettingsLoadResult
    timeline: list[str]
    saved: list[AppSettings] = field(default_factory=list)

    def load(self) -> SettingsLoadResult:
        """Return the configured startup result."""
        return self.loaded

    def save(self, settings: AppSettings) -> None:
        """Record the final valid settings snapshot."""
        self.timeline.append("repository.save")
        self.saved.append(settings)


@dataclass
class FailingStartRuntime(ShellRuntime):
    """Runtime fake that raises after being constructed and started."""

    timeline: list[str] = field(default_factory=list)
    error: Exception = field(default_factory=RuntimeError)

    def start(self) -> None:
        """Record startup before raising the selected worker failure."""
        super().start()
        self.timeline.append("runtime.start")
        raise self.error

    def close(self) -> None:
        """Record the compensating close request."""
        super().close()
        self.timeline.append("runtime.close")


@dataclass
class FailingSettingsRepository:
    """Repository fake that raises while loading startup settings."""

    error: Exception

    def load(self) -> SettingsLoadResult:
        """Raise the configured private startup error."""
        raise self.error

    def save(self, settings: AppSettings) -> None:
        """Satisfy the outer persistence boundary without saving."""
        del settings


@dataclass
class ClosingRuntime(ShellRuntime):
    """Runtime fake that records normal shutdown after an application fault."""

    timeline: list[str] = field(default_factory=list)

    def close(self) -> None:
        """Record the ordered runtime close request."""
        super().close()
        self.timeline.append("runtime.close")


@dataclass
class UnhandledMainThreadGui:
    """GUI fake that invokes the process exception hook like a Qt callback."""

    error: Exception
    after_exception_hook: Callable[[], None]
    runs: int = 0

    def run(self) -> int:
        """Report an unhandled callback error and return the loop status."""
        self.runs += 1
        sys.excepthook(type(self.error), self.error, None)
        self.after_exception_hook()
        return 0


@dataclass
class InterruptingGui:
    """GUI fake that interrupts the main thread without using the exception hook."""

    runs: int = 0

    def run(self) -> int:
        """Raise a process-control exception from the main event-loop boundary."""
        self.runs += 1
        raise KeyboardInterrupt


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


def test_qt_runtime_factory_failure_closes_the_created_window_without_leaking_secret(
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = SettingsPaths(Path("config"), Path("data"), Path("log"))
    secret = "bond=private-startup-token"  # noqa: S105 - test value must not reach stderr.
    timeline: list[str] = []
    window = StartupFailureWindow(timeline)
    repository = ShellRepository(
        SettingsLoadResult(AppSettings.default(), SettingsLoadStatus.FIRST_RUN)
    )

    def create_runtime(
        *,
        adapter_factory: ControllerAdapterFactory,
        event_sink: RuntimeEventSink,
        clock: WatchdogClock,
    ) -> RuntimePort:
        del adapter_factory, event_sink, clock
        raise RuntimeError(secret)

    dependencies = ApplicationDependencies(
        paths_resolver=lambda: paths,
        repository_factory=lambda _paths: repository,
        runtime_factory=create_runtime,
        window_factory=lambda _spec: window,
        gui_factory=lambda **_kwargs: QtApplicationRunner(),
        clock=SystemClock(),
        logger_configurer=lambda _paths, _level: logging.getLogger(
            "demi-test-runtime-factory-failure"
        ),
    )

    assert run_application(dependencies) == 1

    captured = capsys.readouterr()
    assert timeline == ["window.close"]
    assert captured.out == ""
    assert captured.err == "Project_Demi の起動に失敗しました。\n"
    assert secret not in captured.err


def test_qt_runtime_start_failure_closes_started_resources_in_reverse_without_leaking_secret(
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = SettingsPaths(Path("config"), Path("data"), Path("log"))
    secret = "bond=private-runtime-token"  # noqa: S105 - test value must not reach stderr.
    timeline: list[str] = []
    settings = AppSettings.default()
    repository = StartupFailureRepository(
        loaded=SettingsLoadResult(settings, SettingsLoadStatus.FIRST_RUN),
        timeline=timeline,
    )
    runtime = FailingStartRuntime(timeline=timeline, error=RuntimeError(secret))
    window = StartupFailureWindow(timeline)

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
        window_factory=lambda _spec: window,
        gui_factory=lambda **_kwargs: QtApplicationRunner(),
        clock=SystemClock(),
        logger_configurer=lambda _paths, _level: logging.getLogger(
            "demi-test-runtime-start-failure"
        ),
    )

    assert run_application(dependencies) == 1

    captured = capsys.readouterr()
    assert runtime.started == 1
    assert runtime.closed == 1
    assert timeline == ["runtime.start", "runtime.close", "repository.save", "window.close"]
    assert len(repository.saved) == 1
    assert captured.out == ""
    assert captured.err == "Project_Demi の起動に失敗しました。\n"
    assert secret not in captured.err


def test_qt_settings_load_failure_returns_a_safe_nonzero_status(
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = SettingsPaths(Path("config"), Path("data"), Path("log"))
    secret = "settings=private-load-token"  # noqa: S105 - test value must not reach stderr.
    window_created = False

    def create_window(_spec: WindowSpec) -> StartupFailureWindow:
        nonlocal window_created
        window_created = True
        return StartupFailureWindow([])

    dependencies = ApplicationDependencies(
        paths_resolver=lambda: paths,
        repository_factory=lambda _paths: FailingSettingsRepository(RuntimeError(secret)),
        runtime_factory=lambda **_kwargs: ShellRuntime(),
        window_factory=create_window,
        gui_factory=lambda **_kwargs: QtApplicationRunner(),
        clock=SystemClock(),
        logger_configurer=lambda _paths, _level: logging.getLogger(
            "demi-test-settings-load-failure"
        ),
    )

    assert run_application(dependencies) == 1

    captured = capsys.readouterr()
    assert not window_created
    assert captured.out == ""
    assert captured.err == "Project_Demi の起動に失敗しました。\n"
    assert secret not in captured.err


def test_qt_window_factory_failure_returns_a_safe_nonzero_status(
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = SettingsPaths(Path("config"), Path("data"), Path("log"))
    secret = "window=private-construction-token"  # noqa: S105 - test value must not reach stderr.
    runtime_created = False
    repository = ShellRepository(
        SettingsLoadResult(AppSettings.default(), SettingsLoadStatus.FIRST_RUN)
    )

    def create_runtime(**_kwargs: object) -> ShellRuntime:
        nonlocal runtime_created
        runtime_created = True
        return ShellRuntime()

    def create_window(_spec: WindowSpec) -> StartupFailureWindow:
        raise RuntimeError(secret)

    dependencies = ApplicationDependencies(
        paths_resolver=lambda: paths,
        repository_factory=lambda _paths: repository,
        runtime_factory=create_runtime,
        window_factory=create_window,
        gui_factory=lambda **_kwargs: QtApplicationRunner(),
        clock=SystemClock(),
        logger_configurer=lambda _paths, _level: logging.getLogger(
            "demi-test-window-factory-failure"
        ),
    )

    assert run_application(dependencies) == 1

    captured = capsys.readouterr()
    assert not runtime_created
    assert captured.out == ""
    assert captured.err == "Project_Demi の起動に失敗しました。\n"
    assert secret not in captured.err


def test_qt_main_thread_exception_hook_neutralizes_and_closes_without_leaking_secret(
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = SettingsPaths(Path("config"), Path("data"), Path("log"))
    secret = "callback=private-main-thread-token"  # noqa: S105 - test value must not reach stderr.
    timeline: list[str] = []
    settings = AppSettings.default()
    repository = StartupFailureRepository(
        loaded=SettingsLoadResult(settings, SettingsLoadStatus.FIRST_RUN),
        timeline=timeline,
    )
    runtime = ClosingRuntime(timeline=timeline)
    window = StartupFailureWindow(timeline)
    observed_cleanup: list[tuple[int, int, tuple[str, ...]]] = []
    gui = UnhandledMainThreadGui(
        error=RuntimeError(secret),
        after_exception_hook=lambda: observed_cleanup.append(
            (runtime.closed, len(repository.saved), tuple(timeline))
        ),
    )
    original_exception_hook = sys.excepthook

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
        window_factory=lambda _spec: window,
        gui_factory=lambda **_kwargs: gui,
        clock=SystemClock(),
        logger_configurer=lambda _paths, _level: logging.getLogger("demi-test-main-thread-failure"),
    )

    assert run_application(dependencies) == 1

    captured = capsys.readouterr()
    assert gui.runs == 1
    assert sys.excepthook is original_exception_hook
    assert runtime.frames[-1].capture_active is False
    assert observed_cleanup == [(1, 1, ("runtime.close", "repository.save", "window.close"))]
    assert captured.out == ""
    assert captured.err == ""
    assert secret not in captured.err


def test_qt_main_thread_keyboard_interrupt_is_not_swallowed_after_cleanup() -> None:
    paths = SettingsPaths(Path("config"), Path("data"), Path("log"))
    timeline: list[str] = []
    settings = AppSettings.default()
    repository = StartupFailureRepository(
        loaded=SettingsLoadResult(settings, SettingsLoadStatus.FIRST_RUN),
        timeline=timeline,
    )
    runtime = ClosingRuntime(timeline=timeline)
    window = StartupFailureWindow(timeline)
    gui = InterruptingGui()
    original_exception_hook = sys.excepthook

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
        window_factory=lambda _spec: window,
        gui_factory=lambda **_kwargs: gui,
        clock=SystemClock(),
        logger_configurer=lambda _paths, _level: logging.getLogger("demi-test-keyboard-interrupt"),
    )

    with pytest.raises(KeyboardInterrupt):
        run_application(dependencies)

    assert gui.runs == 1
    assert sys.excepthook is original_exception_hook
    assert runtime.frames[-1].capture_active is False
    assert timeline == ["runtime.close", "repository.save", "window.close"]


def test_qt_runtime_stopped_close_and_ctrl_q_run_cleanup_once(
    qt_application: QApplication,
) -> None:
    assert qt_application is not None
    settings = AppSettings.default()
    repository = ShellRepository(SettingsLoadResult(settings, SettingsLoadStatus.FIRST_RUN))
    runtime = RuntimeStoppedEmitter()
    runner = QtApplicationRunner()
    paths = SettingsPaths(Path("config"), Path("data"), Path("log"))
    observed_before_competing_close: list[tuple[bool, bool]] = []
    shutdown_callback_calls = 0
    window_holder: list[CountingMainWindow] = []

    def create_window(spec: WindowSpec) -> CountingMainWindow:
        window = CountingMainWindow(spec)
        window_holder.append(window)
        return window

    def create_gui(
        *,
        window: MainWindow,
        on_shutdown_requested: Callable[[WindowSettings | None], bool],
        **_kwargs: object,
    ) -> QtApplicationRunner:
        def count_shutdown(state: WindowSettings | None) -> bool:
            nonlocal shutdown_callback_calls
            shutdown_callback_calls += 1
            return on_shutdown_requested(state)

        runner.configure(window=window, on_shutdown_requested=count_shutdown)

        def emit_stopped_then_request_competing_closes() -> None:
            runtime.emit_runtime_stopped_from_worker()
            qt_application.processEvents()
            observed_before_competing_close.append(
                (not window.isVisible(), window.input_evaluation_interval_ms is None)
            )
            window.quit_action.trigger()
            window.close()

        QTimer.singleShot(0, emit_stopped_then_request_competing_closes)
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
        window_factory=create_window,
        gui_factory=create_gui,
        clock=SystemClock(),
        logger_configurer=lambda _paths, _level: logging.getLogger(
            "demi-test-runtime-stopped-race"
        ),
    )

    assert run_application(dependencies) == 0

    window = window_holder[0]
    assert observed_before_competing_close == [(True, True)]
    assert runtime.closed == 1
    assert len(repository.saved) == 1
    assert shutdown_callback_calls == 1
    assert window.input_evaluation_interval_ms is None
    assert window.input_teardown_calls == 1


def test_qt_shutdown_releases_gui_objects_on_the_main_thread(
    qt_application: QApplication,
) -> None:
    settings = AppSettings.default()
    repository = ShellRepository(SettingsLoadResult(settings, SettingsLoadStatus.FIRST_RUN))
    runtime = RuntimeStoppedEmitter()
    runner = QtApplicationRunner()
    paths = SettingsPaths(Path("config"), Path("data"), Path("log"))
    main_thread = get_ident()
    lifecycle_observations: list[tuple[str, int, bool]] = []
    destruction_observations: list[tuple[str, int]] = []
    timer_inactive_after_teardown: list[bool] = []
    windows: list[ThreadTrackingMainWindow] = []

    def create_window(spec: WindowSpec) -> ThreadTrackingMainWindow:
        window = ThreadTrackingMainWindow(
            spec,
            lifecycle_observations=lifecycle_observations,
            destruction_observations=destruction_observations,
            timer_inactive_after_teardown=timer_inactive_after_teardown,
        )
        windows.append(window)
        return window

    def create_gui(
        *,
        window: MainWindow,
        on_shutdown_requested: Callable[[WindowSettings | None], bool],
        **_kwargs: object,
    ) -> QtApplicationRunner:
        runner.configure(window=window, on_shutdown_requested=on_shutdown_requested)
        QTimer.singleShot(0, runtime.emit_runtime_stopped_from_worker)
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
        window_factory=create_window,
        gui_factory=create_gui,
        clock=SystemClock(),
        logger_configurer=lambda _paths, _level: logging.getLogger(
            "demi-test-gui-thread-ownership"
        ),
    )

    assert run_application(dependencies) == 0

    qt_application.processEvents()

    assert windows
    assert {phase for phase, _, _ in lifecycle_observations} >= {
        "create",
        "refresh",
        "shutdown",
        "input-teardown",
    }
    assert {thread_id for _, thread_id, _ in lifecycle_observations} == {main_thread}
    assert all(is_gui_thread for _, _, is_gui_thread in lifecycle_observations)
    assert timer_inactive_after_teardown == [True]
    assert set(destruction_observations) == {
        ("window", main_thread),
        ("timer", main_thread),
    }
    assert qt_application.topLevelWidgets() == []


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


def test_qt_event_loop_stays_responsive_during_slow_runtime_operations(
    qt_application: QApplication,
) -> None:
    assert qt_application is not None
    settings = replace(
        AppSettings.default(),
        connection=replace(AppSettings.default().connection, adapter_id="usb:0"),
    )
    repository = ShellRepository(SettingsLoadResult(settings, SettingsLoadStatus.LOADED))
    timing_events: list[TimingEvent] = []
    runtime = SlowRuntime(timing_events=timing_events)
    runner = QtApplicationRunner()
    paths = SettingsPaths(Path("config"), Path("data"), Path("log"))
    tick_times: list[float] = []
    completed: list[bool] = []

    def create_gui(
        *,
        window: MainWindow,
        session: ApplicationSession,
        on_shutdown_requested: Callable[[WindowSettings | None], bool],
        **_kwargs: object,
    ) -> QtApplicationRunner:
        runner.configure(window=window, on_shutdown_requested=on_shutdown_requested)
        timer = QTimer(window)
        timer.setTimerType(Qt.TimerType.PreciseTimer)
        assert timer.timerType() is Qt.TimerType.PreciseTimer
        timer.setInterval(10)
        phase = 0

        def advance() -> None:
            nonlocal phase
            tick_times.append(time.monotonic())
            connection_state = session.presentation.model.connection_state
            _record_timing_event(
                timing_events,
                stage="gui.timer.tick",
                detail=f"phase={phase}, state={connection_state.name}",
            )
            if phase == 0 and connection_state is ConnectionState.READY:
                _record_timing_event(
                    timing_events,
                    stage="gui.connection_action.begin",
                    detail="connect",
                )
                session.connection_action()
                _record_timing_event(
                    timing_events,
                    stage="gui.connection_action.end",
                    detail="connect",
                )
                phase = 1
            elif phase == 1 and connection_state is ConnectionState.CONNECTED:
                _record_timing_event(
                    timing_events,
                    stage="gui.connection_action.begin",
                    detail="disconnect",
                )
                session.connection_action()
                _record_timing_event(
                    timing_events,
                    stage="gui.connection_action.end",
                    detail="disconnect",
                )
                phase = 2
            elif phase == 2 and connection_state is ConnectionState.READY:
                timer.stop()
                completed.append(True)
                window.close()

        def fail_safe_close() -> None:
            if not completed:
                timer.stop()
                window.close()

        timer.timeout.connect(advance)
        timer.start()
        QTimer.singleShot(1000, fail_safe_close)
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
        window_factory=lambda spec: TimingMainWindow(spec, timing_events=timing_events),
        gui_factory=create_gui,
        clock=SystemClock(),
        logger_configurer=lambda _paths, _level: logging.getLogger("demi-test-qt-slow-runtime"),
    )

    assert run_application(dependencies) == 0
    assert completed == [True]
    assert [type(command) for command in runtime.commands] == [
        DiscoverAdapters,
        ConnectSaved,
        Disconnect,
    ]
    assert len(runtime.workers) == 1
    assert not runtime.workers[0].is_alive()
    assert len(tick_times) >= 4
    max_tick_gap = max(later - earlier for earlier, later in pairwise(tick_times))
    assert max_tick_gap < 0.1, _format_timing_events(timing_events)
