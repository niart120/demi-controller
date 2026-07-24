"""OS-specific settings and bond paths."""

import os
from dataclasses import dataclass
from pathlib import Path

import platformdirs


@dataclass(frozen=True, slots=True)
class SettingsPaths:
    """Resolved user directories used by settings, data, and logs."""

    config_dir: Path
    data_dir: Path
    log_dir: Path

    @property
    def settings_file(self) -> Path:
        """Return the current settings TOML path."""
        return self.config_dir / "settings.toml"

    @property
    def controller_profile_file(self) -> Path:
        """Return the one fixed Pro Controller connection-profile path."""
        return self.data_dir / "bonds" / "pro-controller" / "default.json"


def resolve_paths() -> SettingsPaths:
    """Resolve Project_Demi directories through platformdirs.

    Returns:
        Config, data, and log directories selected for the current OS.
    """
    test_root = os.environ.get("DEMI_TEST_PATH_ROOT")
    if test_root:
        root = Path(test_root)
        return SettingsPaths(
            config_dir=root / "config",
            data_dir=root / "data",
            log_dir=root / "logs",
        )
    directories = platformdirs.PlatformDirs(appname="Project_Demi", appauthor=False)
    return SettingsPaths(
        config_dir=Path(directories.user_config_path),
        data_dir=Path(directories.user_data_path),
        log_dir=Path(directories.user_log_path),
    )
