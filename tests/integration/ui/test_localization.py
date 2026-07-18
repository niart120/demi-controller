from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialogButtonBox

from demi.app import WindowSpec
from demi.application.settings_editor import SettingsEditor
from demi.domain.settings import AppSettings
from demi.ui.dialogs.colors import ControllerColorsDialog
from demi.ui.dialogs.connection import ConnectionDialog
from demi.ui.dialogs.mapping import MappingDialog
from demi.ui.main_window import MainWindow


def test_default_user_interface_uses_english_source_text(
    qt_application: QApplication,
) -> None:
    assert qt_application is not None
    window = MainWindow(WindowSpec(width=960, height=640, maximized=False))
    mapping = MappingDialog(SettingsEditor(AppSettings.default()))
    connection = ConnectionDialog(SettingsEditor(AppSettings.default()), on_rescan=lambda: None)
    colors = ControllerColorsDialog(
        SettingsEditor(AppSettings.default()),
        connected=False,
        on_preview=lambda _colors: None,
        on_save=lambda: True,
        on_cancel=lambda: True,
        on_defer_reconnect=lambda: None,
        on_reconnect=lambda: None,
    )

    assert window.main_toolbar.connection_action.text() == "Connect"
    assert window.main_toolbar.capture_action.text() == "Start input"
    assert mapping.windowTitle() == "Key mappings"
    assert mapping.table.model().headerData(0, Qt.Orientation.Horizontal) == "Target"
    assert connection.windowTitle() == "Connection settings"
    assert connection.rescan_button.text() == "Rescan"
    assert colors.windowTitle() == "Controller colors"

    for dialog in (mapping, colors):
        save_button = dialog.button_box.button(QDialogButtonBox.StandardButton.Save)
        cancel_button = dialog.button_box.button(QDialogButtonBox.StandardButton.Cancel)
        assert save_button is not None
        assert cancel_button is not None
        assert save_button.text() == "Save"
        assert cancel_button.text() == "Cancel"

    assert connection.connect_button.text() == "Save and connect"
    connection_cancel = connection.button_box.button(QDialogButtonBox.StandardButton.Cancel)
    assert connection_cancel is not None
    assert connection_cancel.text() == "Cancel"

    colors.close()
    connection.close()
    mapping.close()
    window.close()
