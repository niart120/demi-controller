"""Build a standalone Project_Demi artifact with PySide6 Deploy and Nuitka."""

import os
import platform
import shutil
import subprocess
from importlib.metadata import Distribution, PackageNotFoundError, distribution, version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "dist" / "standalone"
BUILD_DIR = ROOT / "build" / "pyside6-deploy"
NUITKA_CACHE_DIR = ROOT / "build" / "nuitka-cache"
DEPLOY_CONFIG = ROOT / "pysidedeploy.spec"
NUITKA_PACKAGE_CONFIG = ROOT / "packaging" / "nuitka-package.config.yml"
RUNTIME_PACKAGES = (
    "demi-controller",
    "platformdirs",
    "libusb1",
    "libusb-package",
    "pysdl2",
    "pysdl2-dll",
    "swbt-python",
    "tomli-w",
    "bumble",
    "pyside6-essentials",
    "shiboken6",
)
SDL2_DLL_PACKAGE_PATH = Path("sdl2dll") / "dll"


def main() -> None:
    """Build the executable and write version, build, and license metadata."""
    _reset_output_dirs()
    _run_pyside6_deploy()
    _rename_launcher_executable()
    _write_version()
    _write_build_info()
    _write_licenses()
    artifact = _artifact_path()
    if not artifact.is_file():
        raise RuntimeError(f"PySide6 Deploy did not create {artifact}")
    print(f"Built {artifact.relative_to(ROOT)}")


def _reset_output_dirs() -> None:
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    OUTPUT_DIR.mkdir(parents=True)
    BUILD_DIR.mkdir(parents=True)


def _run_pyside6_deploy() -> None:
    mutable_config = BUILD_DIR / DEPLOY_CONFIG.name
    _write_mutable_deploy_config(mutable_config)
    command = [
        "pyside6-deploy",
        "--force",
        "--config-file",
        str(mutable_config),
    ]
    subprocess.run(command, cwd=ROOT, check=True, env=_nuitka_environment())


def _nuitka_environment() -> dict[str, str]:
    """Return a build environment with a writable Nuitka cache location."""
    return os.environ | {"NUITKA_CACHE_DIR": str(NUITKA_CACHE_DIR)}


def _write_mutable_deploy_config(destination: Path) -> None:
    if os.name == "nt":
        _sdl2_dll_directory()
    config = DEPLOY_CONFIG.read_text(encoding="utf-8")
    config = config.replace("project_dir = packaging", f"project_dir = {ROOT / 'packaging'}")
    config = config.replace(
        "input_file = packaging/launcher.py", f"input_file = {ROOT / 'packaging' / 'launcher.py'}"
    )
    config = config.replace(
        "extra_args = ",
        "extra_args = --include-distribution-metadata=swbt-python --include-module=libusb_package "
        f"--user-package-configuration-file={NUITKA_PACKAGE_CONFIG.as_posix()} ",
    )
    destination.write_text(config, encoding="utf-8", newline="\n")


def _sdl2_dll_directory() -> Path:
    path = _load_distribution("pysdl2-dll").locate_file(SDL2_DLL_PACKAGE_PATH)
    if not path.is_dir() or not (path / "SDL2.dll").is_file():
        raise RuntimeError(f"pysdl2-dll does not provide SDL2.dll: {path}")
    return path


def _artifact_path() -> Path:
    executable = "demi.exe" if os.name == "nt" else "demi"
    return OUTPUT_DIR / "demi.dist" / executable


def _rename_launcher_executable() -> None:
    launcher_name = "launcher.exe" if os.name == "nt" else "launcher"
    launcher = OUTPUT_DIR / "demi.dist" / launcher_name
    if not launcher.is_file():
        raise RuntimeError(f"PySide6 Deploy did not create {launcher}")
    launcher.replace(_artifact_path())


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
        f"nuitka={version('nuitka')}",
        f"pyside6-essentials={version('pyside6-essentials')}",
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
