from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox

from demi.application.presentation import AdapterOption
from demi.application.settings_editor import SettingsEditor
from demi.domain.mapping import BindingTarget
from demi.domain.settings import AppSettings
from demi.ui.dialogs.settings import SettingsDialog, SettingsTab


def test_settings_dialog_shares_one_draft_across_four_flat_tabs_and_saves_once(
    qt_application: QApplication,
) -> None:
    editor = SettingsEditor(AppSettings.default())
    saved: list[AppSettings] = []
    dialog = SettingsDialog(
        editor,
        initial_tab=SettingsTab.CONNECTION,
        connected=False,
        on_rescan=lambda: None,
        on_save=lambda: saved.append(editor.draft) or True,
        on_cancel=lambda: True,
        on_preview=lambda _colors: None,
        on_delete_profile=lambda: True,
        on_request_pairing=lambda: True,
        on_defer_reconnect=lambda: None,
        on_reconnect=lambda: None,
    )
    dialog.connection_page.set_adapters((AdapterOption("usb:0", "USB Adapter 0"),))
    dialog.show()
    qt_application.processEvents()

    assert dialog.windowTitle() == "Settings"
    assert [dialog.tabs.tabText(index) for index in range(dialog.tabs.count())] == [
        "Connection",
        "Bindings",
        "Mouse",
        "Colors",
    ]
    assert dialog.current_tab is SettingsTab.CONNECTION
    assert dialog.tabs.widget(SettingsTab.BINDINGS) is dialog.mapping_page.bindings_page
    assert dialog.tabs.widget(SettingsTab.MOUSE) is dialog.mapping_page.mouse_page
    assert not dialog.mapping_page.tabs.isVisible()
    assert not dialog.mapping_page.button_box.isVisible()
    assert not dialog.connection_page.button_box.isVisible()
    assert not dialog.colors_page.button_box.isVisible()

    dialog.connection_page.adapter_combo.setCurrentIndex(0)
    dialog.connection_page.reconnect_on_start_checkbox.setChecked(True)
    button_menu = dialog.mapping_page.add_binding_group_menus["Buttons"]
    add_button_a = next(
        action for action in button_menu.actions() if action.data() == BindingTarget.BUTTON_A
    )
    add_button_a.trigger()
    assert dialog.colors_page.set_color("body", "#ABCDEF")

    dialog.tabs.setCurrentIndex(SettingsTab.BINDINGS)
    assert editor.draft.connection.adapter_id == "usb:0"
    assert editor.draft.connection.reconnect_on_start is False
    assert editor.draft.profiles[0].bindings[-1].target is BindingTarget.BUTTON_A
    assert editor.draft.controller_colors.body == "#ABCDEF"

    save_button = dialog.button_box.button(QDialogButtonBox.StandardButton.Save)
    assert save_button is not None
    save_button.click()
    qt_application.processEvents()

    assert len(saved) == 1
    assert saved[0].connection.reconnect_on_start is True
    assert saved[0].profiles[0].bindings[-1].target is BindingTarget.BUTTON_A
    assert saved[0].controller_colors.body == "#ABCDEF"
    assert dialog.result() == int(QDialog.DialogCode.Accepted)


def test_settings_dialog_cancel_discards_once_and_restores_the_saved_color_preview(
    qt_application: QApplication,
) -> None:
    original = AppSettings.default()
    editor = SettingsEditor(original)
    previews = []
    cancellations: list[str] = []
    dialog = SettingsDialog(
        editor,
        initial_tab=SettingsTab.COLORS,
        connected=False,
        on_rescan=lambda: None,
        on_save=lambda: True,
        on_cancel=lambda: cancellations.append("cancel") or True,
        on_preview=previews.append,
        on_delete_profile=lambda: True,
        on_request_pairing=lambda: True,
        on_defer_reconnect=lambda: None,
        on_reconnect=lambda: None,
    )
    dialog.show()
    qt_application.processEvents()

    assert dialog.colors_page.set_color("body", "#ABCDEF")
    dialog.reject()
    qt_application.processEvents()

    assert cancellations == ["cancel"]
    assert previews[-1] == original.controller_colors
    assert dialog.result() == int(QDialog.DialogCode.Rejected)


def test_settings_dialog_escape_from_an_embedded_page_cancels_the_whole_draft_once(
    qt_application: QApplication,
) -> None:
    editor = SettingsEditor(AppSettings.default())
    cancellations: list[str] = []
    dialog = SettingsDialog(
        editor,
        initial_tab=SettingsTab.BINDINGS,
        connected=False,
        on_rescan=lambda: None,
        on_save=lambda: True,
        on_cancel=lambda: cancellations.append("cancel") or True,
        on_preview=lambda _colors: None,
        on_delete_profile=lambda: True,
        on_request_pairing=lambda: True,
        on_defer_reconnect=lambda: None,
        on_reconnect=lambda: None,
    )
    dialog.show()
    qt_application.processEvents()
    dialog.mapping_page.table.setFocus()

    QTest.keyClick(dialog.mapping_page.table, Qt.Key.Key_Escape)
    qt_application.processEvents()

    assert cancellations == ["cancel"]
    assert dialog.result() == int(QDialog.DialogCode.Rejected)
