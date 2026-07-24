from PySide6.QtCore import QEvent, QPointF, QRect, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QStyleOptionViewItem

from demi.application.settings_editor import SettingsEditor
from demi.domain.settings import AppSettings
from demi.ui.dialogs.mapping import MappingActionDelegate, MappingDialog, MappingTableModel


def test_mapping_delegate_routes_mouse_and_keyboard_activation_to_the_same_row(
    qt_application: object,
) -> None:
    assert qt_application is not None
    model = MappingTableModel(SettingsEditor(AppSettings.default()))
    activated_rows: list[int] = []
    delegate = MappingActionDelegate(on_activated=activated_rows.append)
    index = model.index(3, 3)
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 120, 32)

    mouse = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPointF(60.0, 16.0),
        QPointF(60.0, 16.0),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    assert delegate.editorEvent(mouse, model, option, index) is True
    assert (
        delegate.editorEvent(
            QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier),
            model,
            option,
            index,
        )
        is True
    )

    assert activated_rows == [3, 3]
    assert model.data(index, Qt.ItemDataRole.DisplayRole) == "Remap"


def test_mapping_dialog_uses_shared_delegates_without_per_row_widgets(
    qt_application: object,
) -> None:
    assert qt_application is not None
    dialog = MappingDialog(SettingsEditor(AppSettings.default()))

    assert isinstance(dialog.table.itemDelegateForColumn(3), MappingActionDelegate)
    assert isinstance(dialog.table.itemDelegateForColumn(5), MappingActionDelegate)
    assert all(
        dialog.table.indexWidget(dialog.mapping_model.index(row, column)) is None
        for row in range(33)
        for column in (3, 5)
    )
