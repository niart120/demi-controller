"""Verify the contents of artifacts already created by ``uv build``."""

from __future__ import annotations

import argparse
import tarfile
from pathlib import Path
from zipfile import ZipFile

I18N_RESOURCES = frozenset(
    {
        "demi/i18n/__init__.py",
        "demi/i18n/demi_ja.ts",
        "demi/i18n/demi_ja.qm",
    }
)
WHEEL_REQUIRED_FILES = I18N_RESOURCES | {"demi/THIRD_PARTY_NOTICES.md"}


def _single_artifact(directory: Path, pattern: str) -> Path:
    artifacts = sorted(directory.glob(pattern))
    if len(artifacts) != 1:
        message = f"Expected one {pattern} artifact in {directory}, found {len(artifacts)}."
        raise SystemExit(message)
    return artifacts[0]


def _sdist_names(artifact: Path) -> set[str]:
    with tarfile.open(artifact, "r:gz") as archive:
        return {
            name.partition("/")[2].removeprefix("src/")
            for name in archive.getnames()
            if "/" in name
        }


def _wheel_names(artifact: Path) -> set[str]:
    with ZipFile(artifact) as archive:
        return set(archive.namelist())


def main() -> int:
    """Validate the wheel and source distribution in the selected directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, default=Path("dist"))
    arguments = parser.parse_args()

    sdist = _single_artifact(arguments.dist_dir, "demi_controller-*.tar.gz")
    wheel = _single_artifact(arguments.dist_dir, "demi_controller-*.whl")
    missing_from_sdist = I18N_RESOURCES - _sdist_names(sdist)
    wheel_names = _wheel_names(wheel)
    missing_from_wheel = WHEEL_REQUIRED_FILES - wheel_names
    has_project_license = any(name.endswith(".dist-info/licenses/LICENSE") for name in wheel_names)

    failures: list[str] = []
    if missing_from_sdist:
        failures.append(f"sdist is missing: {', '.join(sorted(missing_from_sdist))}")
    if missing_from_wheel:
        failures.append(f"wheel is missing: {', '.join(sorted(missing_from_wheel))}")
    if not has_project_license:
        failures.append("wheel is missing the project LICENSE file")
    if failures:
        raise SystemExit("\n".join(failures))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
