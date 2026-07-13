"""Build a standalone Project_Demi artifact with PyInstaller."""

import os
import platform
import shutil
import subprocess
import sys
from importlib.metadata import Distribution, PackageNotFoundError, distribution, version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "dist" / "standalone"
WORK_DIR = ROOT / "build" / "pyinstaller"
RUNTIME_PACKAGES = (
    "demi-controller",
    "platformdirs",
    "swbt-python",
    "tomli-w",
    "bumble",
)


def main() -> None:
    """Build the executable and write version, build, and license metadata."""
    _reset_output_dirs()
    _run_pyinstaller()
    _write_version()
    _write_build_info()
    _write_licenses()
    artifact = OUTPUT_DIR / ("demi.exe" if os.name == "nt" else "demi")
    if not artifact.is_file():
        raise RuntimeError(f"PyInstaller did not create {artifact}")
    print(f"Built {artifact.relative_to(ROOT)}")


def _reset_output_dirs() -> None:
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR)
    OUTPUT_DIR.mkdir(parents=True)


def _run_pyinstaller() -> None:
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        "--onefile",
        "--name",
        "demi",
        "--paths",
        str(ROOT / "src"),
        "--distpath",
        str(OUTPUT_DIR),
        "--workpath",
        str(WORK_DIR),
        "--specpath",
        str(WORK_DIR),
        "--collect-submodules",
        "demi",
        "--collect-all",
        "swbt",
        "--collect-all",
        "bumble",
        str(ROOT / "packaging" / "launcher.py"),
    ]
    subprocess.run(command, cwd=ROOT, check=True)


def _write_version() -> None:
    (OUTPUT_DIR / "VERSION.txt").write_text(
        f"demi-controller {version('demi-controller')}\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_build_info() -> None:
    lines = (
        f"distribution=demi-controller {version('demi-controller')}",
        f"os={platform.system()} {platform.release()}",
        f"python={platform.python_version()}",
        f"pyinstaller={version('pyinstaller')}",
    )
    (OUTPUT_DIR / "BUILD_INFO.txt").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_licenses() -> None:
    license_dir = OUTPUT_DIR / "LICENSES"
    license_dir.mkdir()
    (license_dir / "demi-controller-LICENSE").write_text(
        (ROOT / "LICENSE").read_text(encoding="utf-8"),
        encoding="utf-8",
        newline="\n",
    )
    manifest = ["package\tversion\tlicense files"]
    for package_name in RUNTIME_PACKAGES:
        package = _load_distribution(package_name)
        copied = (
            ["demi-controller-LICENSE"]
            if package_name == "demi-controller"
            else _copy_license_files(package, license_dir)
        )
        if not copied:
            raise RuntimeError(f"No license file found for {package_name}")
        manifest.append(f"{package_name}\t{package.version}\t{', '.join(sorted(copied))}")
    (OUTPUT_DIR / "LICENSES.txt").write_text(
        "\n".join(manifest) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _load_distribution(package_name: str) -> Distribution:
    try:
        return distribution(package_name)
    except PackageNotFoundError as error:
        raise RuntimeError(f"Runtime package is not installed: {package_name}") from error


def _copy_license_files(package: Distribution, destination: Path) -> list[str]:
    copied: list[str] = []
    for file in package.files or ():
        filename = Path(file).name
        if not _looks_like_license(filename):
            continue
        source = package.locate_file(file)
        if not source.is_file():
            continue
        safe_package = package.metadata["Name"].replace("-", "_")
        target_name = f"{safe_package}-{filename}"
        shutil.copyfile(source, destination / target_name)
        copied.append(target_name)
    return copied


def _looks_like_license(filename: str) -> bool:
    lowered = filename.lower()
    return any(token in lowered for token in ("license", "copying", "notice"))


if __name__ == "__main__":
    main()
