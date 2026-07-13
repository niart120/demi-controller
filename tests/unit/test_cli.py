import builtins
import importlib
import importlib.metadata
import runpy
import sys
from collections.abc import Mapping, Sequence
from types import ModuleType

import pytest

from demi.cli import main


def test_cli_version_matches_distribution_metadata(capsys: pytest.CaptureFixture[str]) -> None:
    result = main(["--version"])

    assert result == 0
    assert capsys.readouterr().out == f"{importlib.metadata.version('demi-controller')}\n"


def test_package_import_and_version_output_do_not_import_pyglet(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    original_import = builtins.__import__

    def reject_pyglet_import(
        name: str,
        module_globals: Mapping[str, object] | None = None,
        module_locals: Mapping[str, object] | None = None,
        fromlist: Sequence[str] = (),
        level: int = 0,
    ) -> ModuleType:
        if name == "pyglet" or name.startswith("pyglet."):
            raise AssertionError
        return original_import(name, module_globals, module_locals, fromlist, level)

    monkeypatch.delitem(sys.modules, "demi")
    monkeypatch.setattr(builtins, "__import__", reject_pyglet_import)

    package = importlib.import_module("demi")

    assert package.__version__ == importlib.metadata.version("demi-controller")
    assert main(["--version"]) == 0
    assert capsys.readouterr().out == f"{package.__version__}\n"


def test_cli_without_arguments_reports_legacy_ui_unavailable(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main([]) == 1
    assert capsys.readouterr().err == "GUI は UI 更新中のため現在は起動できません。\n"


def test_cli_does_not_create_the_application_for_unknown_arguments(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--unknown"]) == 2
    assert capsys.readouterr().err == "unknown argument: --unknown\n"


def test_module_entry_point_uses_the_same_version_output(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "argv", ["demi", "--version"])

    with pytest.raises(SystemExit) as raised:
        runpy.run_module("demi", run_name="__main__")

    assert raised.value.code == 0
    assert capsys.readouterr().out == f"{importlib.metadata.version('demi-controller')}\n"


def test_module_and_packaging_launcher_report_legacy_ui_unavailable(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "argv", ["demi"])

    with pytest.raises(SystemExit) as module_exit:
        runpy.run_module("demi", run_name="__main__")
    with pytest.raises(SystemExit) as launcher_exit:
        runpy.run_path("packaging/launcher.py", run_name="__main__")

    assert module_exit.value.code == 1
    assert launcher_exit.value.code == 1
    assert capsys.readouterr().err == "GUI は UI 更新中のため現在は起動できません。\n" * 2


def test_project_demi_compatibility_script_points_to_the_canonical_cli() -> None:
    scripts = {
        entry_point.name: entry_point.value
        for entry_point in importlib.metadata.entry_points(group="console_scripts")
    }

    assert scripts["demi"] == "demi.cli:main"
    assert scripts["project-demi"] == "demi.cli:main"
