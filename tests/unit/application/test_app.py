import logging
from dataclasses import dataclass, field, replace
from pathlib import Path

from demi.app import ApplicationDependencies, ApplicationSession, _window_spec_for, run_application
from demi.application.coordinator import CaptureCoordinator
from demi.application.dialogs import DialogKind
from demi.application.state import ConnectionState
from demi.config.paths import SettingsPaths
from demi.config.repository import SettingsLoadResult, SettingsLoadStatus
from demi.controller.commands import (
    ConnectSaved,
    Disconnect,
    RecreateWithColors,
    StartPairing,
)
from demi.controller.events import (
    AdapterDescriptor,
    AdaptersDiscovered,
    ConnectionChanged,
    ControllerError,
    ControllerErrorCategory,
    PairingProgress,
    WatchdogNeutralized,
)
from demi.domain.controller import ControllerFrame
from demi.domain.settings import (
    AppSettings,
    ControllerColorSettings,
    DiagnosticLevel,
    InputSettings,
    WindowSettings,
)
from demi.input.publisher import InputPublisher


@dataclass
class FakeClock:
    """Deterministic monotonic clock."""

    now_ns: int = 1

    def monotonic_ns(self) -> int:
        """Return the configured monotonic timestamp."""
        return self.now_ns


@dataclass
class FakeRuntime:
    """Runtime fake recording composition-root lifecycle calls."""

    started: int = 0
    closed: int = 0
    commands: list[object] = field(default_factory=list)
    frames: list[ControllerFrame] = field(default_factory=list)
    close_error: Exception | None = None

    def start(self) -> None:
        """Record worker startup."""
        self.started += 1

    def post(self, command: object) -> None:
        """Record an ordered runtime command."""
        self.commands.append(command)

    def offer_frame(self, frame: ControllerFrame) -> bool:
        """Record an input frame."""
        self.frames.append(frame)
        return True

    def close(self) -> None:
        """Record ordered worker shutdown."""
        self.closed += 1
        if self.close_error is not None:
            raise self.close_error


@dataclass
class FakeWindow:
    """Window boundary sufficient for application assembly."""

    width: int = 960
    height: int = 640
    maximized: bool = False
    pointer_capture: list[bool] = field(default_factory=list)
    close_calls: int = 0

    def set_pointer_capture(self, enabled: bool) -> None:
        """Record pointer capture changes."""
        self.pointer_capture.append(enabled)

    def window_state(self) -> WindowSettings:
        """Return the current state consumed by ordered shutdown."""
        return WindowSettings(
            width=self.width,
            height=self.height,
            maximized=self.maximized,
        )

    def close(self) -> None:
        """Record native window teardown."""
        self.close_calls += 1


@dataclass
class FakeInputWindow(FakeWindow):
    """Window fake that records the optional Qt input-boundary setup."""

    configured_publisher: InputPublisher | None = None
    configured_coordinator: CaptureCoordinator | None = None
    relative_capture_epochs: list[int] = field(default_factory=list)
    relative_stop_calls: int = 0

    def configure_input(
        self,
        *,
        publisher: InputPublisher,
        coordinator: CaptureCoordinator,
    ) -> None:
        """Record the input publisher and coordinator selected at composition."""
        self.configured_publisher = publisher
        self.configured_coordinator = coordinator

    def start_relative_pointer_capture(self, capture_epoch: int) -> None:
        """Record one relative-pointer capture start."""
        self.relative_capture_epochs.append(capture_epoch)

    def stop_relative_pointer_capture(self) -> None:
        """Record one relative-pointer capture stop."""
        self.relative_stop_calls += 1


@dataclass
class FakePreviewWindow(FakeWindow):
    """Window fake that records colors selected for the frame preview."""

    preview_colors: ControllerColorSettings | None = None
    preview_frames: list[ControllerFrame] = field(default_factory=list)

    def set_frame(self, frame: ControllerFrame) -> None:
        """Record one frame selected for preview display."""
        self.preview_frames.append(frame)

    def set_controller_colors(self, colors: ControllerColorSettings) -> None:
        """Record the validated preview colors selected at startup."""
        self.preview_colors = colors


