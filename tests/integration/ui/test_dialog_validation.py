from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QDialogButtonBox

from demi.application.settings_editor import SettingsEditor
from demi.domain.settings import AppSettings, DiagnosticLevel
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

    assert mapping.set_source(0, "KEY:F4")
    assert not mapping.set_source(0, "KEY:F5")
    assert mapping_editor.draft.profiles[0].bindings[0].source == "KEY:F4"
    assert mapping.mapping_model.data(mapping.mapping_model.index(0, 4)) == (
        "Input cannot be assigned"
    )
    assert mapping.isVisible()

    connection_editor = SettingsEditor(AppSettings.default())
    connection = ConnectionDialog(connection_editor, on_rescan=lambda: None)
    connection.diagnostic_level_combo.setCurrentIndex(-1)
    connection.show()
    qt_application.processEvents()

    assert not connection.apply_connection_fields()
    assert connection_editor.draft.connection.diagnostic_level is DiagnosticLevel.INFO
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


def test_settings_dialogs_mark_save_as_primary_and_focus_invalid_connection_input(
    qt_application: QApplication,
) -> None:
    mapping = MappingDialog(SettingsEditor(AppSettings.default()))
    colors = ControllerColorsDialog(
        SettingsEditor(AppSettings.default()),
        connected=False,
        on_preview=lambda _colors: None,
        on_save=lambda: True,
        on_cancel=lambda: True,
        on_defer_reconnect=lambda: None,
        on_reconnect=lambda: None,
    )
    connection = ConnectionDialog(SettingsEditor(AppSettings.default()), on_rescan=lambda: None)

    for dialog in (mapping, colors, connection):
        dialog.show()
        qt_application.processEvents()
        save = dialog.button_box.button(QDialogButtonBox.StandardButton.Save)
        assert save is not None
        assert save.isDefault()

    connection.diagnostic_level_combo.setCurrentIndex(-1)
    assert not connection.apply_connection_fields()
    qt_application.processEvents()

    assert connection.diagnostic_level_combo.hasFocus()
    assert connection.connection_error_label.text() == "Connection settings are invalid"
