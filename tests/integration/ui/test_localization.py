from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QColorDialog, QDialogButtonBox, QLabel

from demi.app import WindowSpec
from demi.application.settings_editor import SettingsEditor
from demi.config.codec import encode_settings
from demi.domain.settings import AppSettings, UiLanguage
from demi.ui.application import QtApplicationRunner
from demi.ui.dialogs.colors import ControllerColorsDialog
from demi.ui.dialogs.connection import ConnectionDialog
from demi.ui.dialogs.mapping import MappingDialog
from demi.ui.main_window import MainWindow


def test_default_user_interface_uses_english_source_text(
    qt_application: QApplication,
) -> None:
    assert qt_application is not None
    window = MainWindow(WindowSpec(width=960, height=640, maximized=False))
    mapping_editor = SettingsEditor(AppSettings.default())
    mapping = MappingDialog(mapping_editor)
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
    assert window.status_bar.adapter_label.text() == "Adapter: None"
    assert mapping.windowTitle() == "Key mappings"
    assert mapping.table.model().headerData(0, Qt.Orientation.Horizontal) == "Target"
    assert mapping.table.model().data(mapping.table.model().index(0, 2)) == "No"
    assert mapping.capture_button.text() == "Capture next input"
    assert mapping.mouse_gyro_group.title() == "Mouse gyro settings"
    assert connection.windowTitle() == "Connection settings"
    assert connection.rescan_button.text() == "Rescan"
    assert connection.pairing_button.text() == "Pair new controller"
    assert connection.discovery_label.text() == "Search for USB adapters"
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


def test_japanese_language_installs_app_and_qt_translators_before_widgets(
    qt_application: QApplication,
) -> None:
    runner = QtApplicationRunner()
    window = runner.create_main_window(
        WindowSpec(
            width=960,
            height=640,
            maximized=False,
            language=UiLanguage.JAPANESE,
        )
    )
    mapping_editor = SettingsEditor(AppSettings.default())
    mapping = MappingDialog(mapping_editor)
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
    color_picker = QColorDialog()

    assert window.main_toolbar.connection_action.text() == "接続"
    assert window.status_bar.adapter_label.text() == "アダプター: なし"
    assert mapping.windowTitle() == "キー割り当て"
    assert mapping.table.model().data(mapping.table.model().index(0, 2)) == "いいえ"
    assert mapping.capture_button.text() == "次の入力を取得"
    assert mapping.mouse_gyro_group.title() == "マウスジャイロ設定"
    assert "ピッチ上限" in {
        label.text() for label in mapping.findChildren(QLabel)
    }
    assert connection.windowTitle() == "接続設定"
    assert connection.pairing_button.text() == "新規ペアリング"
    assert connection.discovery_label.text() == "USBアダプターを検索してください"
    assert colors.windowTitle() == "コントローラーカラー"
    assert color_picker.windowTitle() == "色を選択"

    encoded = encode_settings(mapping_editor.draft)
    profiles = encoded["profiles"]
    assert isinstance(profiles, list)
    profile = cast("dict[str, object]", profiles[0])
    bindings = profile["bindings"]
    assert isinstance(bindings, list)
    binding = cast("dict[str, object]", bindings[0])
    connection_settings = cast("dict[str, object]", encoded["connection"])
    assert binding["source"] == "KEY:F"
    assert binding["target"] == "BUTTON:A"
    assert connection_settings["diagnostic_level"] == "INFO"

    for dialog in (mapping, colors):
        save_button = dialog.button_box.button(QDialogButtonBox.StandardButton.Save)
        cancel_button = dialog.button_box.button(QDialogButtonBox.StandardButton.Cancel)
        assert save_button is not None
        assert cancel_button is not None
        assert save_button.text() == "保存"
        assert cancel_button.text() == "キャンセル"

    color_picker.close()
    colors.close()
    connection.close()
    mapping.close()
    window.close()
    assert qt_application is runner.application
