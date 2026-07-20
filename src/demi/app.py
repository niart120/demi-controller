"""Application composition root for Project_Demi."""

from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING, Protocol, TypeGuard, runtime_checkable

from demi.application.coordinator import (
    CaptureCoordinator,
    CaptureFailure,
    PointerCapturePort,
    RelativePointerCapturePort,
)
from demi.application.dialogs import DialogKind, DialogManager
from demi.application.frame_fanout import (
    ControllerColorPreviewPort,
    ControllerFrameFanout,
    FramePreviewPort,
)
from demi.application.presentation import AdapterOption, PresentationStore
from demi.application.settings_modal import SettingsModalController, settings_recovery_notice
from demi.application.shutdown import ApplicationShutdownCoordinator
from demi.application.state import ConnectionState
from demi.application.ui_state import ApplicationUiSnapshot
from demi.config.errors import SettingsPersistenceError
from demi.config.paths import resolve_paths
from demi.config.repository import SettingsRepository
from demi.controller.adapter import RuntimeEventSink
from demi.controller.commands import (
    ConnectSaved,
    Disconnect,
    DiscoverAdapters,
    RecreateWithColors,
    StartPairing,
)
from demi.controller.events import (
    AdaptersDiscovered,
    ConnectionChanged,
    ControllerError,
    ControllerErrorCategory,
    PairingProgress,
    RuntimeStopped,
    WatchdogNeutralized,
)
from demi.controller.runtime import ControllerRuntime
from demi.controller.swbt_adapter import SwbtControllerAdapter
from demi.domain.errors import DomainValueError
from demi.domain.settings import DiagnosticLevel, UiLanguage
from demi.input.publisher import InputPublisher

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import TracebackType

    from demi.config.paths import SettingsPaths
    from demi.config.repository import SettingsLoadResult
    from demi.controller.adapter import ControllerAdapterFactory
    from demi.controller.commands import ControllerCommand
    from demi.controller.events import (
        RuntimeEvent,
    )
    from demi.controller.watchdog import WatchdogClock
    from demi.domain.controller import ControllerFrame
    from demi.domain.mapping import InputProfile
    from demi.domain.settings import AppSettings, WindowSettings
    from demi.ui.application import QtApplicationRunner
    from demi.ui.event_bridge import QtRuntimeEventBridge
    from demi.ui.main_window import MainWindow


class Clock(Protocol):
    """Monotonic clock consumed by input and controller boundaries."""

    def monotonic_ns(self) -> int:
        """Return monotonic time in nanoseconds."""


class SettingsRepositoryPort(Protocol):
    """Settings operations required by the composition root."""

    def load(self) -> SettingsLoadResult:
        """Load settings and their recovery status."""

    def save(self, settings: AppSettings) -> None:
        """Persist a validated settings snapshot."""


class RuntimePort(Protocol):
    """Controller operations owned by the desktop application."""

    def start(self) -> None:
        """Start the controller worker."""

    def post(self, command: ControllerCommand) -> None:
        """Post one ordered controller command."""

    def offer_frame(self, frame: ControllerFrame) -> bool:
        """Offer the newest input frame to the controller worker."""

    def close(self) -> None:
        """Close the controller worker and join its thread."""


@dataclass(frozen=True, slots=True)
class WindowSpec:
    """Saved window dimensions supplied to a desktop UI implementation."""

    width: int
    height: int
    maximized: bool
    language: UiLanguage = UiLanguage.ENGLISH


class WindowPort(PointerCapturePort, Protocol):
    """Window operations required by capture coordination."""

    def window_state(self) -> WindowSettings | None:
        """Return a valid state captured before native window destruction."""

    def close(self) -> bool | None:
        """Request native window closure."""


@runtime_checkable
class InputCaptureSetupPort(Protocol):
    """Optional outer UI boundary that installs its own input adapters."""

    def configure_input(
        self,
        *,
        publisher: InputPublisher,
        coordinator: CaptureCoordinator,
    ) -> None:
        """Connect a publisher and coordinator after application assembly."""


