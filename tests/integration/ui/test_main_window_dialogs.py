from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QWidget

from demi.app import WindowSpec
from demi.application.state import AppState, ConnectionState
from demi.ui.main_window import MainWindow
from demi.ui.toolbar import ToolbarState


def test_main_window_opens_one_injected_settings_dialog_per_toolbar_action(
    qt_application: QApplication,
) -> None:
    window = MainWindow(WindowSpec(width=960, height=640, maximized=False))
    opened: list[QDialog] = []

    def factory(name: str) -> Callable[[QWidget], QDialog]:
        def create(parent: QWidget) -> QDialog:
            dialog = QDialog(parent)
            dialog.setObjectName(name)
            opened.append(dialog)
            return dialog

        return create

    window.bind_settings_dialog_factories(
        connection=factory("connection"),
        bindings=factory("bindings"),
        mouse=factory("mouse"),
        colors=factory("colors"),
    )
    window.main_toolbar.refresh(
        ToolbarState(
            application_state=AppState.IDLE,
            connection_state=ConnectionState.READY,
            dialog_open=False,
        )
    )

    window.main_toolbar.connection_settings_action.trigger()
    qt_application.processEvents()

    assert [dialog.objectName() for dialog in opened] == ["connection"]
    assert window.active_settings_dialog is opened[0]
    assert opened[0].parentWidget() is window
    assert opened[0].windowModality() is Qt.WindowModality.WindowModal
    assert opened[0].isVisible()

    window.main_toolbar.bindings_action.trigger()
    qt_application.processEvents()

    assert [dialog.objectName() for dialog in opened] == ["connection"]

    opened[0].reject()
    qt_application.processEvents()

    assert window.active_settings_dialog is None

    window.main_toolbar.bindings_action.trigger()
    qt_application.processEvents()
    opened[1].reject()
    qt_application.processEvents()
    window.main_toolbar.mouse_action.trigger()
    qt_application.processEvents()
    opened[2].reject()
    qt_application.processEvents()
    window.main_toolbar.colors_action.trigger()
    qt_application.processEvents()

    assert [dialog.objectName() for dialog in opened] == [
        "connection",
        "bindings",
        "mouse",
        "colors",
    ]
    assert window.active_settings_dialog is opened[3]
