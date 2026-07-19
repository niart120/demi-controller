from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QMessageBox

from demi.application.settings_editor import SettingsEditor
from demi.domain.settings import AppSettings
from demi.ui.dialogs.colors import ControllerColorsDialog

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication

    from demi.application.settings_editor import ColorField
    from demi.domain.settings import ControllerColorSettings


def test_colors_dialog_previews_draft_restores_saved_colors_and_requests_reconnect(
    qt_application: QApplication,
) -> None:
    original = AppSettings.default().controller_colors
    previews: list[ControllerColorSettings] = []
    cancellations: list[str] = []
    editor = SettingsEditor(AppSettings.default())

    def cancel() -> bool:
        cancellations.append("cancel")
        return True

    cancelled = ControllerColorsDialog(
        editor,
        connected=False,
        on_preview=previews.append,
        on_save=lambda: True,
        on_cancel=cancel,
        on_defer_reconnect=lambda: None,
        on_reconnect=lambda: None,
    )
    cancelled.show()
    qt_application.processEvents()
    cancelled.set_color("body", "#abcdef")

    assert editor.draft.controller_colors.body == "#ABCDEF"
    assert previews[-1].body == "#ABCDEF"
    assert cancelled.color_buttons["body"].property("swatchColor") == "#ABCDEF"

    cancel_button = cancelled.button_box.button(QDialogButtonBox.StandardButton.Cancel)
    assert cancel_button is not None
    cancel_button.click()
    qt_application.processEvents()

    assert cancellations == ["cancel"]
    assert previews[-1] == original
    assert cancelled.result() == int(QDialog.DialogCode.Rejected)

    saved: list[ControllerColorSettings] = []
    reconnects: list[str] = []
    saving_editor = SettingsEditor(AppSettings.default())

    def save() -> bool:
        saved.append(saving_editor.draft.controller_colors)
        return True

    saving = ControllerColorsDialog(
        saving_editor,
        connected=True,
        on_preview=lambda _colors: None,
        on_save=save,
        on_cancel=lambda: True,
        on_defer_reconnect=lambda: None,
        on_reconnect=lambda: reconnects.append("reconnect"),
    )
    saving.show()
    qt_application.processEvents()
    saving.set_color("buttons", "#123456")
    save_button = saving.button_box.button(QDialogButtonBox.StandardButton.Save)
    assert save_button is not None
    save_button.click()
    qt_application.processEvents()

    confirmation = saving.reconnect_confirmation
    assert confirmation is not None
    assert confirmation.text() == "Reconnect to apply the display colors to the target device."
    assert saved[-1].buttons == "#123456"
    assert saving.isVisible()

    reconnect_button = confirmation.button(QMessageBox.StandardButton.Yes)
    assert reconnect_button is not None
    reconnect_button.click()
    qt_application.processEvents()

    assert reconnects == ["reconnect"]
    assert saving.result() == int(QDialog.DialogCode.Accepted)

    deferred: list[str] = []
    deferring = ControllerColorsDialog(
        SettingsEditor(AppSettings.default()),
        connected=True,
        on_preview=lambda _colors: None,
        on_save=lambda: True,
        on_cancel=lambda: True,
        on_defer_reconnect=lambda: deferred.append("later"),
        on_reconnect=lambda: None,
    )
    deferring.show()
    qt_application.processEvents()
    deferred_save_button = deferring.button_box.button(QDialogButtonBox.StandardButton.Save)
    assert deferred_save_button is not None
    deferred_save_button.click()
    qt_application.processEvents()
    deferred_confirmation = deferring.reconnect_confirmation
    assert deferred_confirmation is not None
    defer_button = deferred_confirmation.button(QMessageBox.StandardButton.No)
    assert defer_button is not None
    defer_button.click()
    qt_application.processEvents()

    assert deferred == ["later"]
    assert deferring.result() == int(QDialog.DialogCode.Accepted)


def test_colors_dialog_uses_four_textless_swatches_for_the_current_colors() -> None:
    settings = AppSettings.default()
    dialog = ControllerColorsDialog(
        SettingsEditor(settings),
        connected=False,
        on_preview=lambda _colors: None,
        on_save=lambda: True,
        on_cancel=lambda: True,
        on_defer_reconnect=lambda: None,
        on_reconnect=lambda: None,
    )

    expected: dict[ColorField, str] = {
        "body": settings.controller_colors.body,
        "buttons": settings.controller_colors.buttons,
        "left_grip": settings.controller_colors.left_grip,
        "right_grip": settings.controller_colors.right_grip,
    }
    assert set(dialog.color_buttons) == set(expected)
    for field, color in expected.items():
        button = dialog.color_buttons[field]
        assert button.text() == ""
        assert button.property("swatchColor") == color

    assert not any(label.text().startswith("#") for label in dialog.findChildren(QLabel))


@pytest.mark.parametrize("field", ["body", "buttons", "left_grip", "right_grip"])
@pytest.mark.parametrize("activation", ["mouse", "enter", "space"])
def test_each_color_swatch_opens_its_current_color_with_mouse_or_keyboard(
    qt_application: QApplication,
    field: ColorField,
    activation: str,
) -> None:
    settings = AppSettings.default()
    dialog = ControllerColorsDialog(
        SettingsEditor(settings),
        connected=False,
        on_preview=lambda _colors: None,
        on_save=lambda: True,
        on_cancel=lambda: True,
        on_defer_reconnect=lambda: None,
        on_reconnect=lambda: None,
    )
    dialog.show()
    button = dialog.color_buttons[field]
    button.setFocus()
    qt_application.processEvents()

    if activation == "mouse":
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    elif activation == "enter":
        QTest.keyClick(button, Qt.Key.Key_Return)
    else:
        QTest.keyClick(button, Qt.Key.Key_Space)
    qt_application.processEvents()

    picker = dialog.color_dialog
    assert picker is not None
    assert picker.currentColor().name().upper() == getattr(settings.controller_colors, field)
    picker.close()
