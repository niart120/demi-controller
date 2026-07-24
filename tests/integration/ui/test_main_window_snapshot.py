from dataclasses import replace

from PySide6.QtWidgets import QApplication, QWidget

from demi.app import WindowSpec
from demi.application.presentation import AdapterOption
from demi.application.settings_editor import SettingsEditor
from demi.application.state import AppState, ConnectionState
from demi.application.ui_state import ApplicationUiSnapshot
from demi.domain.settings import AppSettings, ConnectionSettings
from demi.ui.dialogs.connection import ConnectionDialog
from demi.ui.main_window import MainWindow


def test_main_window_refreshes_toolbar_and_status_bar_from_application_snapshot(
    qt_application: QApplication,
) -> None:
    assert qt_application is not None
    window = MainWindow(WindowSpec(width=960, height=640, maximized=False))

    window.refresh(
        ApplicationUiSnapshot(
            application_state=AppState.CAPTURED,
            connection_state=ConnectionState.CONNECTED,
            adapter_label="Bluetooth adapter",
            adapters=(),
            dialog_open=False,
            preview_only=False,
            warning="",
            error=None,
            color_reconnect_pending=False,
        )
    )

    assert window.main_toolbar.connection_action.text() == "Disconnect"
    assert window.main_toolbar.connection_action.isEnabled()
    assert window.main_toolbar.capture_action.text() == "Stop mouse"
    assert window.main_toolbar.capture_action.isChecked()
    assert window.status_bar.adapter_label.text() == "Adapter: Bluetooth adapter"
    assert window.status_bar.connection_label.text() == "Connection: Connected"
    assert window.status_bar.capture_label.text() == "Mouse capture: On"
    assert window.status_bar.preview_label.text() == "Preview: transmitting"


def test_main_window_prioritizes_primary_actions_connection_status_and_preview(
    qt_application: QApplication,
) -> None:
    window = MainWindow(WindowSpec(width=960, height=640, maximized=False))
    window.show()
    qt_application.processEvents()

    assert window.main_toolbar.actions()[:2] == [
        window.main_toolbar.connection_action,
        window.main_toolbar.capture_action,
    ]
    assert not window.main_toolbar.isMovable()
    assert not window.main_toolbar.isFloatable()
    assert (
        window.status_bar.connection_label.geometry().left()
        < window.status_bar.adapter_label.geometry().left()
    )
    assert (
        window.status_bar.notice_label.geometry().left()
        < window.status_bar.preview_label.geometry().left()
    )
    assert window.main_toolbar.geometry().bottom() < window.controller_preview.geometry().top()
    assert window.controller_preview.geometry().bottom() < window.status_bar.geometry().top()


def test_main_window_disables_busy_connection_and_reenables_a_retryable_error(
    qt_application: QApplication,
) -> None:
    assert qt_application is not None
    window = MainWindow(WindowSpec(width=960, height=640, maximized=False))

    window.refresh(
        ApplicationUiSnapshot(
            application_state=AppState.IDLE,
            connection_state=ConnectionState.CONNECTING,
            adapter_label="Bluetooth adapter",
            adapters=(),
            dialog_open=False,
            preview_only=True,
            warning="Pairing in progress",
            error=None,
            color_reconnect_pending=False,
        )
    )

    assert not window.main_toolbar.connection_action.isEnabled()
    assert window.status_bar.connection_label.text() == "Connection: Connecting"
    assert window.status_bar.notice_label.text() == "Warning: Pairing in progress"

    window.refresh(
        ApplicationUiSnapshot(
            application_state=AppState.IDLE,
            connection_state=ConnectionState.ERROR,
            adapter_label="Bluetooth adapter",
            adapters=(),
            dialog_open=False,
            preview_only=True,
            warning="Connection failed",
            error="Connection failed",
            color_reconnect_pending=False,
        )
    )

    assert window.main_toolbar.connection_action.isEnabled()
    assert window.status_bar.connection_label.text() == "Connection: Error"
    assert window.status_bar.notice_label.text() == "Error: Connection failed"

    window.refresh(
        ApplicationUiSnapshot(
            application_state=AppState.IDLE,
            connection_state=ConnectionState.ERROR,
            adapter_label="Bluetooth adapter",
            adapters=(),
            dialog_open=False,
            preview_only=True,
            warning="接続に失敗しました",
            error="接続に失敗しました",
            color_reconnect_pending=False,
            connection_retryable=False,
        )
    )

    assert not window.main_toolbar.connection_action.isEnabled()


def test_main_window_refreshes_connection_candidates_without_auto_selecting(
    qt_application: QApplication,
) -> None:
    assert qt_application is not None
    window = MainWindow(WindowSpec(width=960, height=640, maximized=False))
    editor = SettingsEditor(
        replace(
            AppSettings.default(),
            connection=ConnectionSettings(adapter_id="usb:missing"),
        )
    )

    def create_connection_dialog(parent: QWidget) -> ConnectionDialog:
        return ConnectionDialog(editor, on_rescan=lambda: None, parent=parent)

    window.bind_settings_dialog_factories(
        connection=create_connection_dialog,
        bindings=lambda _parent: None,
        mouse=lambda _parent: None,
        colors=lambda _parent: None,
    )
    window.refresh(
        ApplicationUiSnapshot(
            application_state=AppState.IDLE,
            connection_state=ConnectionState.READY,
            adapter_label="なし",
            adapters=(
                AdapterOption("usb:0", "USB Adapter 0"),
                AdapterOption("usb:1", "USB Adapter 1"),
            ),
            dialog_open=False,
            preview_only=True,
            warning="",
            error=None,
            color_reconnect_pending=False,
        )
    )
    window.main_toolbar.connection_settings_action.trigger()
    qt_application.processEvents()

    dialog = window.active_settings_dialog
    assert isinstance(dialog, ConnectionDialog)
    assert window.main_toolbar.connection_action.isEnabled()
    assert dialog.adapter_model.rowCount() == 2
    assert dialog.adapter_combo.currentIndex() == -1
    assert editor.draft.connection.adapter_id == "usb:missing"
    assert dialog.save_button.isEnabled()
    assert not dialog.pairing_button.isEnabled()

    window.refresh(
        ApplicationUiSnapshot(
            application_state=AppState.IDLE,
            connection_state=ConnectionState.READY,
            adapter_label="なし",
            adapters=(),
            dialog_open=True,
            preview_only=True,
            warning="",
            error=None,
            color_reconnect_pending=False,
        )
    )

    assert dialog.adapter_model.rowCount() == 0
    assert not dialog.adapter_combo.isEnabled()
    assert dialog.rescan_button.isEnabled()
    assert dialog.save_button.isEnabled()
    assert not dialog.pairing_button.isEnabled()