@dataclass
class FakeGui:
    """GUI loop fake that returns immediately."""

    runs: int = 0
    exit_status: int = 0

    def run(self) -> int:
        """Record one GUI loop entry."""
        self.runs += 1
        return self.exit_status


def test_application_runner_assembles_boundaries_without_starting_the_runtime() -> None:
    paths = SettingsPaths(Path("config"), Path("data"), Path("log"))
    repository_result = SettingsLoadResult(AppSettings.default(), SettingsLoadStatus.FIRST_RUN)
    runtime = FakeRuntime()
    window = FakeWindow()
    gui = FakeGui()
    logger = logging.getLogger("demi-test-app")
    gui_kwargs: dict[str, object] = {}

    def create_gui(**kwargs: object) -> FakeGui:
        """Capture composition-root dependencies without entering a GUI loop."""
        gui_kwargs.update(kwargs)
        return gui

    dependencies = ApplicationDependencies(
        paths_resolver=lambda: paths,
        repository_factory=lambda _paths: FakeRepository(repository_result),
        runtime_factory=lambda **_kwargs: runtime,
        window_factory=lambda _spec: window,
        gui_factory=create_gui,
        clock=FakeClock(),
        logger_configurer=lambda _paths, _level: logger,
    )

    assert run_application(dependencies) == 0

    assert runtime.started == 0
    assert runtime.commands == []
    assert gui.runs == 1
    assert runtime.closed == 1
    assert isinstance(gui_kwargs["session"], ApplicationSession)
    assert gui_kwargs["actions"] is gui_kwargs["session"]
    assert callable(gui_kwargs["settings_provider"])
    assert gui_kwargs["dialogs"] is gui_kwargs["session"].dialogs
    assert callable(gui_kwargs["editor_provider"])
    assert {"backend", "bridge", "event_pump", "status_bar", "view"}.isdisjoint(gui_kwargs)


def test_application_runner_configures_the_optional_input_window_boundary() -> None:
    paths = SettingsPaths(Path("config"), Path("data"), Path("log"))
    repository_result = SettingsLoadResult(AppSettings.default(), SettingsLoadStatus.FIRST_RUN)
    runtime = FakeRuntime()
    window = FakeInputWindow()
    logger = logging.getLogger("demi-test-input-window")
    dependencies = ApplicationDependencies(
        paths_resolver=lambda: paths,
        repository_factory=lambda _paths: FakeRepository(repository_result),
        runtime_factory=lambda **_kwargs: runtime,
        window_factory=lambda _spec: window,
        gui_factory=lambda **_kwargs: FakeGui(),
        clock=FakeClock(),
        logger_configurer=lambda _paths, _level: logger,
    )

    assert run_application(dependencies) == 0

    assert window.configured_publisher is not None
    assert window.configured_coordinator is not None
    assert window.configured_coordinator.publisher is window.configured_publisher


def test_application_runner_passes_saved_colors_to_the_preview_window() -> None:
    paths = SettingsPaths(Path("config"), Path("data"), Path("log"))
    colors = ControllerColorSettings(
        body="#102030",
        buttons="#405060",
        left_grip="#708090",
        right_grip="#A0B0C0",
    )
    settings = replace(AppSettings.default(), controller_colors=colors)
    repository_result = SettingsLoadResult(settings, SettingsLoadStatus.FIRST_RUN)
    window = FakePreviewWindow()
    dependencies = ApplicationDependencies(
        paths_resolver=lambda: paths,
        repository_factory=lambda _paths: FakeRepository(repository_result),
        runtime_factory=lambda **_kwargs: FakeRuntime(),
        window_factory=lambda _spec: window,
        gui_factory=lambda **_kwargs: FakeGui(),
        clock=FakeClock(),
        logger_configurer=lambda _paths, _level: logging.getLogger("demi-test-preview-colors"),
    )

    assert run_application(dependencies) == 0

    assert window.preview_colors == colors


