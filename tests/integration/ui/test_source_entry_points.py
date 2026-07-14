"""Source checkout GUI smoke tests for the canonical entry points."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


def _console_script(name: str) -> Path:
    suffix = ".exe" if sys.platform == "win32" else ""
    return Path(sys.executable).with_name(f"{name}{suffix}")


def _source_gui_commands() -> tuple[tuple[str, tuple[str, ...]], ...]:
    return (
        ("demi", (str(_console_script("demi")),)),
        ("project-demi", (str(_console_script("project-demi")),)),
        ("python -m demi", (sys.executable, "-m", "demi")),
    )


@pytest.mark.parametrize(("label", "command"), _source_gui_commands())
def test_source_entry_points_start_and_close_the_qt_runner(
    label: str,
    command: tuple[str, ...],
    tmp_path: Path,
) -> None:
    repository_root = Path(__file__).parents[3]
    environment = os.environ.copy()
    environment.update(
        {
            "APPDATA": str(tmp_path / "appdata"),
            "LOCALAPPDATA": str(tmp_path / "localappdata"),
            "DEMI_TEST_PATH_ROOT": str(tmp_path),
            "QT_QPA_PLATFORM": "offscreen",
            "DEMI_QT_TEST_CLOSE_AFTER_MS": "25",
            "XDG_CONFIG_HOME": str(tmp_path / "config"),
            "XDG_DATA_HOME": str(tmp_path / "data"),
            "XDG_STATE_HOME": str(tmp_path / "state"),
        }
    )

    result = subprocess.run(  # noqa: S603 - test-owned entry point and environment only.
        command,
        cwd=repository_root,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
        timeout=5,
    )

    assert result.returncode == 0, f"{label}: {result.stderr}"
    log_files = tuple(tmp_path.rglob("project-demi.log"))

    assert len(log_files) == 1
    log_contents = log_files[0].read_text(encoding="utf-8")
    assert "support diagnostics os=" in log_contents
    assert "input timing samples=" in log_contents
