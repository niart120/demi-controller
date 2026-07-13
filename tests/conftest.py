"""Shared test fixtures."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qt_application() -> QApplication:
    """Return the one offscreen QApplication shared by widget tests."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication  # noqa: PLC0415 - Qt test時だけimportする。

    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        return existing
    return QApplication([])