def test_application_runner_returns_nonzero_when_ordered_shutdown_fails() -> None:
    paths = SettingsPaths(Path("config"), Path("data"), Path("log"))
    result = SettingsLoadResult(AppSettings.default(), SettingsLoadStatus.FIRST_RUN)
    runtime = FakeRuntime(close_error=RuntimeError())
    logger = logging.getLogger("demi-test-shutdown-failure")
    dependencies = ApplicationDependencies(
        paths_resolver=lambda: paths,
        repository_factory=lambda _paths: FakeRepository(result),
        runtime_factory=lambda **_kwargs: runtime,
        window_factory=lambda _spec: FakeWindow(),
        gui_factory=lambda **_kwargs: FakeGui(),
        clock=FakeClock(),
        logger_configurer=lambda _paths, _level: logger,
    )

    assert run_application(dependencies) == 1
    assert runtime.closed == 1


def test_application_runner_returns_the_gui_event_loop_status() -> None:
    paths = SettingsPaths(Path("config"), Path("data"), Path("log"))
    result = SettingsLoadResult(AppSettings.default(), SettingsLoadStatus.FIRST_RUN)
    runtime = FakeRuntime()
    gui = FakeGui(exit_status=23)
    logger = logging.getLogger("demi-test-gui-status")
    dependencies = ApplicationDependencies(
        paths_resolver=lambda: paths,
        repository_factory=lambda _paths: FakeRepository(result),
        runtime_factory=lambda **_kwargs: runtime,
        window_factory=lambda _spec: FakeWindow(),
        gui_factory=lambda **_kwargs: gui,
        clock=FakeClock(),
        logger_configurer=lambda _paths, _level: logger,
    )

    assert run_application(dependencies) == 23
    assert gui.runs == 1


def test_window_spec_preserves_the_saved_maximized_state() -> None:
    settings = replace(
        AppSettings.default(),
        window=replace(AppSettings.default().window, width=1200, height=800, maximized=True),
    )

    spec = _window_spec_for(settings)

    assert (spec.width, spec.height, spec.maximized) == (1200, 800, True)


def test_session_reconnects_once_only_when_the_saved_adapter_is_discovered() -> None:
    settings = replace(
        AppSettings.default(),
        connection=replace(
            AppSettings.default().connection,
            adapter_id="usb:0",
            reconnect_on_start=True,
        ),
    )
    runtime = FakeRuntime()
    coordinator = make_coordinator(runtime)
    session = ApplicationSession(
        settings=settings,
        paths=SettingsPaths(Path("config"), Path("data"), Path("log")),
        repository=FakeRepository(SettingsLoadResult(settings, SettingsLoadStatus.LOADED)),
        runtime=runtime,
        coordinator=coordinator,
    )

    session.begin()
    session.handle_runtime_event(ConnectionChanged(ConnectionState.READY))
    session.handle_runtime_event(
        AdaptersDiscovered((AdapterDescriptor("usb:0", "Adapter", "usb"),))
    )
    reconnects = [command for command in runtime.commands if isinstance(command, ConnectSaved)]
    assert reconnects == []

    session.handle_runtime_event(ConnectionChanged(ConnectionState.READY))
    session.handle_runtime_event(
        AdaptersDiscovered((AdapterDescriptor("usb:0", "Adapter", "usb"),))
    )

    reconnects = [command for command in runtime.commands if isinstance(command, ConnectSaved)]
    assert len(reconnects) == 1
    assert reconnects[0].adapter_id == "usb:0"
    assert reconnects[0].bond_path == Path("data") / "bonds" / "pro-controller" / "default.json"
    assert session.presentation.model.connection_state is ConnectionState.CONNECTING
    assert session.presentation.model.adapter_label == "Adapter"


