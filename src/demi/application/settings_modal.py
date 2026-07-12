"""Application orchestration for settings modal drafts."""

from dataclasses import dataclass
from typing import Protocol

from demi.config.repository import SettingsLoadResult, SettingsLoadStatus
from demi.domain.settings import AppSettings

from .coordinator import CaptureCoordinator
from .dialogs import DialogKind, DialogManager
from .settings_editor import SettingsEditor


class SettingsRepositoryPort(Protocol):
    """Repository operation required by the settings modal."""

    def save(self, settings: AppSettings) -> None:
        """Atomically save a validated settings snapshot."""


@dataclass(frozen=True, slots=True)
class SettingsSaveResult:
    """Result of committing one modal draft."""

    settings: AppSettings
    reconnect_required: bool


class SettingsModalController:
    """Coordinate one settings draft with modal and capture lifecycle state."""

    _EDITABLE_DIALOGS = frozenset({DialogKind.MAPPING, DialogKind.CONNECTION, DialogKind.COLORS})

    def __init__(
        self,
        repository: SettingsRepositoryPort,
        capture: CaptureCoordinator,
        dialogs: DialogManager,
    ) -> None:
        """Initialize a closed settings modal controller."""
        self._repository = repository
        self._capture = capture
        self._dialogs = dialogs
        self._editor: SettingsEditor | None = None
        self._original: AppSettings | None = None
        self._connected = False

    @property
    def editor(self) -> SettingsEditor | None:
        """Return the active draft editor, if a settings modal is open."""
        return self._editor

    def open(self, kind: DialogKind, settings: AppSettings, *, connected: bool = False) -> bool:
        """Open one editable settings modal and neutralize capture first."""
        if kind not in self._EDITABLE_DIALOGS or not self._dialogs.open(kind):
            return False
        if not self._capture.open_configuration():
            self._dialogs.close()
            return False
        self._editor = SettingsEditor(settings)
        self._original = settings
        self._connected = connected
        return True

    def cancel(self) -> bool:
        """Discard the active draft and return to idle state."""
        if self._editor is None:
            return False
        self._finish()
        return True

    def save(self) -> SettingsSaveResult:
        """Validate and atomically save the active draft.

        Raises:
            RuntimeError: No editable settings modal is open.
            DomainValueError: A reserved or invalid draft value is present.
            SettingsPersistenceError: The repository cannot commit the draft.
        """
        editor = self._editor
        original = self._original
        if editor is None or original is None:
            raise RuntimeError
        editor.validate()
        settings = editor.draft
        self._repository.save(settings)
        result = SettingsSaveResult(
            settings=settings,
            reconnect_required=self._connected
            and settings.controller_colors != original.controller_colors,
        )
        self._finish()
        return result

    def _finish(self) -> None:
        self._dialogs.close()
        self._capture.close_configuration()
        self._editor = None
        self._original = None
        self._connected = False


def settings_recovery_notice(result: SettingsLoadResult) -> str | None:
    """Build a safe user notice for a recovered settings document."""
    if result.status is not SettingsLoadStatus.RECOVERED:
        return None
    if result.backup_path is None:
        return "設定を復旧しました。破損ファイルの退避はできませんでした。"
    return f"設定を復旧しました。破損ファイルを {result.backup_path.name} として退避しました。"
