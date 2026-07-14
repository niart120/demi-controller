from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from demi.application.presentation import AdapterOption
from demi.ui.dialogs.connection import ConnectionDialog


def test_connection_dialog_requests_rescan_and_updates_adapters_without_blocking(
    qt_application: QApplication,
) -> None:
    requests: list[str] = []
    event_loop_progress: list[str] = []

    def request_rescan() -> None:
        requests.append("rescan")
        QTimer.singleShot(
            0,
            lambda: dialog.set_adapters(
                (
                    AdapterOption("usb:0", "USB Adapter 0"),
                    AdapterOption("usb:1", "USB Adapter 1"),
                )
            ),
        )

    dialog = ConnectionDialog(on_rescan=request_rescan)
    dialog.show()
    qt_application.processEvents()

    dialog.rescan_button.click()
    QTimer.singleShot(0, lambda: event_loop_progress.append("processed"))

    assert requests == ["rescan"]
    assert not dialog.rescan_button.isEnabled()

    qt_application.processEvents()

    assert event_loop_progress == ["processed"]
    assert dialog.adapter_model.rowCount() == 2
    assert dialog.adapter_combo.itemText(0) == "USB Adapter 0"
    assert dialog.adapter_combo.itemData(0) == "usb:0"
    assert dialog.rescan_button.isEnabled()


def test_connection_dialog_with_no_adapters_keeps_only_rescan_available(
    qt_application: QApplication,
) -> None:
    dialog = ConnectionDialog(on_rescan=lambda: None)
    dialog.set_adapters(())
    dialog.show()
    qt_application.processEvents()

    assert dialog.adapter_model.rowCount() == 0
    assert not dialog.adapter_combo.isEnabled()
    assert not dialog.connect_button.isEnabled()
    assert not dialog.pairing_button.isEnabled()
    assert dialog.rescan_button.isEnabled()
    assert dialog.discovery_label.text() == (
        "利用可能なUSBアダプターがありません。接続機器を確認して再検索してください"
    )