def test_session_does_not_reconnect_for_a_missing_adapter_or_when_disabled() -> None:
    missing_adapter_settings = replace(
        AppSettings.default(),
        connection=replace(
            AppSettings.default().connection,
            adapter_id="usb:missing",
            reconnect_on_start=True,
        ),
    )
    missing_runtime = FakeRuntime()
    missing_session = ApplicationSession(
        settings=missing_adapter_settings,
        paths=SettingsPaths(Path("config"), Path("data"), Path("log")),
        repository=FakeRepository(
            SettingsLoadResult(missing_adapter_settings, SettingsLoadStatus.LOADED)
        ),
        runtime=missing_runtime,
        coordinator=make_coordinator(missing_runtime),
    )

    missing_session.begin()
    missing_session.handle_runtime_event(AdaptersDiscovered(()))
    missing_session.handle_runtime_event(ConnectionChanged(ConnectionState.READY))

    assert not any(isinstance(command, ConnectSaved) for command in missing_runtime.commands)
    assert missing_session.presentation.model.warning == "保存済みの USB アダプターが見つかりません"

    disabled_settings = replace(
        AppSettings.default(),
        connection=replace(
            AppSettings.default().connection,
            adapter_id="usb:0",
            reconnect_on_start=False,
        ),
    )
    disabled_runtime = FakeRuntime()
    disabled_session = ApplicationSession(
        settings=disabled_settings,
        paths=SettingsPaths(Path("config"), Path("data"), Path("log")),
        repository=FakeRepository(SettingsLoadResult(disabled_settings, SettingsLoadStatus.LOADED)),
        runtime=disabled_runtime,
        coordinator=make_coordinator(disabled_runtime),
    )

    disabled_session.begin()
    disabled_session.handle_runtime_event(
        AdaptersDiscovered((AdapterDescriptor("usb:0", "Adapter", "usb"),))
    )
    disabled_session.handle_runtime_event(ConnectionChanged(ConnectionState.READY))

    assert not any(isinstance(command, ConnectSaved) for command in disabled_runtime.commands)
    assert not any(isinstance(command, StartPairing) for command in disabled_runtime.commands)


def test_session_updates_the_selected_adapter_label_after_discovery() -> None:
    settings = AppSettings.default()
    runtime = FakeRuntime()
    coordinator = make_coordinator(runtime)
    session = ApplicationSession(
        settings=settings,
        paths=SettingsPaths(Path("config"), Path("data"), Path("log")),
        repository=FakeRepository(SettingsLoadResult(settings, SettingsLoadStatus.LOADED)),
        runtime=runtime,
        coordinator=coordinator,
    )

    session.handle_runtime_event(ConnectionChanged(ConnectionState.READY, adapter_id="usb:0"))
    session.handle_runtime_event(
        AdaptersDiscovered((AdapterDescriptor("usb:0", "Adapter", "usb"),))
    )

    assert session.presentation.model.adapter_label == "Adapter"


def test_session_preserves_an_error_and_ignores_a_stale_watchdog_event() -> None:
    settings = AppSettings.default()
    runtime = FakeRuntime()
    coordinator = make_coordinator(runtime)
    session = ApplicationSession(
        settings=settings,
        paths=SettingsPaths(Path("config"), Path("data"), Path("log")),
        repository=FakeRepository(SettingsLoadResult(settings, SettingsLoadStatus.LOADED)),
        runtime=runtime,
        coordinator=coordinator,
    )
    assert coordinator.start_capture() is True
    current_epoch = coordinator.capture_epoch

    session.handle_runtime_event(WatchdogNeutralized(capture_epoch=current_epoch - 1))
    assert coordinator.is_captured is True

    session.handle_runtime_event(
        ControllerError(
            category=ControllerErrorCategory.RECONNECT_FAILED,
            summary="ignored lower-level summary",
            retryable=True,
            diagnostic_id="runtime-0001",
        )
    )
    session.handle_runtime_event(ConnectionChanged(ConnectionState.READY))

    assert coordinator.is_captured is False
    assert session.presentation.model.connection_state is ConnectionState.READY
    assert session.presentation.model.error == "保存済み接続に失敗しました"


