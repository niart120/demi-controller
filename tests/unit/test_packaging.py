import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest


def _load_build_module() -> ModuleType:
    build_path = Path(__file__).parents[2] / "packaging" / "build.py"
    spec = importlib.util.spec_from_file_location("demi_packaging_build", build_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_smoke_module() -> ModuleType:
    smoke_path = Path(__file__).parents[2] / "packaging" / "smoke.py"
    spec = importlib.util.spec_from_file_location("demi_packaging_smoke", smoke_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_packaging_launcher_and_build_entrypoints_are_present() -> None:
    root = Path(__file__).parents[2]

    assert (root / "packaging" / "launcher.py").is_file()
    assert (root / "packaging" / "build.py").is_file()
    assert (root / "packaging" / "smoke.py").is_file()


def test_project_metadata_and_lock_do_not_resolve_pyglet() -> None:
    root = Path(__file__).parents[2]

    assert "pyglet" not in (root / "pyproject.toml").read_text(encoding="utf-8").lower()
    assert "pyglet" not in (root / "uv.lock").read_text(encoding="utf-8").lower()


def test_package_builder_uses_pyside6_deploy_with_minimal_qt_runtime() -> None:
    root = Path(__file__).parents[2]

    metadata = (root / "pyproject.toml").read_text(encoding="utf-8").lower()
    builder = (root / "packaging" / "build.py").read_text(encoding="utf-8").lower()
    deploy_config = (root / "pysidedeploy.spec").read_text(encoding="utf-8").lower()

    assert '"pyside6>=' in metadata
    assert "pyinstaller" not in metadata
    assert "pyside6-deploy" in builder
    assert "pyinstaller" not in builder
    assert "modules = core,gui,widgets" in deploy_config
    assert "plugins = platforms" in deploy_config
    assert "--include-qt-plugins=platforms" in deploy_config
    assert "--noinclude-qt-plugins=imageformats" in deploy_config


def test_deploy_config_uses_a_versioned_project_file_for_the_launcher() -> None:
    root = Path(__file__).parents[2]
    deploy_config = (root / "pysidedeploy.spec").read_text(encoding="utf-8")
    project_file = root / "packaging" / "demi.pyproject"

    assert "project_file = demi.pyproject" in deploy_config
    assert json.loads(project_file.read_text(encoding="utf-8")) == {"files": ["launcher.py"]}


def test_package_builder_and_license_inventory_do_not_reference_pyglet() -> None:
    root = Path(__file__).parents[2]

    assert "pyglet" not in (root / "packaging" / "build.py").read_text(encoding="utf-8").lower()
    assert "pyglet" not in (root / "packaging" / "LICENSES.md").read_text(encoding="utf-8").lower()


def test_gamepad_runtime_dependencies_are_noticed() -> None:
    root = Path(__file__).parents[2]

    metadata = (root / "pyproject.toml").read_text(encoding="utf-8").lower()
    builder = (root / "packaging" / "build.py").read_text(encoding="utf-8").lower()
    inventory = (root / "packaging" / "LICENSES.md").read_text(encoding="utf-8").lower()
    notices = (root / "src" / "demi" / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8").lower()

    assert "pysdl2" in metadata
    assert "pysdl2-dll" in metadata
    assert "libusb1" in metadata
    assert '"pysdl2"' in builder
    assert '"pysdl2-dll"' in builder
    assert '"libusb1"' in builder
    assert '"libusb-package"' in builder
    assert "pysdl2-dll" in inventory
    assert "pysdl2-dll" in notices
    assert "libusb1" in inventory
    assert "libusb1" in notices
    assert "libusb-package" in inventory
    assert "libusb-package" in notices


def test_mutable_deploy_config_collects_installed_sdl2_dlls(tmp_path: Path) -> None:
    build = _load_build_module()
    config_path = tmp_path / "pysidedeploy.spec"

    build._write_mutable_deploy_config(config_path)

    config = config_path.read_text(encoding="utf-8")
    package_config = (
        Path(__file__).parents[2] / "packaging" / "nuitka-package.config.yml"
    ).read_text(encoding="utf-8")
    assert f"--user-package-configuration-file={build.NUITKA_PACKAGE_CONFIG.as_posix()}" in config
    assert "--include-distribution-metadata=swbt-python" in config
    assert "--include-module=libusb_package" in config
    assert "module-name: 'sdl2dll'" in package_config
    assert 'os.path.join(get_module_directory("sdl2dll"), "dll", "SDL2.dll")' in package_config


def test_mutable_deploy_config_checks_sdl2_only_for_windows(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    build = _load_build_module()
    checked: list[None] = []
    monkeypatch.setattr(build.os, "name", "nt")
    monkeypatch.setattr(build, "_sdl2_dll_directory", lambda: checked.append(None))

    build._write_mutable_deploy_config(tmp_path / "pysidedeploy.spec")

    assert checked == [None]


def test_package_builder_uses_a_workspace_scoped_nuitka_cache() -> None:
    build = _load_build_module()

    environment = build._nuitka_environment()

    assert environment["NUITKA_CACHE_DIR"] == str(build.ROOT / "build" / "nuitka-cache")


def test_windows_package_builder_adds_visual_studio_dumpbin_to_deploy_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    build = _load_build_module()
    dumpbin = (
        tmp_path
        / "Microsoft Visual Studio"
        / "18"
        / "Community"
        / "VC"
        / "Tools"
        / "MSVC"
        / "14.50"
        / "bin"
        / "Hostx64"
        / "x64"
        / "dumpbin.exe"
    )
    dumpbin.parent.mkdir(parents=True)
    dumpbin.touch()
    monkeypatch.setattr(build.os, "name", "nt")
    monkeypatch.setattr(build.shutil, "which", lambda _executable: None)
    monkeypatch.setenv("ProgramFiles", str(tmp_path))

    environment = build._nuitka_environment()

    assert environment["PATH"].split(build.os.pathsep)[0] == str(dumpbin.parent)


def test_windows_smoke_requires_sdl2_runtime(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    smoke = _load_smoke_module()
    monkeypatch.setattr(smoke.os, "name", "nt")

    with pytest.raises(RuntimeError, match="SDL2 runtime is missing"):
        smoke._assert_windows_sdl2_runtime(tmp_path)

    sdl2_dll = tmp_path / "sdl2dll" / "dll" / "SDL2.dll"
    sdl2_dll.parent.mkdir(parents=True)
    sdl2_dll.touch()
    smoke._assert_windows_sdl2_runtime(tmp_path)


def test_legacy_package_workflow_is_removed_until_qt_packaging() -> None:
    workflow = Path(__file__).parents[2] / ".github" / "workflows" / "package.yml"

    assert not workflow.exists()
