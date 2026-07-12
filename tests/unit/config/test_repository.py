from pathlib import Path

import pytest

from demi.config import repository as repository_module
from demi.config.paths import SettingsPaths
from demi.config.repository import SettingsLoadStatus, SettingsPersistenceError, SettingsRepository
from demi.domain.settings import AppSettings


@pytest.fixture
def paths(tmp_path: Path) -> SettingsPaths:
    return SettingsPaths(
        config_dir=tmp_path / "config",
        data_dir=tmp_path / "data",
        log_dir=tmp_path / "logs",
    )


def test_missing_file_returns_first_run_defaults(paths: SettingsPaths) -> None:
    result = SettingsRepository(paths).load()

    assert result.status is SettingsLoadStatus.FIRST_RUN
    assert result.settings == AppSettings.default()
    assert result.backup_path is None


def test_save_then_load_returns_the_same_settings(paths: SettingsPaths) -> None:
    repository = SettingsRepository(paths)
    settings = AppSettings.default()

    repository.save(settings)
    result = repository.load()

    assert result.status is SettingsLoadStatus.LOADED
    assert result.settings == settings
    assert paths.settings_file.exists()


def test_corrupt_file_is_preserved_and_defaults_are_recovered(paths: SettingsPaths) -> None:
    paths.config_dir.mkdir(parents=True)
    corrupt = "schema = 'demi.settings/v1'\n[connection]\ntimeout_seconds = 0\n"
    paths.settings_file.write_text(corrupt, encoding="utf-8", newline="\n")

    result = SettingsRepository(paths).load()

    assert result.status is SettingsLoadStatus.RECOVERED
    assert result.settings == AppSettings.default()
    assert result.backup_path is not None
    assert result.backup_path.exists()
    assert result.backup_path.name.startswith("settings.toml.broken-")
    assert paths.settings_file.read_text(encoding="utf-8") == corrupt


def test_backup_failure_keeps_the_corrupt_file_and_reports_no_backup(
    paths: SettingsPaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths.config_dir.mkdir(parents=True)
    corrupt = "not = [valid"
    paths.settings_file.write_text(corrupt, encoding="utf-8", newline="\n")

    def fail_copy(*_args: object, **_kwargs: object) -> None:
        raise OSError

    monkeypatch.setattr(repository_module.shutil, "copy2", fail_copy)

    result = SettingsRepository(paths).load()

    assert result.status is SettingsLoadStatus.RECOVERED
    assert result.backup_path is None
    assert paths.settings_file.read_text(encoding="utf-8") == corrupt


def test_replace_failure_keeps_the_previous_settings_and_cleans_temp_file(
    paths: SettingsPaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = SettingsRepository(paths)
    repository.save(AppSettings.default())
    original = paths.settings_file.read_text(encoding="utf-8")

    def fail_replace(_source: Path, _target: Path) -> None:
        raise OSError

    monkeypatch.setattr(Path, "replace", fail_replace)

    with pytest.raises(SettingsPersistenceError):
        repository.save(AppSettings.default())

    assert paths.settings_file.read_text(encoding="utf-8") == original
    assert list(paths.config_dir.glob(".settings-*.tmp")) == []
