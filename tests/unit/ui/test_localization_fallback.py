import logging
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QDialogButtonBox

from demi.domain.settings import UiLanguage
from demi.ui import localization
from demi.ui.toolbar import MainToolBar


def test_missing_application_catalog_falls_back_to_complete_english_ui(
    qt_application: QApplication,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(localization, "files", lambda _package: tmp_path)

    with caplog.at_level(logging.WARNING, logger="demi.ui.localization"):
        translators = localization.install_translators(
            qt_application,
            UiLanguage.JAPANESE,
        )

    toolbar = MainToolBar()
    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
    )
    save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
    cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)

    assert translators == ()
    assert toolbar.connection_action.text() == "Connect"
    assert save_button is not None
    assert cancel_button is not None
    assert save_button.text() == "Save"
    assert cancel_button.text() == "Cancel"
    assert caplog.messages == ["UI translation unavailable; using English"]
