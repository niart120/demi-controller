"""License-notice checks for source and wheel users."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from zipfile import ZipFile


def test_source_and_wheel_provide_project_and_qt_notice_paths(tmp_path: Path) -> None:
    """Ship a discoverable Project_Demi, PySide6, and Qt notice with the wheel."""
    repository_root = Path(__file__).parents[3]
    source_notice = repository_root / "src" / "demi" / "THIRD_PARTY_NOTICES.md"
    source_inventory = repository_root / "packaging" / "LICENSES.md"
    uv = shutil.which("uv")

    assert uv is not None
    assert source_notice.is_file()
    for text in (
        source_notice.read_text(encoding="utf-8"),
        source_inventory.read_text(encoding="utf-8"),
    ):
        assert "Project_Demi" in text
        assert "PySide6" in text
        assert "Qt" in text
        assert "third-party" in text.lower()

    wheel_directory = tmp_path / "wheel"
    wheel_directory.mkdir()
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    result = subprocess.run(  # noqa: S603 - test-owned uv build only.
        (uv, "build", "--wheel", "--out-dir", str(wheel_directory)),
        cwd=repository_root,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    wheels = tuple(wheel_directory.glob("demi_controller-*.whl"))
    assert len(wheels) == 1
    with ZipFile(wheels[0]) as wheel:
        names = set(wheel.namelist())

    assert "demi/THIRD_PARTY_NOTICES.md" in names
    assert any(name.endswith(".dist-info/licenses/LICENSE") for name in names)
