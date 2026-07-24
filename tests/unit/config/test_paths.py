from pathlib import Path

import platformdirs
import pytest

from demi.config.paths import SettingsPaths, resolve_paths


def test_resolve_paths_uses_the_project_platformdirs_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakePlatformDirs:
        user_config_path = "C:/config"
        user_data_path = "C:/data"
        user_log_path = "C:/logs"

        def __init__(self, *, appname: str, appauthor: bool) -> None:
            assert appname == "Project_Demi"
            assert appauthor is False

    monkeypatch.setattr(platformdirs, "PlatformDirs", FakePlatformDirs)

    paths = resolve_paths()

    assert paths.config_dir == Path("C:/config")
    assert paths.data_dir == Path("C:/data")
    assert paths.log_dir == Path("C:/logs")
    assert paths.settings_file == Path("C:/config/settings.toml")


def test_resolve_paths_uses_the_explicit_process_test_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("DEMI_TEST_PATH_ROOT", str(tmp_path))

    paths = resolve_paths()

    assert paths.config_dir == tmp_path / "config"
    assert paths.data_dir == tmp_path / "data"
    assert paths.log_dir == tmp_path / "logs"


def test_controller_profile_file_is_one_fixed_pro_controller_path() -> None:
    paths = SettingsPaths(
        config_dir=Path("C:/config"),
        data_dir=Path("C:/data"),
        log_dir=Path("C:/logs"),
    )

    assert paths.controller_profile_file == Path("C:/data/bonds/pro-controller/default.json")
    assert not hasattr(paths, "bond_file")