def test_session_save_applies_mouse_settings_to_the_live_input_publisher() -> None:
    settings = AppSettings.default()
    runtime = FakeRuntime()
    coordinator = make_coordinator(runtime)
    repository = FakeRepository(SettingsLoadResult(settings, SettingsLoadStatus.LOADED))
    session = ApplicationSession(
        settings=settings,
        paths=SettingsPaths(Path("config"), Path("data"), Path("log")),
        repository=repository,
        runtime=runtime,
        coordinator=coordinator,
    )

    assert session.open_settings(DialogKind.MAPPING) is True
    assert session.settings_modal.editor is not None
    session.settings_modal.editor.update_mouse(gyro_enabled=False, horizontal_sensitivity=2.0)

    assert session.save_settings() is True
    assert session.settings.input.mouse.gyro_enabled is False
    assert repository.saved[-1].input.mouse.horizontal_sensitivity == 2.0
    assert coordinator.start_capture() is True
    coordinator.publisher.state.add_mouse_motion(12, 6)

    frame = coordinator.evaluate()

    assert frame.gyro_rate.x_radians_per_second == 0.0
    assert frame.gyro_rate.y_radians_per_second == 0.0


def test_session_routes_toolbar_connection_and_capture_actions() -> None:
    settings = replace(
        AppSettings.default(),
        connection=replace(AppSettings.default().connection, adapter_id="usb:0"),
    )
    runtime = FakeRuntime()
    coordinator = make_coordinator(runtime)
    session = ApplicationSession(
        settings=settings,
        paths=SettingsPaths(Path("config"), Path("data"), Path("log")),
        repository=FakeRepository(SettingsLoadResult(settings, SettingsLoadStatus.LOADED)),
        runtime=runtime,
        coordinator=coordinator,
    )
    session.handle_runtime_event(
        AdaptersDiscovered((AdapterDescriptor("usb:0", "Adapter", "usb"),))
    )
    session.handle_runtime_event(ConnectionChanged(ConnectionState.READY, adapter_id="usb:0"))

    session.connection_action()

    assert isinstance(runtime.commands[-1], ConnectSaved)
    session.connection_action()
    assert len([command for command in runtime.commands if isinstance(command, ConnectSaved)]) == 1
    session.handle_runtime_event(PairingProgress("ペアリング処理中"))
    assert session.presentation.model.warning == "ペアリング処理中"
    session.handle_runtime_event(
        ControllerError(
            category=ControllerErrorCategory.RECONNECT_FAILED,
            summary="接続に失敗しました",
            retryable=True,
            diagnostic_id="test-0001",
        )
    )
    assert session.presentation.model.connection_state is ConnectionState.ERROR
    session.connection_action()
    assert len([command for command in runtime.commands if isinstance(command, ConnectSaved)]) == 2
    assert session.toggle_capture() is True
    assert runtime.frames[-1].capture_active is True
    session.handle_runtime_event(ConnectionChanged(ConnectionState.CONNECTED, adapter_id="usb:0"))
    session.connection_action()
    session.connection_action()

    assert coordinator.is_captured is False
    assert runtime.frames[-1].capture_active is False
    disconnects = [command for command in runtime.commands if isinstance(command, Disconnect)]
    assert len(disconnects) == 1
    assert session.presentation.model.connection_state is ConnectionState.DISCONNECTING


def test_session_applies_saved_settings_to_the_live_input_publisher() -> None:
    settings = replace(
        AppSettings.default(),
        input=InputSettings(evaluation_interval_ms=16),
    )
    runtime = FakeRuntime()
    coordinator = make_coordinator(runtime)
    session = ApplicationSession(
        settings=settings,
        paths=SettingsPaths(Path("config"), Path("data"), Path("log")),
        repository=FakeRepository(SettingsLoadResult(settings, SettingsLoadStatus.LOADED)),
        runtime=runtime,
        coordinator=coordinator,
        publisher=coordinator.publisher,
    )

    assert session.open_settings(DialogKind.MAPPING) is True
    assert session.settings_modal.editor is not None
    session.settings_modal.editor.update_mouse(horizontal_sensitivity=2.5, invert_y=True)
    assert session.save_settings() is True
    assert session.settings.input.mouse.horizontal_sensitivity == 2.5
    assert session.settings.input.mouse.invert_y is True
    assert coordinator.publisher.evaluation_interval_ms == 16


