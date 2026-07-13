"""Unit tests for local application logging configuration."""

import logging
from collections.abc import Iterator
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from demi.app import configure_logging
from demi.config.paths import SettingsPaths
from demi.domain.settings import DiagnosticLevel


@pytest.fixture
def paths(tmp_path: Path) -> SettingsPaths:
    """Return isolated local paths without a pre-created log directory."""
    return SettingsPaths(
        config_dir=tmp_path / "config",
        data_dir=tmp_path / "data",
        log_dir=tmp_path / "logs",
    )


@pytest.fixture(autouse=True)
def close_demi_handlers_after_test() -> Iterator[None]:
    """Close global logger handlers so temporary files remain removable."""
    yield
    logger = logging.getLogger("demi")
    for handler in tuple(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def test_configure_logging_creates_one_configured_rotating_file_handler(
    paths: SettingsPaths,
) -> None:
    assert paths.log_dir.exists() is False

    logger = configure_logging(paths, DiagnosticLevel.DEBUG)

    assert paths.log_dir.is_dir()
    assert logger.level == logging.DEBUG
    assert logger.propagate is False
    assert len(logger.handlers) == 1
    handler = logger.handlers[0]
    assert isinstance(handler, RotatingFileHandler)
    assert Path(handler.baseFilename) == (paths.log_dir / "project-demi.log").resolve()
    assert handler.maxBytes == 1_048_576
    assert handler.backupCount == 3
    assert handler.encoding == "utf-8"


def test_configure_logging_replaces_previous_handler_and_level(paths: SettingsPaths) -> None:
    logger = configure_logging(paths, DiagnosticLevel.DEBUG)
    previous_handler = logger.handlers[0]

    reconfigured = configure_logging(paths, DiagnosticLevel.ERROR)

    assert reconfigured is logger
    assert reconfigured.level == logging.ERROR
    assert len(reconfigured.handlers) == 1
    assert reconfigured.handlers[0] is not previous_handler
    assert isinstance(reconfigured.handlers[0], RotatingFileHandler)
