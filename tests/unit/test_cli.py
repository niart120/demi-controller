import importlib.metadata
import runpy
import sys

import pytest

from demi import cli
from demi.cli import main


def test_cli_version_matches_distribution_metadata(capsys: pytest.CaptureFixture[str]) -> None:
    result = main(["--version"])

    assert result == 0
    assert capsys.readouterr().out == f"{importlib.metadata.version('demi-controller')}\n"


def test_cli_without_arguments_runs_the_application_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[bool] = []

    def run_application() -> int:
        calls.append(True)
        return 17

    monkeypatch.setattr(cli, "run_application", run_application)

    assert main([]) == 17
    assert calls == [True]


def test_cli_does_not_create_the_application_for_unknown_arguments(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def unexpected_runner() -> int:
        raise AssertionError

    monkeypatch.setattr(cli, "run_application", unexpected_runner)

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


def test_module_and_packaging_launcher_run_the_canonical_application_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[bool] = []

    def run_application() -> int:
        calls.append(True)
        return 23

    monkeypatch.setattr(cli, "run_application", run_application)
    monkeypatch.setattr(sys, "argv", ["demi"])

    with pytest.raises(SystemExit) as module_exit:
        runpy.run_module("demi", run_name="__main__")
    with pytest.raises(SystemExit) as launcher_exit:
        runpy.run_path("packaging/launcher.py", run_name="__main__")

    assert module_exit.value.code == 23
    assert launcher_exit.value.code == 23
    assert calls == [True, True]


def test_project_demi_compatibility_script_points_to_the_canonical_cli() -> None:
    scripts = {
        entry_point.name: entry_point.value
        for entry_point in importlib.metadata.entry_points(group="console_scripts")
    }

    assert scripts["demi"] == "demi.cli:main"
    assert scripts["project-demi"] == "demi.cli:main"
