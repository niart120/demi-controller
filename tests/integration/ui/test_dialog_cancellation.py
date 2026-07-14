from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QDialog

from demi.application.settings_editor import SettingsEditor
from demi.domain.settings import AppSettings
from demi.ui.dialogs.colors import ControllerColorsDialog
from demi.ui.dialogs.connection import ConnectionDialog
from demi.ui.dialogs.mapping import MappingDialog


def test_editable_dialogs_cancel_the_draft_once_for_escape_and_window_close(
    qt_application: QApplication,
) -> None:
    cancellations: list[str] = []

    mapping_escape = MappingDialog(
        SettingsEditor(AppSettings.default()),
        on_cancel=lambda: cancellations.append("mapping escape") or True,
    )
    mapping_escape.show()
    _send_escape(mapping_escape)
    qt_application.processEvents()

    mapping_close = MappingDialog(
        SettingsEditor(AppSettings.default()),
        on_cancel=lambda: cancellations.append("mapping close") or True,
    )
    mapping_close.show()
    mapping_close.close()
    qt_application.processEvents()

    connection_escape = ConnectionDialog(
        SettingsEditor(AppSettings.default()),
        on_rescan=lambda: None,
        on_cancel=lambda: cancellations.append("connection escape") or True,
    )
    connection_escape.show()
    _send_escape(connection_escape)
    qt_application.processEvents()

    connection_close = ConnectionDialog(
        SettingsEditor(AppSettings.default()),
        on_rescan=lambda: None,
        on_cancel=lambda: cancellations.append("connection close") or True,
    )
    connection_close.show()
    connection_close.close()
    qt_application.processEvents()

    colors_escape = _colors_dialog("colors escape", cancellations)
    colors_escape.show()
    _send_escape(colors_escape)
    qt_application.processEvents()

    colors_close = _colors_dialog("colors close", cancellations)
    colors_close.show()
    colors_close.close()
    qt_application.processEvents()

    assert cancellations == [
        "mapping escape",
        "mapping close",
        "connection escape",
        "connection close",
        "colors escape",
        "colors close",
    ]
    assert all(
        dialog.result() == int(QDialog.DialogCode.Rejected)
        for dialog in (
            mapping_escape,
            mapping_close,
            connection_escape,
            connection_close,
            colors_escape,
            colors_close,
        )
    )


def _colors_dialog(name: str, cancellations: list[str]) -> ControllerColorsDialog:
    return ControllerColorsDialog(
        SettingsEditor(AppSettings.default()),
        connected=False,
        on_preview=lambda _colors: None,
        on_save=lambda: True,
        on_cancel=lambda: cancellations.append(name) or True,
        on_defer_reconnect=lambda: None,
        on_reconnect=lambda: None,
    )


def _send_escape(dialog: QDialog) -> None:
    QCoreApplication.sendEvent(
        dialog,
        QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier),
    )
    QCoreApplication.sendEvent(
        dialog,
        QKeyEvent(QEvent.Type.KeyRelease, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier),
    )