class GuiPort(Protocol):
    """GUI loop started after application assembly succeeds."""

    def run(self) -> int:
        """Enter the GUI event loop and return its exit status."""


class GuiUnavailableError(RuntimeError):
    """Signal that no desktop UI implementation is available yet."""


class DiscardRuntimeEventSink(RuntimeEventSink):
    """Discard worker events until a replacement GUI owns their delivery."""

    def emit(self, event: RuntimeEvent) -> None:
        """Discard one runtime event without invoking a GUI boundary."""
        del event


class RuntimeFactory(Protocol):
    """Create a controller runtime at the composition boundary."""

    def __call__(
        self,
        *,
        adapter_factory: ControllerAdapterFactory,
        event_sink: RuntimeEventSink,
        clock: WatchdogClock,
    ) -> RuntimePort:
        """Create an unstarted runtime."""


class SystemClock:
    """Production monotonic clock backed by the standard library."""

    def monotonic_ns(self) -> int:
        """Return the current monotonic time in nanoseconds."""
        return time.perf_counter_ns()


class ApplicationSession:
    """Own main-thread settings, presentation, and runtime command decisions."""

    def __init__(
        self,
        *,
        settings: AppSettings,
        paths: SettingsPaths,
        repository: SettingsRepositoryPort,
        runtime: RuntimePort,
        coordinator: CaptureCoordinator,
        loaded: SettingsLoadResult | None = None,
        publisher: InputPublisher | None = None,
        reconfigure_diagnostic_logging: Callable[[DiagnosticLevel], None] | None = None,
        log_controller_error: Callable[[ControllerErrorCategory], None] | None = None,
    ) -> None:
        """Create a main-thread session before the worker starts.

        Args:
            settings: Validated settings selected for this process.
            paths: User-local configuration, data, and log paths.
            repository: Settings persistence boundary.
            runtime: Ordered controller command boundary.
            coordinator: Main-thread capture lifecycle owner.
            loaded: Optional load result used for a safe recovery notice.
            publisher: Live input publisher updated after settings saves.
            reconfigure_diagnostic_logging: Optional callback that applies a
                saved diagnostic logging threshold.
            log_controller_error: Optional safe category-only error logger.
        """
        self._settings = settings
        self._paths = paths
        self._repository = repository
        self._runtime = runtime
        self._coordinator = coordinator
        self._publisher = publisher if publisher is not None else coordinator.publisher
        self._reconfigure_diagnostic_logging = reconfigure_diagnostic_logging
        self._log_controller_error = log_controller_error
        self._dialogs = DialogManager()
        self._settings_modal = SettingsModalController(repository, coordinator, self._dialogs)
        self._presentation = PresentationStore()
        self._connection_retryable = True
        self._startup_reconnect_pending = settings.connection.reconnect_on_start and bool(
            settings.connection.adapter_id
        )
        self._startup_reconnect_discovery_complete = False
        if loaded is not None:
            self._presentation.set_recovery_notice(settings_recovery_notice(loaded))
        self._apply_live_settings(settings)

    @property
    def settings(self) -> AppSettings:
        """Return the current validated settings snapshot."""
        return self._settings

    @property
    def dialogs(self) -> DialogManager:
        """Return the single-modal state owner used by the GUI."""
        return self._dialogs

    @property
    def settings_modal(self) -> SettingsModalController:
        """Return the settings draft controller used by the GUI."""
        return self._settings_modal

    @property
    def presentation(self) -> PresentationStore:
        """Return main-thread presentation state for the GUI."""
        return self._presentation

    @property
    def ui_snapshot(self) -> ApplicationUiSnapshot:
        """Return the current framework-independent state for the main window."""
        presentation = self._presentation.model
        return ApplicationUiSnapshot(
            application_state=self._coordinator.app_state,
            connection_state=presentation.connection_state,
            adapter_label=presentation.adapter_label,
            adapters=presentation.adapters,
            dialog_open=self._dialogs.model.visible,
            preview_only=presentation.connection_state is not ConnectionState.CONNECTED,
            warning=presentation.warning,
            error=presentation.error,
            color_reconnect_pending=presentation.color_reconnect_pending,
            connection_retryable=self._connection_retryable,
        )

    def begin(self) -> None:
        """Request initial adapter discovery after the runtime has started."""
        self._presentation.set_connection(ConnectionState.STARTING)
        self._runtime.post(DiscoverAdapters())

    def handle_runtime_event(self, event: RuntimeEvent) -> None:
        """Reduce one worker event on the GUI main thread.

        Args:
            event: Immutable event drained from the thread-safe event bridge.
        """
        if isinstance(event, AdaptersDiscovered):
            adapters = tuple(
                AdapterOption(descriptor.id, descriptor.display_name)
                for descriptor in event.adapters
            )
            self._presentation.set_adapters(adapters)
            self._startup_reconnect_discovery_complete = True
        elif isinstance(event, ConnectionChanged):
            if event.state in {ConnectionState.READY, ConnectionState.CONNECTED}:
                self._connection_retryable = True
            self._presentation.set_connection(
                event.state,
                adapter_id=event.adapter_id,
                adapter_label=self._adapter_label(event.adapter_id),
            )
            if event.state is ConnectionState.READY and self._startup_reconnect_discovery_complete:
                self._start_saved_reconnect_once()
        elif isinstance(event, ControllerError):
            self._coordinator.neutralize_input()
            self._connection_retryable = event.retryable
            self._presentation.set_connection(ConnectionState.ERROR)
            self._presentation.set_error(_safe_error_message(event.category))
            if self._log_controller_error is not None:
                self._log_controller_error(event.category)
        elif isinstance(event, WatchdogNeutralized):
            if (
                self._coordinator.is_captured
                and event.capture_epoch == self._coordinator.capture_epoch
            ):
                self._coordinator.neutralize_input()
                self._presentation.set_warning("Input monitoring timed out")
        elif isinstance(event, PairingProgress):
            self._presentation.set_warning(event.summary)
        elif isinstance(event, RuntimeStopped):
            self._coordinator.begin_shutdown()
            self._presentation.set_connection(ConnectionState.STOPPED)

    def open_settings(self, kind: DialogKind) -> bool:
        """Open one editable settings dialog through the capture coordinator.

        Args:
            kind: Editable dialog requested by the GUI.

        Returns:
            Whether the dialog was opened.
        """
        return self._settings_modal.open(
            kind,
            self._settings,
            connected=self._presentation.model.connection_state is ConnectionState.CONNECTED,
        )

    def toggle_capture(self) -> bool:
        """Toggle capture unless an editable modal owns application input.

        Returns:
            Whether the capture transition was accepted.
        """
        if self._dialogs.model.visible or self._presentation.model.color_reconnect_pending:
            return False
        return self._coordinator.toggle_capture()

    def report_capture_failure(self, failure: CaptureFailure) -> None:
        """Show a safe relative-pointer failure warning in the presentation model.

        Args:
            failure: Category reported by the capture lifecycle coordinator.
        """
        messages = {
            CaptureFailure.RELATIVE_POINTER_REGISTRATION: "Could not start relative mouse input",
            CaptureFailure.RELATIVE_POINTER_READ: "Relative mouse input stopped",
            CaptureFailure.POINTER_CAPTURE: "Could not start input capture",
        }
        self._presentation.set_warning(messages[failure])

    def connection_action(self) -> None:
        """Perform the state-dependent toolbar connection action."""
        state = self._presentation.model.connection_state
        if state is ConnectionState.CONNECTED:
            self._coordinator.stop_capture()
            self._presentation.set_connection(ConnectionState.DISCONNECTING)
            self._runtime.post(Disconnect())
            return
        if state is ConnectionState.ERROR and not self._connection_retryable:
            return
        if state not in {ConnectionState.READY, ConnectionState.ERROR}:
            return
        connection = self._settings.connection
        if not connection.adapter_id or not self._presentation.has_adapter(connection.adapter_id):
            self._presentation.set_warning("Select a USB adapter to connect")
            self.open_settings(DialogKind.CONNECTION)
            return
        self._presentation.acknowledge_error()
        self._runtime.post(
            ConnectSaved(
                adapter_id=connection.adapter_id,
                bond_path=self._paths.bond_file(connection.bond_slot),
                timeout_seconds=connection.timeout_seconds,
                colors=self._settings.controller_colors,
            )
        )
        self._presentation.set_connection(
            ConnectionState.CONNECTING,
            adapter_id=connection.adapter_id,
            adapter_label=self._adapter_label(connection.adapter_id),
        )

    def save_settings(self) -> bool:
        """Save the open draft and apply it to live main-thread consumers.

        Returns:
            ``True`` after a successful save; ``False`` when the draft remains
            open for correction after a validation or persistence failure.
        """
        try:
            result = self._settings_modal.save()
        except (DomainValueError, SettingsPersistenceError):
            self._presentation.set_warning("Could not save settings")
            return False
        previous_diagnostic_level = self._settings.connection.diagnostic_level
        self._apply_live_settings(result.settings)
        if (
            result.settings.connection.diagnostic_level is not previous_diagnostic_level
            and self._reconfigure_diagnostic_logging is not None
        ):
            self._reconfigure_diagnostic_logging(result.settings.connection.diagnostic_level)
        if result.reconnect_required:
            self._presentation.set_color_reconnect_pending(True)
            self._presentation.set_warning(
                "Display colors updated. Reconnect to apply them to the target device"
            )
        return True

    def cancel_settings(self) -> bool:
        """Discard the current modal draft without changing live settings."""
        return self._settings_modal.cancel()

    def request_pairing(self) -> bool:
        """Move an editable connection draft to its explicit confirmation step."""
        if (
            self._dialogs.model.kind is not DialogKind.CONNECTION
            or self._settings_modal.editor is None
        ):
            return False
        return self._dialogs.replace(DialogKind.PAIRING_CONFIRMATION)

    def rescan_adapters(self) -> None:
        """Request fresh adapter discovery while a connection draft is open."""
        if self._dialogs.model.kind not in {
            DialogKind.CONNECTION,
            DialogKind.PAIRING_CONFIRMATION,
        }:
            return
        self._runtime.post(DiscoverAdapters())

    def cancel_pairing(self) -> bool:
        """Return a pairing confirmation to its editable connection draft."""
        if self._dialogs.model.kind is not DialogKind.PAIRING_CONFIRMATION:
            return False
        return self._dialogs.replace(DialogKind.CONNECTION)

    def confirm_pairing(self) -> bool:
        """Persist a confirmed draft and post one explicit pairing command."""
        editor = self._settings_modal.editor
        if self._dialogs.model.kind is not DialogKind.PAIRING_CONFIRMATION or editor is None:
            return False
        connection = editor.draft.connection
        if not connection.adapter_id or not self._presentation.has_adapter(connection.adapter_id):
            self._presentation.set_warning("Select a USB adapter to pair")
            self._dialogs.replace(DialogKind.CONNECTION)
            return False
        if not self.save_settings():
            return False
        self._runtime.post(
            StartPairing(
                adapter_id=self._settings.connection.adapter_id,
                bond_path=self._paths.bond_file(self._settings.connection.bond_slot),
                timeout_seconds=self._settings.connection.timeout_seconds,
                colors=self._settings.controller_colors,
            )
        )
        self._presentation.set_connection(
            ConnectionState.CONNECTING,
            adapter_id=self._settings.connection.adapter_id,
            adapter_label=self._adapter_label(self._settings.connection.adapter_id),
        )
        return True

    def defer_color_reconnect(self) -> None:
        """Keep saved colors locally without changing the connected controller."""
        self._presentation.set_color_reconnect_pending(False)

    def request_color_reconnect(self) -> bool:
        """Neutralize capture and explicitly recreate a connected controller's colors."""
        if not self._presentation.model.color_reconnect_pending:
            return False
        self._coordinator.stop_capture()
        self._presentation.set_color_reconnect_pending(False)
        self._runtime.post(RecreateWithColors(colors=self._settings.controller_colors))
        return True

    def _apply_live_settings(self, settings: AppSettings) -> None:
        self._settings = settings
        self._publisher.reconfigure(
            profile=_active_profile(settings),
            mouse_settings=settings.input.mouse,
            circular_limit=settings.input.circular_stick_limit,
            evaluation_interval_ms=settings.input.evaluation_interval_ms,
        )

    def _start_saved_reconnect_once(self) -> None:
        if not self._startup_reconnect_pending:
            return
        self._startup_reconnect_pending = False
        connection = self._settings.connection
        if not self._presentation.has_adapter(connection.adapter_id):
            self._presentation.set_warning("Saved USB adapter not found")
            return
        self._runtime.post(
            ConnectSaved(
                adapter_id=connection.adapter_id,
                bond_path=self._paths.bond_file(connection.bond_slot),
                timeout_seconds=connection.timeout_seconds,
                colors=self._settings.controller_colors,
            )
        )
        self._presentation.set_connection(
            ConnectionState.CONNECTING,
            adapter_id=connection.adapter_id,
            adapter_label=self._adapter_label(connection.adapter_id),
        )

    def _adapter_label(self, adapter_id: str | None) -> str:
        if adapter_id is None:
            return self._presentation.model.adapter_label
        for adapter in self._presentation.model.adapters:
            if adapter.id == adapter_id:
                return adapter.label
        return "None"


