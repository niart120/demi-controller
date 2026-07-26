"""Run a version smoke test against the current standalone artifact."""

import os
import subprocess
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """Run the standalone executable with ``--version``."""
    executable = "demi.exe" if os.name == "nt" else "demi"
    artifact = ROOT / "dist" / "standalone" / "demi.dist" / executable
    if not artifact.is_file():
        raise RuntimeError(f"Standalone artifact does not exist: {artifact}")
    result = subprocess.run(
        [str(artifact), "--version"],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    expected = version("demi-controller")
    if result.returncode != 0:
        raise RuntimeError(f"Standalone version command failed: {result.stderr.strip()}")
    if result.stdout.strip() != expected:
        raise RuntimeError(
            f"Standalone version mismatch: expected {expected}, got {result.stdout.strip()}"
        )
    _assert_windows_qt_plugins(artifact.parent)
    _assert_windows_sdl2_runtime(artifact.parent)
    print(f"{artifact.name}: version {expected}")


def _assert_windows_qt_plugins(artifact_dir: Path) -> None:
    if os.name != "nt":
        return
    plugin_dir = artifact_dir / "PySide6" / "qt-plugins"
    unexpected_families = sorted(
        child.name for child in plugin_dir.iterdir() if child.is_dir() and child.name != "platforms"
    )
    if unexpected_families:
        raise RuntimeError(f"Unexpected Qt plugin families: {', '.join(unexpected_families)}")
    if not (plugin_dir / "platforms" / "qwindows.dll").is_file():
        raise RuntimeError("Windows Qt platform plugin is missing: qwindows.dll")


def _assert_windows_sdl2_runtime(artifact_dir: Path) -> None:
    if os.name != "nt":
        return
    sdl2_dll = artifact_dir / "sdl2dll" / "dll" / "SDL2.dll"
    if not sdl2_dll.is_file():
        raise RuntimeError(f"SDL2 runtime is missing: {sdl2_dll}")


if __name__ == "__main__":
    main()
