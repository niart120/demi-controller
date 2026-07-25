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


def test_gamepad_runtime_dependencies_are_collected_and_noticed() -> None:
    root = Path(__file__).parents[2]

    metadata = (root / "pyproject.toml").read_text(encoding="utf-8").lower()
    builder = (root / "packaging" / "build.py").read_text(encoding="utf-8").lower()
    inventory = (root / "packaging" / "LICENSES.md").read_text(encoding="utf-8").lower()
    notices = (root / "src" / "demi" / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8").lower()

    assert "pysdl2" in metadata
    assert "pysdl2-dll" in metadata
    assert '"sdl2"' in builder
    assert '"sdl2dll"' in builder
    assert "pysdl2-dll" in inventory
    assert "pysdl2-dll" in notices


def test_legacy_package_workflow_is_removed_until_qt_packaging() -> None:
    workflow = Path(__file__).parents[2] / ".github" / "workflows" / "package.yml"

    assert not workflow.exists()
