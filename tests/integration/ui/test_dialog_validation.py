from __future__ import annotations

from typing import TYPE_CHECKING

from demi.application.settings_editor import SettingsEditor
from demi.domain.settings import AppSettings
from demi.ui.dialogs.colors import ControllerColorsDialog
from demi.ui.dialogs.connection import ConnectionDialog
from demi.ui.dialogs.mapping import MappingDialog

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication


def test_dialogs_keep_invalid_values_out_of_drafts_and_show_an_explanation(
    qt_application: QApplication,
) -> None:
    mapping_editor = SettingsEditor(AppSettings.default())
    mapping = MappingDialog(mapping_editor)
    mapping.show()
    qt_application.processEvents()

    assert not mapping.set_source(0, "KEY:F4")
    assert mapping_editor.draft.profiles[0].bindings[0].source == "KEY:F"
    assert mapping.capture_label.text() == "Input cannot be assigned"
    assert mapping.isVisible()

    connection_editor = SettingsEditor(AppSettings.default())
    connection = ConnectionDialog(connection_editor, on_rescan=lambda: None)
    connection.bond_slot_edit.setText("invalid slot")
    connection.timeout_edit.setText("0")
    connection.show()
    qt_application.processEvents()

    assert not connection.apply_connection_fields()
    assert connection_editor.draft.connection.bond_slot == "default"
    assert connection_editor.draft.connection.timeout_seconds == 30.0
    assert connection.connection_error_label.text() == "Connection settings are invalid"
    assert connection.isVisible()

    colors_editor = SettingsEditor(AppSettings.default())
    colors = ControllerColorsDialog(
        colors_editor,
        connected=False,
        on_preview=lambda _colors: None,
        on_save=lambda: True,
        on_cancel=lambda: True,
        on_defer_reconnect=lambda: None,
        on_reconnect=lambda: None,
    )
    colors.show()
    qt_application.processEvents()

    assert not colors.set_color("body", "#GGGGGG")
    assert colors_editor.draft.controller_colors.body == "#323232"
    assert colors.save_error_label.text() == "The color format is invalid"
    assert colors.color_buttons["body"].isEnabled()
    assert colors.isVisible()
