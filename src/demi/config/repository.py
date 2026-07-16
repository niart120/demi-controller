"""Settings file repository with backup and atomic replacement behavior."""

import os
import shutil
import tempfile
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from demi.domain.mapping import default_profile, is_diagnostic_target
from demi.domain.settings import AppSettings

from .codec import dumps_settings, loads_settings
from .errors import ConfigurationError, SettingsPersistenceError
from .paths import SettingsPaths


class SettingsLoadStatus(StrEnum):
    """Outcome categories returned by a settings load."""

    FIRST_RUN = "FIRST_RUN"
    LOADED = "LOADED"
    MIGRATED = "MIGRATED"
    RECOVERED = "RECOVERED"


@dataclass(frozen=True, slots=True)
class SettingsLoadResult:
    """Settings and lifecycle status returned from the repository."""

    settings: AppSettings
    status: SettingsLoadStatus
    backup_path: Path | None = None


class SettingsRepository:
    """Read and atomically write the user settings file."""

    def __init__(self, paths: SettingsPaths) -> None:
        """Create a repository rooted at resolved user directories."""
        self._paths = paths

    def load(self) -> SettingsLoadResult:
        """Load settings, distinguishing first run and recovery outcomes.

        Returns:
            A settings snapshot with FIRST_RUN, LOADED, MIGRATED, or RECOVERED
            status.

        Raises:
            SettingsPersistenceError: The settings file cannot be read.
        """
        if not self._paths.settings_file.exists():
            return SettingsLoadResult(AppSettings.default(), SettingsLoadStatus.FIRST_RUN)
        try:
            settings = loads_settings(self._paths.settings_file.read_text(encoding="utf-8"))
        except OSError as exc:
            raise SettingsPersistenceError from exc
        except ConfigurationError:
            return SettingsLoadResult(
                AppSettings.default(),
                SettingsLoadStatus.RECOVERED,
                self._backup_corrupt_file(),
            )
        settings, migrated = _with_missing_default_diagnostics(settings)
        return SettingsLoadResult(
            settings,
            SettingsLoadStatus.MIGRATED if migrated else SettingsLoadStatus.LOADED,
        )

    def save(self, settings: AppSettings) -> None:
        """Atomically replace the settings file with a validated snapshot.

        Args:
            settings: Validated snapshot to persist.

        Raises:
            SettingsPersistenceError: The temporary write or atomic replace
                fails. The previous settings file is left untouched.
        """
        temporary_path: Path | None = None
        try:
            self._paths.config_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                dir=self._paths.config_dir,
                prefix=".settings-",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                temporary_file.write(dumps_settings(settings))
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            temporary_path.replace(self._paths.settings_file)
        except OSError as exc:
            raise SettingsPersistenceError from exc
        finally:
            if temporary_path is not None:
                with suppress(OSError):
                    temporary_path.unlink(missing_ok=True)

    def _backup_corrupt_file(self) -> Path | None:
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        backup_path = self._paths.settings_file.with_name(
            f"{self._paths.settings_file.name}.broken-{timestamp}"
        )
        suffix = 1
        while backup_path.exists():
            backup_path = self._paths.settings_file.with_name(
                f"{self._paths.settings_file.name}.broken-{timestamp}-{suffix}"
            )
            suffix += 1
        try:
            shutil.copy2(self._paths.settings_file, backup_path)
        except OSError:
            return None
        return backup_path


def _with_missing_default_diagnostics(settings: AppSettings) -> tuple[AppSettings, bool]:
    diagnostic_bindings = tuple(
        binding for binding in default_profile().bindings if is_diagnostic_target(binding.target)
    )
    migrated = False
    profiles = []
    for candidate in settings.profiles:
        migrated_profile = candidate
        if candidate.id == "default" and candidate.builtin:
            existing_targets = {binding.target for binding in candidate.bindings}
            missing = tuple(
                binding for binding in diagnostic_bindings if binding.target not in existing_targets
            )
            if missing:
                migrated_profile = replace(
                    candidate,
                    bindings=(*candidate.bindings, *missing),
                )
                migrated = True
        profiles.append(migrated_profile)
    if not migrated:
        return settings, False
    return replace(settings, profiles=tuple(profiles)), True
