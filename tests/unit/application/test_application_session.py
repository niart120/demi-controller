from dataclasses import dataclass, field
from pathlib import Path

from demi.app import ApplicationSession
from demi.application.coordinator import CaptureCoordinator
from demi.application.state import ConnectionState
from demi.config.paths import SettingsPaths
from demi.config.repository import SettingsLoadResult, SettingsLoadStatus
from demi.controller.commands import ControllerCommand
from demi.controller.events import AdapterDescriptor, AdaptersDiscovered, ConnectionChanged
from demi.domain.controller import ControllerFrame
from demi.domain.settings import AppSettings
from demi.input.publisher import InputPublisher
from demi.ui.event_bridge import MainThreadEventBridge


@dataclass
class FakeClock:
    """Deterministic monotonic clock for session tests."""

    now_ns: int = 1

    def monotonic_ns(self) -> int:
        """Return the configured timestamp."""
        return self.now_ns


@dataclass
class FakeRuntime:
    """Runtime port recording commands posted by a session."""

    commands: list[ControllerCommand] = field(default_factory=list)

    def start(self) -> None:
        """Satisfy the runtime lifecycle protocol."""

    def offer_frame(self, frame: ControllerFrame) -> bool:
        """Accept a frame without a worker thread."""
        del frame
        return True

    def post(self, command: ControllerCommand) -> None:
        """Record an ordered command."""
        self.commands.append(command)

    def close(self) -> None:
        """Satisfy the runtime lifecycle protocol."""


@dataclass
class FakeRepository:
    """Settings repository fake sufficient for session construction."""

    saved: list[AppSettings] = field(default_factory=list)

    def load(self) -> SettingsLoadResult:
        """Return a deterministic first-run result."""
        return SettingsLoadResult(AppSettings.default(), SettingsLoadStatus.FIRST_RUN)

    def save(self, settings: AppSettings) -> None:
        """Record a settings snapshot."""
        self.saved.append(settings)


@dataclass
class FakeSink:
    """Frame sink required by the capture coordinator."""

    frames: list[ControllerFrame] = field(default_factory=list)

    def offer_frame(self, frame: ControllerFrame) -> None:
        """Record one frame."""
        self.frames.append(frame)


class FakeWindow:
    """Window boundary used by the capture coordinator."""

    def set_exclusive_mouse(self, exclusive: bool = True) -> None:
        """Accept capture transitions."""
        del exclusive


def make_session() -> ApplicationSession:
    """Create an application session without pyglet or a controller worker."""
    publisher = InputPublisher(clock=FakeClock(), sink=FakeSink())
    capture = CaptureCoordinator(publisher=publisher, window=FakeWindow())
    return ApplicationSession(
        runtime=FakeRuntime(),
        coordinator=capture,
        repository=FakeRepository(),
        paths=SettingsPaths(Path("config"), Path("data"), Path("log")),
        settings=AppSettings.default(),
    )


def test_worker_event_changes_presentation_only_when_the_main_thread_drains() -> None:
    session = make_session()
    bridge: MainThreadEventBridge[ConnectionChanged] = MainThreadEventBridge()
    event = ConnectionChanged(
        state=ConnectionState.CONNECTED,
        adapter_id="usb:0",
        summary="connected",
    )

    bridge.emit(event)

    assert session.presentation.model.connection_state is ConnectionState.STOPPED
    assert bridge.drain(session.handle_runtime_event) == 1
    assert session.presentation.model.connection_state is ConnectionState.CONNECTED
    assert session.presentation.model.adapter_label == "なし"


def test_adapter_events_are_reduced_to_safe_display_choices() -> None:
    session = make_session()

    session.handle_runtime_event(ConnectionChanged(state=ConnectionState.READY, adapter_id="usb:0"))
    session.handle_runtime_event(
        AdaptersDiscovered(
            adapters=(
                AdapterDescriptor(
                    id="usb:0",
                    display_name="Bluetooth adapter",
                    transport="usb",
                ),
            )
        )
    )

    assert session.presentation.model.adapters[0].id == "usb:0"
    assert session.presentation.model.adapters[0].label == "Bluetooth adapter"
