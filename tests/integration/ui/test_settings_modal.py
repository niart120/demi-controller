from dataclasses import dataclass, field
from pathlib import Path

import pytest

from demi.application.coordinator import CaptureCoordinator
from demi.application.dialogs import DialogKind, DialogManager
from demi.application.settings_modal import (
    SettingsModalController,
    settings_recovery_notice,
)
from demi.application.state import AppState
from demi.config.errors import SettingsPersistenceError
from demi.config.repository import SettingsLoadResult, SettingsLoadStatus
from demi.domain.controller import ControllerFrame
from demi.domain.settings import AppSettings
from demi.input.publisher import InputPublisher


@dataclass
class FakeClock:
    """Deterministic clock for settings modal integration tests."""

    now_ns: int = 1_000_000_000

    def monotonic_ns(self) -> int:
        """Return the configured timestamp."""
        return self.now_ns


@dataclass
class FakeSink:
    """Frame sink used to observe modal neutralization."""

    frames: list[ControllerFrame] = field(default_factory=list)

    def offer_frame(self, frame: ControllerFrame) -> None:
        """Record one published frame."""
        self.frames.append(frame)


@dataclass
class FakeWindow:
    """Window port recording exclusive mouse changes."""

    exclusive_calls: list[bool] = field(default_factory=list)

    def set_pointer_capture(self, enabled: bool) -> None:
        """Record a pointer capture transition."""
        self.exclusive_calls.append(enabled)


@dataclass
class FakeRepository:
    """Repository fake with a controllable save failure."""

    saved: AppSettings | None = None
    fail_save: bool = False

    def save(self, settings: AppSettings) -> None:
        """Store a settings snapshot or raise the configured error."""
        if self.fail_save:
            raise SettingsPersistenceError
        self.saved = settings


def make_controller(
    repository: FakeRepository,
) -> tuple[SettingsModalController, CaptureCoordinator, FakeSink, DialogManager]:
    """Create a modal controller with fake capture and repository boundaries."""
    sink = FakeSink()
    coordinator = CaptureCoordinator(
        publisher=InputPublisher(clock=FakeClock(), sink=sink),
        pointer_capture=FakeWindow(),
    )
    dialogs = DialogManager()
    return SettingsModalController(repository, coordinator, dialogs), coordinator, sink, dialogs


def test_modal_save_neutralizes_capture_and_reports_color_reconnect_requirement() -> None:
    repository = FakeRepository()
    controller, coordinator, sink, dialogs = make_controller(repository)
    assert coordinator.start_capture() is True
    coordinator.publisher.state.press_key("F")

    assert controller.open(DialogKind.COLORS, AppSettings.default(), connected=True) is True
    assert coordinator.app_state is AppState.CONFIGURING
    assert sink.frames[-1].capture_active is False

    assert controller.editor is not None
    controller.editor.update_color("body", "#ABCDEF")
    result = controller.save()

    assert result.reconnect_required is True
    assert repository.saved is not None
    assert repository.saved.controller_colors.body == "#ABCDEF"
    assert coordinator.app_state is AppState.IDLE
    assert dialogs.model.kind is DialogKind.NONE
    assert controller.editor is None


def test_modal_save_failure_keeps_draft_and_modal_open_until_cancel() -> None:
    repository = FakeRepository(fail_save=True)
    controller, coordinator, _, dialogs = make_controller(repository)

    assert controller.open(DialogKind.CONNECTION, AppSettings.default()) is True
    assert controller.editor is not None
    controller.editor.update_connection(adapter_id="usb:0")

    with pytest.raises(SettingsPersistenceError):
        controller.save()

    assert controller.editor is not None
    assert controller.editor.draft.connection.adapter_id == "usb:0"
    assert dialogs.model.kind is DialogKind.CONNECTION
    assert coordinator.app_state is AppState.CONFIGURING
    assert controller.cancel() is True
    assert coordinator.app_state is AppState.IDLE
    assert dialogs.model.kind is DialogKind.NONE


def test_recovered_settings_notice_contains_only_the_backup_name() -> None:
    result = SettingsLoadResult(
        settings=AppSettings.default(),
        status=SettingsLoadStatus.RECOVERED,
        backup_path=Path("settings.toml.broken-20260713-123456"),
    )

    notice = settings_recovery_notice(result)

    assert notice is not None
    assert "settings.toml.broken-20260713-123456" in notice
    assert "schema" not in notice
    assert (
        settings_recovery_notice(
            SettingsLoadResult(AppSettings.default(), SettingsLoadStatus.FIRST_RUN)
        )
        is None
    )


def test_recovered_settings_notice_reports_when_backup_could_not_be_created() -> None:
    notice = settings_recovery_notice(
        SettingsLoadResult(AppSettings.default(), SettingsLoadStatus.RECOVERED)
    )

    assert notice == "設定を復旧しました。破損ファイルの退避はできませんでした。"
