from pathlib import Path


def test_ci_workflow_runs_the_repository_quality_gates() -> None:
    workflow = (Path(__file__).parents[2] / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    for command in (
        "uv sync --locked --dev",
        "uv lock --check",
        "uv run ruff format --check .",
        "uv run ruff check .",
        "uv run ty check --no-progress",
        "uv run pytest tests/unit",
        "uv build",
        "git diff --check",
    ):
        assert f"run: {command}" in workflow

    for python_version in ('"3.12"', '"3.13"'):
        assert python_version in workflow
    assert "UV_PYTHON: ${{ matrix.python-version }}" in workflow
    assert "pull_request:" in workflow


def test_ci_workflow_caches_dependencies_per_python_version() -> None:
    workflow = (Path(__file__).parents[2] / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    assert "enable-cache: true" in workflow
    assert "cache-suffix: python-${{ matrix.python-version }}" in workflow
    assert "cache-dependency-glob: |\n            pyproject.toml\n            uv.lock" in workflow


def test_ci_workflow_runs_source_gates_on_all_supported_os() -> None:
    workflow = (Path(__file__).parents[2] / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    assert "runs-on: ${{ matrix.os }}" in workflow
    for runner in ("ubuntu-latest", "macos-latest", "windows-latest"):
        assert f"          - {runner}" in workflow
    assert "QT_QPA_PLATFORM: offscreen" in workflow
    assert "run: uv run pytest tests/integration" in workflow


def test_ci_workflow_installs_the_linux_egl_runtime_for_pyside6() -> None:
    workflow = (Path(__file__).parents[2] / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    assert "if: runner.os == 'Linux'" in workflow
    assert "sudo apt-get install --yes libegl1" in workflow