def test_session_requires_pairing_confirmation_and_an_explicit_color_reconnect() -> None:
    settings = replace(
        AppSettings.default(),
        connection=replace(AppSettings.default().connection, adapter_id="usb:0"),
    )
    runtime = FakeRuntime()
    coordinator = make_coordinator(runtime)
    session = ApplicationSession(
        settings=settings,
        paths=SettingsPaths(Path("config"), Path("data"), Path("log")),
        repository=FakeRepository(SettingsLoadResult(settings, SettingsLoadStatus.LOADED)),
        runtime=runtime,
        coordinator=coordinator,
    )
    session.handle_runtime_event(
        AdaptersDiscovered((AdapterDescriptor("usb:0", "Adapter", "usb"),))
    )

    assert session.open_settings(DialogKind.CONNECTION) is True
    assert session.request_pairing() is True
    assert not any(isinstance(command, StartPairing) for command in runtime.commands)
    assert session.confirm_pairing() is True
    assert isinstance(runtime.commands[-1], StartPairing)

    session.handle_runtime_event(ConnectionChanged(ConnectionState.CONNECTED, adapter_id="usb:0"))
    assert session.open_settings(DialogKind.COLORS) is True
    assert session.settings_modal.editor is not None
    session.settings_modal.editor.update_color("body", "#ABCDEF")
    assert session.save_settings() is True
    assert session.presentation.model.color_reconnect_pending is True
    assert session.toggle_capture() is False

    session.defer_color_reconnect()
    assert not any(isinstance(command, RecreateWithColors) for command in runtime.commands)
    assert session.presentation.model.color_reconnect_pending is False

    assert session.open_settings(DialogKind.COLORS) is True
    assert session.settings_modal.editor is not None
    session.settings_modal.editor.update_color("buttons", "#ABCDEF")
    assert session.save_settings() is True
    session.request_color_reconnect()

    assert coordinator.is_captured is False
    assert isinstance(runtime.commands[-1], RecreateWithColors)


def test_session_reconfigures_diagnostic_logging_and_logs_only_error_category() -> None:
    settings = AppSettings.default()
    runtime = FakeRuntime()
    coordinator = make_coordinator(runtime)
    configured_levels: list[DiagnosticLevel] = []
    logged_categories: list[ControllerErrorCategory] = []
    session = ApplicationSession(
        settings=settings,
        paths=SettingsPaths(Path("config"), Path("data"), Path("log")),
        repository=FakeRepository(SettingsLoadResult(settings, SettingsLoadStatus.LOADED)),
        runtime=runtime,
        coordinator=coordinator,
        reconfigure_diagnostic_logging=configured_levels.append,
        log_controller_error=logged_categories.append,
    )

    assert session.open_settings(DialogKind.CONNECTION) is True
    assert session.settings_modal.editor is not None
    session.settings_modal.editor.update_connection(diagnostic_level=DiagnosticLevel.ERROR)
    assert session.save_settings() is True
    session.handle_runtime_event(
        ControllerError(
            category=ControllerErrorCategory.RECONNECT_FAILED,
            summary="bond=/private/secret.json",
            retryable=True,
            diagnostic_id="runtime-0001",
        )
    )

    assert configured_levels == [DiagnosticLevel.ERROR]
    assert logged_categories == [ControllerErrorCategory.RECONNECT_FAILED]


def make_coordinator(runtime: FakeRuntime) -> CaptureCoordinator:
    """Build a capture coordinator connected to the fake runtime sink."""
    return CaptureCoordinator(
        publisher=InputPublisher(clock=FakeClock(), sink=runtime),
        pointer_capture=FakeWindow(),
    )


@dataclass
class FakeRepository:
    """Repository fake that returns one predetermined load result."""

    result: SettingsLoadResult
    saved: list[AppSettings] = field(default_factory=list)

    def load(self) -> SettingsLoadResult:
        """Return the configured settings result."""
        return self.result

    def save(self, settings: AppSettings) -> None:
        """Record a settings save."""
        self.saved.append(settings)
