from pathlib import Path


def test_packaging_launcher_and_build_entrypoints_are_present() -> None:
    root = Path(__file__).parents[2]

    assert (root / "packaging" / "launcher.py").is_file()
    assert (root / "packaging" / "build.py").is_file()
    assert (root / "packaging" / "smoke.py").is_file()


def test_project_metadata_and_lock_do_not_resolve_pyglet() -> None:
    root = Path(__file__).parents[2]

    assert "pyglet" not in (root / "pyproject.toml").read_text(encoding="utf-8").lower()
    assert "pyglet" not in (root / "uv.lock").read_text(encoding="utf-8").lower()


def test_package_builder_and_license_inventory_do_not_reference_pyglet() -> None:
    root = Path(__file__).parents[2]

    assert "pyglet" not in (root / "packaging" / "build.py").read_text(encoding="utf-8").lower()
    assert "pyglet" not in (root / "packaging" / "LICENSES.md").read_text(encoding="utf-8").lower()


def test_package_workflow_builds_three_os_artifacts() -> None:
    workflow = (Path(__file__).parents[2] / ".github" / "workflows" / "package.yml").read_text(
        encoding="utf-8"
    )

    assert "runs-on: ${{ matrix.os }}" in workflow
    for runner in ("ubuntu-latest", "macos-latest", "windows-latest"):
        assert f"          - {runner}" in workflow
    assert "uv run python packaging/build.py" in workflow
    assert "uv run python packaging/smoke.py" in workflow
