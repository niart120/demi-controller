import logging
from dataclasses import dataclass, field, replace
from pathlib import Path

from demi.app import ApplicationDependencies, ApplicationSession, _window_spec_for, run_application
from demi.application.coordinator import CaptureCoordinator
from demi.application.dialogs import DialogKind
from demi.application.presentation import PresentationStore
from demi.application.state import ConnectionState
from demi.config.paths import SettingsPaths
from demi.config.repository import SettingsLoadResult, SettingsLoadStatus
from demi.controller.commands import (
    ConnectSaved,
    Disconnect,
    DiscoverAdapters,
    RecreateWithColors,
    StartPairing,
)
from demi.controller.events import (
    AdapterDescriptor,
    AdaptersDiscovered,
    ConnectionChanged,
    ControllerError,
    ControllerErrorCategory,
    WatchdogNeutralized,
)
from demi.domain.controller import ControllerFrame
from demi.domain.settings import AppSettings, DiagnosticLevel, InputSettings
from demi.input.publisher import InputPublisher
from demi.ui.controller_view import ControllerView
from demi.ui.event_bridge import MainThreadEventBridge
from demi.ui.status_bar import StatusBar


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
    exclusive_mouse: list[bool] = field(default_factory=list)
    close_calls: int = 0

    def set_exclusive_mouse(self, exclusive: bool = True) -> None:
        """Record relative mouse changes."""
        self.exclusive_mouse.append(exclusive)

    def close(self) -> None:
        """Record native window teardown."""
        self.close_calls += 1


@dataclass
class FakeGui:
    """GUI loop fake that returns immediately."""

    runs: int = 0

    def run(self) -> None:
        """Record one GUI loop entry."""
        self.runs += 1


def test_application_runner_assembles_runtime_and_requests_discovery() -> None:
    paths = SettingsPaths(Path("config"), Path("data"), Path("log"))
    repository_result = SettingsLoadResult(AppSettings.default(), SettingsLoadStatus.FIRST_RUN)
    runtime = FakeRuntime()
    window = FakeWindow()
    gui = FakeGui()
    logger = logging.getLogger("demi-test-app")
    gui_kwargs: dict[str, object] = {}

    def create_gui(**kwargs: object) -> FakeGui:
        """Capture composition-root dependencies without entering pyglet."""
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

    assert runtime.started == 1
    assert len(runtime.commands) == 1
    assert isinstance(runtime.commands[0], DiscoverAdapters)
    assert gui.runs == 1
    assert runtime.closed == 1
    assert isinstance(gui_kwargs["session"], ApplicationSession)
    assert callable(gui_kwargs["event_pump"])
    assert gui_kwargs["actions"] is gui_kwargs["session"]
    assert callable(gui_kwargs["settings_provider"])
    assert gui_kwargs["dialogs"] is gui_kwargs["session"].dialogs
    assert callable(gui_kwargs["editor_provider"])


def test_application_runner_passes_a_main_thread_event_pump_to_the_gui() -> None:
    paths = SettingsPaths(Path("config"), Path("data"), Path("log"))
    repository_result = SettingsLoadResult(AppSettings.default(), SettingsLoadStatus.FIRST_RUN)
    runtime = FakeRuntime()
    window = FakeWindow()
    gui = FakeGui()
    captured: dict[str, object] = {}
    logger = logging.getLogger("demi-test-event-pump")

    def create_gui(**kwargs: object) -> FakeGui:
        captured.update(kwargs)
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

    assert isinstance(captured["bridge"], MainThreadEventBridge)
    assert callable(captured["event_pump"])
    assert isinstance(captured["presentation"], PresentationStore)


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
    assert session.toggle_capture() is True
    session.handle_runtime_event(ConnectionChanged(ConnectionState.CONNECTED, adapter_id="usb:0"))
    session.connection_action()

    assert coordinator.is_captured is False
    assert isinstance(runtime.commands[-1], Disconnect)


def test_session_applies_saved_settings_to_live_input_and_view_consumers() -> None:
    settings = replace(
        AppSettings.default(),
        input=InputSettings(evaluation_interval_ms=16),
    )
    runtime = FakeRuntime()
    coordinator = make_coordinator(runtime)
    view = ControllerView()
    status_bar = StatusBar()
    session = ApplicationSession(
        settings=settings,
        paths=SettingsPaths(Path("config"), Path("data"), Path("log")),
        repository=FakeRepository(SettingsLoadResult(settings, SettingsLoadStatus.LOADED)),
        runtime=runtime,
        coordinator=coordinator,
        publisher=coordinator.publisher,
        view=view,
        status_bar=status_bar,
    )

    assert session.open_settings(DialogKind.MAPPING) is True
    assert session.settings_modal.editor is not None
    session.settings_modal.editor.update_mouse(horizontal_sensitivity=2.5, invert_y=True)
    assert session.save_settings() is True
    assert session.settings.input.mouse.horizontal_sensitivity == 2.5
    assert session.settings.input.mouse.invert_y is True
    assert coordinator.publisher.evaluation_interval_ms == 16
    assert status_bar.model.evaluation_interval_ms == 16

    assert session.open_settings(DialogKind.COLORS) is True
    assert session.settings_modal.editor is not None
    session.settings_modal.editor.update_color("body", "#ABCDEF")
    assert session.save_settings() is True

    assert view.colors.body == "#ABCDEF"


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
        window=FakeWindow(),
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
