import importlib.metadata
import runpy
import sys

import pytest

from demi.cli import main


def test_cli_version_matches_distribution_metadata(capsys: pytest.CaptureFixture[str]) -> None:
    result = main(["--version"])

    assert result == 0
    assert capsys.readouterr().out == f"{importlib.metadata.version('demi-controller')}\n"


def test_module_entry_point_uses_the_same_version_output(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "argv", ["demi", "--version"])

    with pytest.raises(SystemExit) as raised:
        runpy.run_module("demi", run_name="__main__")

    assert raised.value.code == 0
    assert capsys.readouterr().out == f"{importlib.metadata.version('demi-controller')}\n"
