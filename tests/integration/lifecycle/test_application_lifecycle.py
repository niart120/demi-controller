"""Injected assembly tests for the desktop application lifecycle."""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest

from demi.app import ApplicationDependencies, ApplicationSession, run_application
from demi.application.state import ConnectionState
from demi.config.paths import SettingsPaths
from demi.config.repository import SettingsLoadResult, SettingsLoadStatus
from demi.controller.commands import ConnectSaved, ControllerCommand, DiscoverAdapters
from demi.controller.events import AdapterDescriptor, AdaptersDiscovered, ConnectionChanged
from demi.domain.controller import ControllerFrame, LogicalButton
from demi.domain.mapping import Binding, BindingTarget, InputProfile
from demi.domain.settings import (
    AppSettings,
    ControllerColorSettings,
    DiagnosticLevel,
    InputSettings,
    MouseSettings,
    WindowSettings,
)
from demi.ui.window import WindowSpec

if TYPE_CHECKING:
    from demi.application.coordinator import CaptureCoordinator
    from demi.ui.controller_view import ControllerView
    from demi.ui.status_bar import StatusBar


def _lifecycle_logger() -> logging.Logger:
    """Build a logger that does not route fake-assembly records to stderr."""
    logger = logging.Logger("demi.integration.lifecycle")
    logger.addHandler(logging.NullHandler())
    return logger


@dataclass
class LifecycleClock:
    """Mutable monotonic clock shared by one injected application assembly."""

    now_ns: int = 1_000_000_000

    def monotonic_ns(self) -> int:
        """Return the deterministic current timestamp."""
        return self.now_ns


@dataclass
class LifecycleRepository:
    """Repository boundary that supplies one configured load result."""

    result: SettingsLoadResult
    order: list[str]
    load_calls: int = 0
    saved: list[AppSettings] = field(default_factory=list)

    def load(self) -> SettingsLoadResult:
        """Return the configured settings load outcome."""
        self.load_calls += 1
        self.order.append("repository.load")
        return self.result

    def save(self, settings: AppSettings) -> None:
        """Record the settings snapshot saved during ordered shutdown."""
        self.saved.append(settings)
        self.order.append("repository.save")


@dataclass
class LifecycleRuntime:
    """Runtime boundary recording lifecycle, command, and frame order."""

    order: list[str]
    started: int = 0
    closed: int = 0
    commands: list[ControllerCommand] = field(default_factory=list)
    frames: list[ControllerFrame] = field(default_factory=list)

    def start(self) -> None:
        """Record worker startup."""
        self.started += 1
        self.order.append("runtime.start")

    def post(self, command: ControllerCommand) -> None:
        """Record an ordered command sent from the application session."""
        self.commands.append(command)
        self.order.append(f"runtime.post:{type(command).__name__}")

    def offer_frame(self, frame: ControllerFrame) -> bool:
        """Record one frame offered by the input publisher."""
        self.frames.append(frame)
        self.order.append("runtime.frame")
        return True

    def close(self) -> None:
        """Record worker shutdown."""
        self.closed += 1
        self.order.append("runtime.close")


@dataclass
class LifecycleWindow:
    """Native-window boundary created from the application window specification."""

    spec: WindowSpec
    order: list[str]
    width: int = field(init=False)
    height: int = field(init=False)
    exclusive_mouse: list[bool] = field(default_factory=list)
    close_calls: int = 0

    def __post_init__(self) -> None:
        """Expose the configured logical dimensions as mutable window attributes."""
        self.width = self.spec.width
        self.height = self.spec.height

    def set_exclusive_mouse(self, exclusive: bool = True) -> None:
        """Record capture ownership changes during shutdown."""
        self.exclusive_mouse.append(exclusive)
        self.order.append(f"window.exclusive:{exclusive}")

    def close(self) -> None:
        """Record native-window teardown."""
        self.close_calls += 1
        self.order.append("window.close")


@dataclass
class LifecycleGui:
    """Display-free GUI loop that can inspect one fully assembled application."""

    order: list[str]
    on_run: Callable[[dict[str, object]], None] | None = None
    kwargs: dict[str, object] = field(default_factory=dict)
    runs: int = 0

    def run(self) -> None:
        """Record entry after runtime startup and execute the optional probe."""
        self.runs += 1
        self.order.append("gui.run")
        if self.on_run is not None:
            self.on_run(self.kwargs)