@dataclass(frozen=True, slots=True)
class ApplicationDependencies:
    """Injectable outer-boundary factories used to assemble the desktop app."""

    paths_resolver: Callable[[], SettingsPaths]
    repository_factory: Callable[[SettingsPaths], SettingsRepositoryPort]
    runtime_factory: RuntimeFactory
    window_factory: Callable[[WindowSpec], WindowPort]
    gui_factory: Callable[..., GuiPort]
    clock: Clock
    logger_configurer: Callable[[SettingsPaths, DiagnosticLevel], logging.Logger]

    @classmethod
    def default(cls) -> ApplicationDependencies:
        """Return production factories without creating a display on import."""
        runner: QtApplicationRunner | None = None

        def create_window(spec: WindowSpec) -> WindowPort:
            """Create the Qt application and its main window only for GUI startup."""
            nonlocal runner

            from demi.ui.application import QtApplicationRunner  # noqa: I001, PLC0415 - GUI起動時だけQtをimportする。

            runner = QtApplicationRunner()
            return runner.create_main_window(spec)

        def create_gui(
            *,
            window: WindowPort,
            on_shutdown_requested: Callable[[WindowSettings | None], bool],
            **_kwargs: object,
        ) -> GuiPort:
            """Return the runner created with the application main window."""
            active_runner = runner
            if active_runner is None:
                raise GuiUnavailableError
            active_runner.configure(
                window=window,
                on_shutdown_requested=on_shutdown_requested,
            )
            return active_runner

        return cls(
            paths_resolver=resolve_paths,
            repository_factory=SettingsRepository,
            runtime_factory=_create_runtime,
            window_factory=create_window,
            gui_factory=create_gui,
            clock=SystemClock(),
            logger_configurer=configure_logging,
        )


