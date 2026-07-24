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
from demi.ui.dialogs.settings import SettingsDialog, SettingsTab
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
    assert window.main_toolbar.mouse_input_status.text() == "Mouse input: OFF (F5)"
    assert window.main_toolbar.settings_button.text() == "Settings"
    assert [action.text() for action in window.main_toolbar.settings_menu.actions()] == [
        "Connection",
        "Bindings",
        "Mouse",
        "Colors",
    ]
    assert window.status_bar.adapter_label.text() == "Adapter: None"
    assert mapping.windowTitle() == "Key mappings"
    assert mapping.table.model().headerData(0, Qt.Orientation.Horizontal) == "Target"
    assert (
        mapping.table.model().data(
            mapping.table.model().index(0, 2),
            Qt.ItemDataRole.CheckStateRole,
        )
        == Qt.CheckState.Unchecked
    )
    assert mapping.mouse_gyro_group.title() == "Mouse gyro settings"
    assert [action.text() for action in mapping.add_binding_menu.actions()] == [
        "Buttons",
        "Left stick",
        "Right stick",
        "Diagnostics",
    ]
    assert connection.windowTitle() == "Connection settings"
    assert connection.rescan_button.text() == "Rescan"
    assert connection.pairing_button.text() == "Pair new controller"
    assert connection.discovery_label.text() == "Search for USB adapters"
    assert colors.windowTitle() == "Controller colors"
    assert {button.accessibleName() for button in colors.color_buttons.values()} == {
        "Body",
        "Buttons",
        "Left grip",
        "Right grip",
    }
    assert colors.color_buttons["body"].property("swatchColor") == "#323232"
    assert "Choose a color" in colors.color_buttons["body"].accessibleDescription()
    assert {"Body", "Buttons", "Left grip", "Right grip"}.issubset(
        {label.text() for label in colors.findChildren(QLabel)}
    )
    assert "#323232" in colors.color_buttons["body"].accessibleDescription()

    for dialog in (mapping, colors):
        save_button = dialog.button_box.button(QDialogButtonBox.StandardButton.Save)
        cancel_button = dialog.button_box.button(QDialogButtonBox.StandardButton.Cancel)
        assert save_button is not None
        assert cancel_button is not None
        assert save_button.text() == "Save"
        assert cancel_button.text() == "Cancel"

    assert connection.save_button.text() == "Save"
    assert connection.profile_group.title() == "Controller profile"
    assert connection.global_settings_group.title() == "Global settings"
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
    settings_dialog = SettingsDialog(
        SettingsEditor(AppSettings.default()),
        initial_tab=SettingsTab.BINDINGS,
        connected=False,
        on_rescan=lambda: None,
        on_save=lambda: True,
        on_cancel=lambda: True,
        on_preview=lambda _colors: None,
        on_delete_profile=lambda: True,
        on_request_pairing=lambda: True,
        on_defer_reconnect=lambda: None,
        on_reconnect=lambda: None,
    )

    assert window.main_toolbar.connection_action.text() == "接続"
    assert window.main_toolbar.settings_button.text() == "設定"
    assert [action.text() for action in window.main_toolbar.settings_menu.actions()] == [
        "接続",
        "割り当て",
        "マウス",
        "色",
    ]
    assert window.status_bar.adapter_label.text() == "アダプター: なし"
    assert mapping.windowTitle() == "キー割り当て"
    assert mapping.tabs.tabText(0) == "割り当て"
    assert mapping.tabs.tabText(1) == "マウスジャイロ"
    assert (
        mapping.table.model().data(
            mapping.table.model().index(0, 2),
            Qt.ItemDataRole.CheckStateRole,
        )
        == Qt.CheckState.Unchecked
    )
    assert mapping.table.model().data(mapping.table.model().index(4, 1)) == "中央マウス"
    assert (
        mapping.table.model().data(mapping.table.model().index(4, 1), Qt.ItemDataRole.UserRole)
        == "MOUSE:MIDDLE"
    )
    assert mapping.table.model().data(mapping.table.model().index(4, 1)) == "中央マウス"
    assert (
        mapping.table.model().data(
            mapping.table.model().index(4, 1),
            Qt.ItemDataRole.UserRole,
        )
        == "MOUSE:MIDDLE"
    )
    assert mapping.mouse_gyro_group.title() == "マウスジャイロ設定"
    assert "ピッチ上限" in {label.text() for label in mapping.findChildren(QLabel)}
    assert connection.windowTitle() == "接続設定"
    assert connection.pairing_button.text() == "新規ペアリング"
    assert connection.discovery_label.text() == "USBアダプターを検索してください"
    assert settings_dialog.windowTitle() == "設定"
    assert [
        settings_dialog.tabs.tabText(index) for index in range(settings_dialog.tabs.count())
    ] == ["接続", "割り当て", "マウス", "色"]
    assert settings_dialog.mapping_page.add_binding_button.text() == "割り当てを追加"
    assert [
        action.text() for action in settings_dialog.mapping_page.add_binding_menu.actions()
    ] == ["ボタン", "左スティック", "右スティック", "診断"]
    assert (
        settings_dialog.mapping_page.mapping_model.headerData(
            5,
            Qt.Orientation.Horizontal,
        )
            == ""
    )
    assert settings_dialog.connection_page.profile_group.title() == ("コントローラープロファイル")
    assert settings_dialog.connection_page.global_settings_group.title() == "全体設定"
    assert settings_dialog.connection_page.delete_profile_button.text() == ("プロファイルを削除")
    assert colors.windowTitle() == "コントローラーカラー"
    assert {button.accessibleName() for button in colors.color_buttons.values()} == {
        "本体",
        "ボタン",
        "左グリップ",
        "右グリップ",
    }
    assert colors.color_buttons["body"].property("swatchColor") == "#323232"
    assert "色を選択" in colors.color_buttons["body"].accessibleDescription()
    assert {"本体", "ボタン", "左グリップ", "右グリップ"}.issubset(
        {label.text() for label in colors.findChildren(QLabel)}
    )
    assert "#323232" in colors.color_buttons["body"].accessibleDescription()
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
    settings_dialog.close()
    colors.close()
    connection.close()
    mapping.close()
    window.close()
    assert qt_application is runner.application
