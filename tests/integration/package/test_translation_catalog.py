from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path


def test_sdist_and_wheel_include_loadable_japanese_catalog(tmp_path: Path) -> None:
    repository_root = Path(__file__).parents[3]
    uv = shutil.which("uv")
    assert uv is not None

    distribution_directory = tmp_path / "dist"
    result = subprocess.run(  # noqa: S603 - test-owned uv and repository paths only.
        (uv, "build", "--out-dir", str(distribution_directory)),
        cwd=repository_root,
        capture_output=True,
        check=False,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr

    sdist = next(distribution_directory.glob("demi_controller-*.tar.gz"))
    wheel = next(distribution_directory.glob("demi_controller-*.whl"))
    expected_resources = {
        "demi/i18n/__init__.py",
        "demi/i18n/demi_ja.ts",
        "demi/i18n/demi_ja.qm",
    }

    with tarfile.open(sdist, "r:gz") as archive:
        sdist_names = set()
        for name in archive.getnames():
            relative_name = name.partition("/")[2]
            if relative_name.startswith("src/"):
                relative_name = relative_name.removeprefix("src/")
            sdist_names.add(relative_name)
    with zipfile.ZipFile(wheel) as archive:
        wheel_names = set(archive.namelist())
        extracted_wheel = tmp_path / "extracted-wheel"
        for name in ("demi/__init__.py", *sorted(expected_resources)):
            destination = extracted_wheel / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(name))

    assert expected_resources <= sdist_names
    assert expected_resources <= wheel_names

    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(extracted_wheel)
    smoke = subprocess.run(
        (
            sys.executable,
            "-c",
            "from importlib.resources import files; "
            "from PySide6.QtCore import QTranslator; "
            "catalog = files('demi.i18n').joinpath('demi_ja.qm'); "
            "assert catalog.is_file(); "
            "assert QTranslator().load(str(catalog))",
        ),
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )
    assert smoke.returncode == 0, smoke.stderr