def configure_logging(paths: SettingsPaths, level: DiagnosticLevel) -> logging.Logger:
    """Configure the local rotating Project_Demi log.

    Args:
        paths: User-local paths selected for the current operating system.
        level: Threshold loaded from validated application settings.

    Returns:
        Configured application logger.

    Raises:
        OSError: The user-local log directory cannot be created or opened.
    """
    paths.log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("demi")
    logger.setLevel(getattr(logging, level.value))
    logger.propagate = False
    for handler in tuple(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    file_handler = RotatingFileHandler(
        paths.log_dir / "project-demi.log",
        maxBytes=1_048_576,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(file_handler)
    return logger


def run_application(dependencies: ApplicationDependencies | None = None) -> int:
    """Assemble, run, and safely close the desktop application.

    Args:
        dependencies: Optional outer-boundary factories for tests.

    Returns:
        Zero after normal GUI shutdown, otherwise a nonzero startup status.
    """
    selected_dependencies = (
        dependencies if dependencies is not None else ApplicationDependencies.default()
    )
    runtime: RuntimePort | None = None
    window: WindowPort | None = None
    shutdown: ApplicationShutdownCoordinator | None = None
    publisher: InputPublisher | None = None
    logger: logging.Logger | None = None
    ui_deactivator: Callable[[], None] | None = None
    ui_deactivated = False
    exit_status = 1
    try:
        paths = selected_dependencies.paths_resolver()
        logger = selected_dependencies.logger_configurer(paths, DiagnosticLevel.INFO)
        repository = selected_dependencies.repository_factory(paths)
        loaded = repository.load()
        settings = loaded.settings

        def reconfigure_diagnostic_logging(level: DiagnosticLevel) -> None:
            """Apply one validated diagnostic threshold to the local logger."""
            nonlocal logger
            logger = selected_dependencies.logger_configurer(paths, level)

        def log_controller_error(category: ControllerErrorCategory) -> None:
            """Record a safe controller error category without worker details."""
            if logger is not None:
                logger.error("Controller error: %s", category.value)

        if settings.connection.diagnostic_level is not DiagnosticLevel.INFO:
            reconfigure_diagnostic_logging(settings.connection.diagnostic_level)
        logger.info("Starting Project_Demi")

        spec = _window_spec_for(settings)
        window = selected_dependencies.window_factory(spec)
        event_sink: RuntimeEventSink = DiscardRuntimeEventSink()
        event_router = None
        event_bridge: QtRuntimeEventBridge | None = None
        if _is_qt_main_window(window):
            from demi.ui.application import QtApplicationEventRouter  # noqa: PLC0415
            from demi.ui.event_bridge import QtRuntimeEventBridge  # noqa: PLC0415

            event_router = QtApplicationEventRouter(window)
            event_bridge = QtRuntimeEventBridge(event_router.handle_runtime_event, parent=window)
            event_sink = event_bridge
        runtime = selected_dependencies.runtime_factory(
            adapter_factory=SwbtControllerAdapter,
            event_sink=event_sink,
            clock=selected_dependencies.clock,
        )
        if isinstance(window, ControllerColorPreviewPort):
            window.set_controller_colors(settings.controller_colors)
        preview = window if isinstance(window, FramePreviewPort) else None
        frame_sink = ControllerFrameFanout(runtime=runtime, preview=preview)
        publisher = InputPublisher(
            clock=selected_dependencies.clock,
            sink=frame_sink,
            profile=_active_profile(settings),
            mouse_settings=settings.input.mouse,
            circular_limit=settings.input.circular_stick_limit,
            evaluation_interval_ms=settings.input.evaluation_interval_ms,
        )
        relative_pointer_capture = (
            window if isinstance(window, RelativePointerCapturePort) else None
        )
        coordinator = CaptureCoordinator(
            publisher=publisher,
            pointer_capture=window,
            relative_pointer_capture=relative_pointer_capture,
        )
        if isinstance(window, InputCaptureSetupPort):
            window.configure_input(publisher=publisher, coordinator=coordinator)
        if logger is not None and _is_qt_main_window(window):
            try:
                from demi.ui.diagnostics import collect_support_diagnostics  # noqa: PLC0415

                logger.info(
                    "%s",
                    collect_support_diagnostics(window.relative_pointer_capability).log_message,
                )
            except Exception as error:  # noqa: BLE001 - diagnostics must not prevent application startup.
                logger.error(  # noqa: TRY400 - diagnostics may expose package paths in traceback.
                    "Support diagnostics unavailable: %s",
                    type(error).__name__,
                )
        session = ApplicationSession(
            settings=settings,
            paths=paths,
            repository=repository,
            runtime=runtime,
            coordinator=coordinator,
            loaded=loaded,
            publisher=publisher,
            reconfigure_diagnostic_logging=reconfigure_diagnostic_logging,
            log_controller_error=log_controller_error,
        )
        if event_router is not None:
            event_router.bind(session)
        coordinator.set_capture_failure_reporter(session.report_capture_failure)
        shutdown = ApplicationShutdownCoordinator(
            capture=coordinator,
            runtime=runtime,
            repository=repository,
            settings_provider=lambda: session.settings,
            window_state_provider=lambda: _window_state_for(window),
            report_error=lambda stage, error: _log_shutdown_error(logger, stage, error),
        )

        def deactivate_ui() -> None:
            """Disable Qt callbacks before worker shutdown or native close."""
            nonlocal ui_deactivated
            if ui_deactivated:
                return
            ui_deactivated = True
            if event_bridge is not None:
                event_bridge.deactivate()
            if event_router is not None:
                event_router.deactivate()
            if _is_qt_main_window(window):
                window.begin_shutdown()

        ui_deactivator = deactivate_ui

        def request_shutdown(window_state: WindowSettings | None) -> bool:
            """Run ordered shutdown and allow native close only after success."""
            deactivate_ui()
            shutdown.request(window_state)
            return not shutdown.failed

        if event_router is not None:

            def shutdown_after_runtime_stopped() -> None:
                """Complete a worker-initiated shutdown before closing the window."""
                if shutdown.requested:
                    return
                if request_shutdown(None):
                    _close_window(window, logger)

            event_router.set_runtime_stopped_handler(shutdown_after_runtime_stopped)

        runtime.start()
        session.begin()
        if event_router is not None:
            event_router.refresh()

        gui = selected_dependencies.gui_factory(
            window=window,
            coordinator=coordinator,
            loaded=loaded,
            paths=paths,
            repository=repository,
            runtime=runtime,
            session=session,
            actions=session,
            presentation=session.presentation,
            settings_provider=lambda: session.settings,
            dialogs=session.dialogs,
            editor_provider=lambda: session.settings_modal.editor,
            settings=settings,
            on_shutdown_requested=request_shutdown,
            window_maximized=settings.window.maximized,
        )
        main_thread_failed = False
        original_exception_hook = sys.excepthook

        def handle_main_thread_exception(
            error_type: type[BaseException],
            error: BaseException,
            traceback: TracebackType | None,
        ) -> None:
            """Close safely after a Qt callback reports an ordinary exception."""
            nonlocal main_thread_failed
            if not issubclass(error_type, Exception):
                original_exception_hook(error_type, error, traceback)
                return
            if main_thread_failed:
                return
            main_thread_failed = True
            if logger is not None:
                logger.error(
                    "Project_Demi main-thread failure: %s",
                    error_type.__name__,
                )
            if request_shutdown(None):
                _close_window(window, logger)

        sys.excepthook = handle_main_thread_exception
        try:
            exit_status = gui.run()
        finally:
            sys.excepthook = original_exception_hook
        if main_thread_failed:
            exit_status = 1
    except Exception as error:  # noqa: BLE001 - CLI boundary converts startup failures.
        if logger is not None:
            logger.error(  # noqa: TRY400 - exception text may contain private paths or bond data.
                "Project_Demi startup failed: %s",
                type(error).__name__,
            )
        sys.stderr.write("Project_Demi failed to start.\n")
        exit_status = 1
    finally:
        if shutdown is not None:
            if ui_deactivator is not None:
                ui_deactivator()
            already_requested = shutdown.requested
            shutdown.request()
            if shutdown.failed:
                exit_status = 1
            if not already_requested:
                _close_window(window, logger)
        else:
            if runtime is not None:
                try:
                    runtime.close()
                except Exception as error:  # noqa: BLE001 - preserve the primary exit status.
                    exit_status = 1
                    if logger is not None:
                        logger.error(  # noqa: TRY400 - exception text may contain private paths or bond data.
                            "Project_Demi shutdown failed: %s",
                            type(error).__name__,
                        )
            _close_window(window, logger)
    if logger is not None and publisher is not None:
        timing = publisher.timing_metrics
        logger.info(
            "input timing samples=%d mean_ms=%s p95_ms=%s p99_ms=%s",
            timing.sample_count,
            timing.mean_interval_ms,
            timing.p95_interval_ms,
            timing.p99_interval_ms,
        )
    if logger is not None and exit_status == 0:
        logger.info("Project_Demi stopped normally")
    return exit_status


def _window_state_for(window: WindowPort | None) -> WindowSettings | None:
    """Capture a framework-independent state without native private APIs."""
    if window is None:
        return None
    return window.window_state()


def _is_qt_main_window(window: WindowPort) -> TypeGuard[MainWindow]:
    """Return whether a window can own Qt runtime-event delivery."""
    from demi.ui.main_window import MainWindow  # noqa: PLC0415 - GUI起動時だけQtをimportする。

    return isinstance(window, MainWindow)


def _close_window(window: WindowPort | None, logger: logging.Logger | None) -> None:
    """Close a created native window without masking an earlier startup error."""
    if window is None:
        return
    try:
        window.close()
    except Exception as error:  # noqa: BLE001 - process cleanup remains best effort.
        _log_shutdown_error(logger, "window close", error)


def _log_shutdown_error(
    logger: logging.Logger | None,
    stage: str,
    error: Exception,
) -> None:
    """Record a safe shutdown error without exposing adapter or bond details."""
    if logger is not None:
        logger.error("Project_Demi %s failed: %s", stage, type(error).__name__)


def _create_runtime(
    *,
    adapter_factory: ControllerAdapterFactory,
    event_sink: RuntimeEventSink,
    clock: WatchdogClock,
) -> RuntimePort:
    return ControllerRuntime(
        adapter_factory=adapter_factory,
        event_sink=event_sink,
        clock=clock,
    )


def _window_spec_for(settings: AppSettings) -> WindowSpec:
    return WindowSpec(
        width=settings.window.width,
        height=settings.window.height,
        maximized=settings.window.maximized,
        language=settings.ui.language,
    )


def _active_profile(settings: AppSettings) -> InputProfile:
    for profile in settings.profiles:
        if profile.id == settings.active_profile:
            return profile
    raise RuntimeError


def _safe_error_message(category: ControllerErrorCategory) -> str:
    messages = {
        ControllerErrorCategory.ADAPTER_NOT_FOUND: "USB adapter not found",
        ControllerErrorCategory.ADAPTER_OPEN_FAILED: "Could not open USB adapter",
        ControllerErrorCategory.BOND_NOT_FOUND: "Saved bond not found",
        ControllerErrorCategory.PAIRING_TIMEOUT: "Pairing timed out",
        ControllerErrorCategory.RECONNECT_FAILED: "Could not reconnect saved connection",
        ControllerErrorCategory.CONNECTION_LOST: "Connection lost",
        ControllerErrorCategory.INVALID_INPUT: "Could not apply input to controller",
        ControllerErrorCategory.SHUTDOWN_FAILED: "Part of shutdown failed",
        ControllerErrorCategory.UNEXPECTED: "Unexpected controller error",
    }
    return messages[category]