@dataclass
class LifecycleAssembly:
    """One complete fake outer-boundary assembly for ``run_application``."""

    result: SettingsLoadResult
    paths: SettingsPaths
    order: list[str] = field(default_factory=list)
    clock: LifecycleClock = field(default_factory=LifecycleClock)
    logging_levels: list[DiagnosticLevel] = field(default_factory=list)
    gui_error: Exception | None = None
    repository: LifecycleRepository = field(init=False)
    runtime: LifecycleRuntime = field(init=False)
    gui: LifecycleGui = field(init=False)
    window: LifecycleWindow | None = None
    logger: logging.Logger = field(default_factory=_lifecycle_logger)

    def __post_init__(self) -> None:
        """Create boundaries whose instances are observed by every factory."""
        self.repository = LifecycleRepository(self.result, self.order)
        self.runtime = LifecycleRuntime(self.order)
        self.gui = LifecycleGui(self.order)
        self.logger.addHandler(logging.NullHandler())
        self.logger.propagate = False

    def dependencies(self) -> ApplicationDependencies:
        """Return the composition-root dependencies for this fake assembly."""
        return ApplicationDependencies(
            paths_resolver=self.resolve_paths,
            repository_factory=self.create_repository,
            runtime_factory=self.create_runtime,
            window_factory=self.create_window,
            gui_factory=self.create_gui,
            clock=self.clock,
            logger_configurer=self.configure_logger,
        )

    def resolve_paths(self) -> SettingsPaths:
        """Return the deterministic user-local path set."""
        return self.paths

    def create_repository(self, paths: SettingsPaths) -> LifecycleRepository:
        """Return the sole repository after checking the resolved paths."""
        assert paths == self.paths
        self.order.append("repository.create")
        return self.repository

    def create_runtime(
        self,
        *,
        adapter_factory: object,
        event_sink: object,
        clock: object,
    ) -> LifecycleRuntime:
        """Return the sole display-free runtime without using its worker inputs."""
        del adapter_factory, event_sink, clock
        self.order.append("runtime.create")
        return self.runtime

    def create_window(self, spec: WindowSpec) -> LifecycleWindow:
        """Create one fake native window from the saved window settings."""
        self.window = LifecycleWindow(spec, self.order)
        self.order.append("window.create")
        return self.window

    def create_gui(self, **kwargs: object) -> LifecycleGui:
        """Capture the assembled main-thread objects without creating a display."""
        self.gui.kwargs = kwargs
        self.order.append("gui.create")
        if self.gui_error is not None:
            raise self.gui_error
        return self.gui

    def configure_logger(self, paths: SettingsPaths, level: DiagnosticLevel) -> logging.Logger:
        """Record the requested diagnostic level without opening a log file."""
        assert paths == self.paths
        self.logging_levels.append(level)
        self.order.append(f"logger.configure:{level.value}")
        return self.logger


def test_first_run_starts_discovers_runs_gui_and_shuts_down_in_order() -> None:
    """A first run performs its complete lifecycle without display or Bluetooth access."""
    assembly = LifecycleAssembly(
        SettingsLoadResult(AppSettings.default(), SettingsLoadStatus.FIRST_RUN),
        SettingsPaths(Path("config"), Path("data"), Path("log")),
    )

    assert run_application(assembly.dependencies()) == 0

    assert assembly.repository.load_calls == 1
    assert assembly.runtime.started == 1
    assert assembly.runtime.commands == [DiscoverAdapters()]
    assert assembly.gui.runs == 1
    assert assembly.runtime.closed == 1
    assert assembly.window is not None
    assert assembly.window.close_calls == 1
    assert len(assembly.repository.saved) == 1
    assert assembly.order.index("runtime.start") < assembly.order.index(
        "runtime.post:DiscoverAdapters"
    )
    assert assembly.order.index("runtime.post:DiscoverAdapters") < assembly.order.index("gui.run")
    assert assembly.order.index("gui.run") < assembly.order.index("runtime.close")
    assert assembly.order.index("runtime.close") < assembly.order.index("window.close")


def test_recovered_settings_expose_only_the_safe_backup_name_to_the_gui() -> None:
    """A recovered load reaches presentation with no corrupt-file path disclosure."""
    backup_path = Path("private") / "settings.toml.broken-20260713-123456"
    settings = AppSettings.default()
    assembly = LifecycleAssembly(
        SettingsLoadResult(settings, SettingsLoadStatus.RECOVERED, backup_path),
        SettingsPaths(Path("config"), Path("data"), Path("log")),
    )

    assert run_application(assembly.dependencies()) == 0

    session = _session_from(assembly.gui)
    notice = session.presentation.model.recovery_notice
    expected_notice = (
        "設定を復旧しました。破損ファイルを "
        "settings.toml.broken-20260713-123456 として退避しました。"
    )
    assert notice == expected_notice
    assert str(backup_path.parent) not in notice
    assert "settings.toml.broken-20260713-123456" in notice


