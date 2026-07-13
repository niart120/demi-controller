"""Run a version smoke test against the current standalone artifact."""

import os
import subprocess
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """Run the standalone executable with ``--version``."""
    artifact = ROOT / "dist" / "standalone" / ("demi.exe" if os.name == "nt" else "demi")
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
    print(f"{artifact.name}: version {expected}")


if __name__ == "__main__":
    main()
