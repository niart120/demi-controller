from dataclasses import replace

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox

from demi.application.presentation import AdapterOption
from demi.application.settings_editor import SettingsEditor
from demi.domain.settings import AppSettings, ConnectionSettings, DiagnosticLevel
from demi.ui.dialogs.connection import ConnectionDialog, PairingConfirmationDialog


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

    dialog = ConnectionDialog(SettingsEditor(AppSettings.default()), on_rescan=request_rescan)
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
    dialog = ConnectionDialog(SettingsEditor(AppSettings.default()), on_rescan=lambda: None)
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


def test_connection_dialog_requires_explicit_selection_when_saved_adapter_is_missing(
    qt_application: QApplication,
) -> None:
    settings = replace(
        AppSettings.default(),
        connection=ConnectionSettings(adapter_id="usb:missing"),
    )
    editor = SettingsEditor(settings)
    dialog = ConnectionDialog(editor, on_rescan=lambda: None)
    dialog.set_adapters(
        (
            AdapterOption("usb:0", "USB Adapter 0"),
            AdapterOption("usb:1", "USB Adapter 1"),
        )
    )
    dialog.show()
    qt_application.processEvents()

    assert dialog.adapter_combo.currentIndex() == -1
    assert editor.draft.connection.adapter_id == "usb:missing"
    assert not dialog.connect_button.isEnabled()
    assert not dialog.pairing_button.isEnabled()
    assert dialog.discovery_label.text() == (
        "保存済みのUSBアダプターが見つかりません。アダプターを選択してください"
    )

    dialog.adapter_combo.setCurrentIndex(1)
    qt_application.processEvents()

    assert dialog.adapter_combo.itemData(dialog.adapter_combo.currentIndex()) == "usb:1"
    assert editor.draft.connection.adapter_id == "usb:1"
    assert dialog.connect_button.isEnabled()
    assert dialog.pairing_button.isEnabled()


def test_pairing_confirmation_starts_only_after_accept_and_not_while_busy(
    qt_application: QApplication,
) -> None:
    pairing_commands: list[str] = []
    pairing_requests: list[str] = []
    cancellations: list[str] = []

    def confirm_pairing() -> bool:
        pairing_commands.append("start")
        return True

    def cancel_pairing() -> None:
        cancellations.append("cancel")

    def request_pairing() -> bool:
        pairing_requests.append("confirm")
        return True

    editor = SettingsEditor(AppSettings.default())
    connection_dialog = ConnectionDialog(
        editor,
        on_rescan=lambda: None,
        on_request_pairing=request_pairing,
    )
    connection_dialog.set_adapters((AdapterOption("usb:0", "USB Adapter 0"),))
    connection_dialog.adapter_combo.setCurrentIndex(0)
    connection_dialog.pairing_button.click()

    assert pairing_requests == ["confirm"]
    assert pairing_commands == []

    cancelled = PairingConfirmationDialog(
        on_confirm=confirm_pairing,
        on_cancel=cancel_pairing,
    )
    cancelled.show()
    qt_application.processEvents()
    cancel_button = cancelled.button_box.button(QDialogButtonBox.StandardButton.Cancel)
    assert cancel_button is not None
    cancel_button.click()
    qt_application.processEvents()

    assert pairing_commands == []
    assert cancellations == ["cancel"]
    assert cancelled.result() == int(QDialog.DialogCode.Rejected)

    closed = PairingConfirmationDialog(
        on_confirm=confirm_pairing,
        on_cancel=cancel_pairing,
    )
    closed.show()
    qt_application.processEvents()
    closed.close()
    qt_application.processEvents()

    assert pairing_commands == []
    assert cancellations == ["cancel", "cancel"]

    busy = PairingConfirmationDialog(
        on_confirm=confirm_pairing,
        on_cancel=cancel_pairing,
        busy=True,
    )
    busy.show()
    qt_application.processEvents()
    confirm_button = busy.button_box.button(QDialogButtonBox.StandardButton.Ok)
    assert confirm_button is not None
    assert not confirm_button.isEnabled()
    busy.close()
    qt_application.processEvents()

    assert pairing_commands == []
    assert busy.isVisible()

    busy.set_busy(False)
    busy.reject()
    qt_application.processEvents()

    accepted = PairingConfirmationDialog(
        on_confirm=confirm_pairing,
        on_cancel=cancel_pairing,
    )
    accepted.show()
    qt_application.processEvents()
    accept_button = accepted.button_box.button(QDialogButtonBox.StandardButton.Ok)
    assert accept_button is not None
    accept_button.click()
    qt_application.processEvents()

    assert pairing_commands == ["start"]
    assert accepted.result() == int(QDialog.DialogCode.Accepted)


def test_connection_dialog_saves_all_connection_fields_before_requesting_connect(
    qt_application: QApplication,
) -> None:
    editor = SettingsEditor(AppSettings.default())
    saved_connections: list[ConnectionSettings] = []
    dialog = ConnectionDialog(
        editor,
        on_rescan=lambda: None,
        on_save_and_connect=lambda: saved_connections.append(editor.draft.connection) or True,
    )
    dialog.set_adapters((AdapterOption("usb:0", "USB Adapter 0"),))
    dialog.adapter_combo.setCurrentIndex(0)
    dialog.bond_slot_edit.setText("slot-2")
    dialog.timeout_edit.setText("45")
    dialog.reconnect_on_start_checkbox.setChecked(True)
    dialog.diagnostic_level_combo.setCurrentText(DiagnosticLevel.DEBUG.value)
    dialog.show()
    qt_application.processEvents()

    assert dialog.controller_type_label.text() == "Pro Controller"
    assert isinstance(dialog.button_box, QDialogButtonBox)
    assert dialog.connect_button.isEnabled()

    dialog.connect_button.click()
    qt_application.processEvents()

    assert saved_connections == [
        ConnectionSettings(
            adapter_id="usb:0",
            bond_slot="slot-2",
            timeout_seconds=45.0,
            reconnect_on_start=True,
            diagnostic_level=DiagnosticLevel.DEBUG,
        )
    ]
    assert dialog.result() == int(QDialog.DialogCode.Accepted)

    failed = ConnectionDialog(
        SettingsEditor(AppSettings.default()),
        on_rescan=lambda: None,
        on_save_and_connect=lambda: False,
    )
    failed.set_adapters((AdapterOption("usb:0", "USB Adapter 0"),))
    failed.adapter_combo.setCurrentIndex(0)
    failed.show()
    qt_application.processEvents()
    failed.connect_button.click()
    qt_application.processEvents()

    assert failed.isVisible()
    assert failed.connection_error_label.text() == "設定を保存できませんでした"
