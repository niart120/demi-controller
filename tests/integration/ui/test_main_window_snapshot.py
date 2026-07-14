from PySide6.QtWidgets import QApplication

from demi.app import WindowSpec
from demi.application.state import AppState, ConnectionState
from demi.application.ui_state import ApplicationUiSnapshot
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
            dialog_open=False,
            preview_only=False,
            warning="",
            error=None,
            color_reconnect_pending=False,
        )
    )

    assert window.main_toolbar.connection_action.text() == "切断"
    assert window.main_toolbar.connection_action.isEnabled()
    assert window.main_toolbar.capture_action.text() == "入力解除"
    assert window.main_toolbar.capture_action.isChecked()
    assert window.status_bar.adapter_label.text() == "アダプター: Bluetooth adapter"
    assert window.status_bar.connection_label.text() == "接続: 接続済み"
    assert window.status_bar.capture_label.text() == "入力: 捕捉中"
    assert window.status_bar.preview_label.text() == "プレビュー: 送信あり"
