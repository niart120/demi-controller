"""OS-specific settings and bond paths."""

import re
from dataclasses import dataclass
from pathlib import Path

import platformdirs

from demi.domain.errors import DomainValueError

_BOND_SLOT_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}")


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

    def bond_file(self, slot: str) -> Path:
        """Return a validated Pro Controller bond path for ``slot``."""
        if not isinstance(slot, str) or _BOND_SLOT_PATTERN.fullmatch(slot) is None:
            raise DomainValueError
        return self.data_dir / "bonds" / "pro-controller" / f"{slot}.json"


def resolve_paths() -> SettingsPaths:
    """Resolve Project_Demi directories through platformdirs."""
    directories = platformdirs.PlatformDirs(appname="Project_Demi", appauthor=False)
    return SettingsPaths(
        config_dir=Path(directories.user_config_path),
        data_dir=Path(directories.user_data_path),
        log_dir=Path(directories.user_log_path),
    )
