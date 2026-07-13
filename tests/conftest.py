"""Shared test fixtures."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

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


def close_qt_top_level_windows(application: QApplication) -> None:
    """Close and delete top-level Qt widgets left by one widget test."""
    from PySide6.QtCore import QCoreApplication, QEvent  # noqa: PLC0415 - Qt test時だけimportする。

    for widget in tuple(application.topLevelWidgets()):
        widget.close()
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    application.processEvents()

    assert application.topLevelWidgets() == []


@pytest.fixture
def qt_top_level_window_cleanup() -> Callable[[QApplication], None]:
    """Return the cleanup operation for a widget test that needs it eagerly."""
    return close_qt_top_level_windows


@pytest.fixture(autouse=True)
def clear_qt_top_level_windows(request: pytest.FixtureRequest) -> Iterator[None]:
    """Clean up widgets after every test that requested the shared application."""
    if "qt_application" not in request.fixturenames:
        yield
        return

    application = request.getfixturevalue("qt_application")
    yield
    close_qt_top_level_windows(application)