def test_nondefault_settings_reach_window_gui_session_and_saved_reconnect() -> None:
    """One assembled process preserves all non-default settings consumers."""
    base = AppSettings.default()
    profile = InputProfile(
        id="integration",
        name="統合検証",
        builtin=False,
        bindings=(Binding("KEY:H", BindingTarget.BUTTON_A),),
    )
    colors = ControllerColorSettings(
        body="#ABCDEF",
        buttons="#123456",
        left_grip="#654321",
        right_grip="#FEDCBA",
    )
    settings = replace(
        base,
        active_profile=profile.id,
        profiles=(profile,),
        window=WindowSettings(width=1280, height=720, maximized=True),
        connection=replace(
            base.connection,
            adapter_id="usb:custom",
            bond_slot="integration",
            timeout_seconds=12.5,
            reconnect_on_start=True,
            diagnostic_level=DiagnosticLevel.DEBUG,
        ),
        controller_colors=colors,
        input=InputSettings(
            evaluation_interval_ms=16,
            circular_stick_limit=True,
            mouse=MouseSettings(
                gyro_enabled=False,
                horizontal_sensitivity=2.5,
                vertical_sensitivity=0.5,
                invert_y=True,
                pitch_limit_degrees=45.0,
            ),
        ),
    )
    assembly = LifecycleAssembly(
        SettingsLoadResult(settings, SettingsLoadStatus.LOADED),
        SettingsPaths(Path("config"), Path("data"), Path("log")),
    )
    observed: dict[str, object] = {}

    def inspect_running_gui(kwargs: dict[str, object]) -> None:
        """Capture live consumers before the GUI loop returns into shutdown."""
        session = cast("ApplicationSession", kwargs["session"])
        coordinator = cast("CaptureCoordinator", kwargs["coordinator"])
        view = cast("ControllerView", kwargs["view"])
        status_bar = cast("StatusBar", kwargs["status_bar"])
        observed["gui_settings"] = kwargs["settings"]
        observed["session_settings"] = session.settings
        observed["interval"] = coordinator.publisher.evaluation_interval_ms
        observed["colors"] = view.colors
        observed["status_interval"] = status_bar.model.evaluation_interval_ms

        coordinator.start_capture()
        coordinator.publisher.state.press_key("H")
        coordinator.publisher.state.add_mouse_motion(24, 12)
        assembly.clock.now_ns += 16_000_000
        observed["frame"] = coordinator.evaluate()

        session.handle_runtime_event(
            AdaptersDiscovered((AdapterDescriptor("usb:custom", "検証アダプター", "usb"),))
        )
        session.handle_runtime_event(
            ConnectionChanged(ConnectionState.READY, adapter_id="usb:custom")
        )

    assembly.gui.on_run = inspect_running_gui

    assert run_application(assembly.dependencies()) == 0

    assert assembly.window is not None
    assert assembly.window.spec.width == 1280
    assert assembly.window.spec.height == 720
    assert assembly.window.spec.maximized is True
    assert observed["gui_settings"] is settings
    assert observed["session_settings"] is settings
    assert observed["interval"] == 16
    assert observed["status_interval"] == 16
    assert observed["colors"] == colors
    frame = cast("ControllerFrame", observed["frame"])
    assert frame.buttons == frozenset({LogicalButton.A})
    assert frame.gyro_rate.x_radians_per_second == 0.0
    assert frame.gyro_rate.y_radians_per_second == 0.0
    assert frame.gyro_rate.z_radians_per_second == 0.0
    reconnects = [
        command for command in assembly.runtime.commands if isinstance(command, ConnectSaved)
    ]
    assert len(reconnects) == 1
    assert reconnects[0].adapter_id == "usb:custom"
    assert reconnects[0].bond_path == Path("data") / "bonds" / "pro-controller" / "integration.json"
    assert reconnects[0].timeout_seconds == 12.5
    assert reconnects[0].colors == colors
    assert assembly.logging_levels == [DiagnosticLevel.INFO, DiagnosticLevel.DEBUG]


def test_startup_failure_closes_created_runtime_and_window_once_without_leaking_details(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A factory failure after resource creation returns a safe nonzero status."""
    assembly = LifecycleAssembly(
        SettingsLoadResult(AppSettings.default(), SettingsLoadStatus.FIRST_RUN),
        SettingsPaths(Path("config"), Path("data"), Path("log")),
        gui_error=RuntimeError("bond=/private/secret.json"),
    )

    assert run_application(assembly.dependencies()) == 1

    captured = capsys.readouterr()
    assert "Project_Demi の起動に失敗しました。" in captured.err
    assert "secret" not in captured.err
    assert assembly.runtime.started == 0
    assert assembly.runtime.closed == 1
    assert assembly.window is not None
    assert assembly.window.close_calls == 1


def _session_from(gui: LifecycleGui) -> ApplicationSession:
    """Return the application session captured by a successful GUI factory."""
    session = gui.kwargs["session"]
    assert isinstance(session, ApplicationSession)
    return session
