"""Clean-environment wheel GUI smoke tests."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

WHEEL_INSTALL_TIMEOUT_SECONDS = 120


def _venv_python(environment: Path) -> Path:
    if sys.platform == "win32":
        return environment / "Scripts" / "python.exe"
    return environment / "bin" / "python"


def _run(
    command: tuple[str, ...],
    *,
    cwd: Path,
    environment: dict[str, str],
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(  # noqa: S603 - test-owned uv, interpreter, and wheel only.
        command,
        cwd=cwd,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
        timeout=timeout,
    )

    assert result.returncode == 0, result.stderr
    return result


def test_wheel_installs_pyside6_and_starts_the_qt_runner_in_a_clean_venv(tmp_path: Path) -> None:
    repository_root = Path(__file__).parents[3]
    uv = shutil.which("uv")

    assert uv is not None

    wheel_directory = tmp_path / "wheel"
    wheel_directory.mkdir()
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)

    _run(
        (uv, "build", "--wheel", "--out-dir", str(wheel_directory)),
        cwd=repository_root,
        environment=environment,
    )
    wheels = tuple(wheel_directory.glob("demi_controller-*.whl"))

    assert len(wheels) == 1

    venv_directory = tmp_path / "wheel-venv"
    _run(
        (uv, "venv", "--no-project", "--python", sys.executable, str(venv_directory)),
        cwd=tmp_path,
        environment=environment,
    )
    python = _venv_python(venv_directory)
    _run(
        (uv, "pip", "install", "--python", str(python), str(wheels[0])),
        cwd=tmp_path,
        environment=environment,
        timeout=WHEEL_INSTALL_TIMEOUT_SECONDS,
    )

    version_result = _run(
        (str(python), "-m", "demi", "--version"),
        cwd=tmp_path,
        environment=environment,
    )
    pyside6 = _run(
        (str(python), "-c", "import PySide6; print(PySide6.__version__)"),
        cwd=tmp_path,
        environment=environment,
    )
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
    _run(
        (str(python), "-m", "demi"),
        cwd=tmp_path,
        environment=environment,
    )

    assert version_result.stdout.strip() == version("demi-controller")
    assert pyside6.stdout.strip()
