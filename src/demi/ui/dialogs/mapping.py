"""Model/view presentation for editable controller input bindings."""

from collections.abc import Callable
from typing import Any, override

from PySide6.QtCore import (
    QAbstractTableModel,
    QEvent,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    Qt,
)
from PySide6.QtGui import QHideEvent, QKeyEvent, QMouseEvent, QShowEvent
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from demi.application.settings_editor import BindingConflict, SettingsEditor
from demi.domain.errors import DomainValueError
from demi.domain.mapping import Binding
from demi.input.qt_adapter import key_source_for_event, mouse_source_for_event

_ROOT_INDEX = QModelIndex()

type CaptureTransition = Callable[[], object]
type SettingsAction = Callable[[], bool]


class MappingTableModel(QAbstractTableModel):
    """Expose the active settings draft as a Qt table model."""

    _HEADERS = ("対象", "入力", "反転", "競合")

    def __init__(self, editor: SettingsEditor, parent: QObject | None = None) -> None:
        """Create a table model backed by one application-owned draft.

        Args:
            editor: Immutable settings draft editor used for all changes.
            parent: Optional Qt parent for model ownership.
        """
        super().__init__(parent)
        self._editor = editor

    @override
    def rowCount(
        self,
        parent: QModelIndex | QPersistentModelIndex = _ROOT_INDEX,
    ) -> int:
        """Return the active binding count for top-level table rows."""
        return 0 if parent.isValid() else len(self._bindings())

    @override
    def columnCount(
        self,
        parent: QModelIndex | QPersistentModelIndex = _ROOT_INDEX,
    ) -> int:
        """Return the fixed number of binding presentation columns."""
        return 0 if parent.isValid() else len(self._HEADERS)

    @override
    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        """Return a textual value for a valid table cell."""
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        binding = self._bindings()[index.row()]
        values = (
            binding.target.value,
            binding.source,
            "はい" if binding.inverted else "いいえ",
            self._conflict_text(index.row()),
        )
        return values[index.column()]

    @override
    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        """Return named horizontal columns without custom cell widgets."""
        if (
            orientation is Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(self._HEADERS)
        ):
            return self._HEADERS[section]
        return super().headerData(section, orientation, role)

    def update_source(self, row: int, source: str) -> None:
        """Replace one source through the application-owned draft editor.

        Args:
            row: Active profile binding row.
            source: Canonical source string selected by the dialog.
        """
        self._editor.update_binding(row, source=source)
        self._reset_from_editor()

    def update_inverted(self, row: int, inverted: bool) -> None:
        """Replace one binding inversion flag through the draft editor.

        Args:
            row: Active profile binding row.
            inverted: Whether the binding is active while its source is absent.
        """
        self._editor.update_binding(row, inverted=inverted)
        self._reset_from_editor()

    def inverted_at(self, row: int) -> bool:
        """Return the inversion state for one active profile row."""
        return self._bindings()[row].inverted

    def restore_default_profile(self) -> None:
        """Restore the standard profile through the application-owned editor."""
        self._editor.reset_profile()
        self._reset_from_editor()

    def conflict_summary(self) -> str:
        """Return all current conflicts as visible, line-separated text."""
        return "\n".join(self._format_conflict(conflict) for conflict in self._editor.conflicts())

    def _bindings(self) -> tuple[Binding, ...]:
        settings = self._editor.draft
        for profile in settings.profiles:
            if profile.id == settings.active_profile:
                return profile.bindings
        raise RuntimeError

    def _conflict_text(self, row: int) -> str:
        conflicts = (
            conflict for conflict in self._editor.conflicts() if row in conflict.binding_indices
        )
        return " / ".join(self._format_conflict(conflict) for conflict in conflicts)

    @staticmethod
    def _format_conflict(conflict: BindingConflict) -> str:
        if conflict.local_action is not None:
            return f"ローカル操作: {conflict.local_action}"
        return f"重複: {conflict.source}"

    def _reset_from_editor(self) -> None:
        self.beginResetModel()
        self.endResetModel()


class MappingDialog(QDialog):
    """Edit one mapping draft with standard Qt model/view controls."""

    def __init__(
        self,
        editor: SettingsEditor,
        *,
        on_dialog_opened: CaptureTransition | None = None,
        on_release_capture: CaptureTransition | None = None,
        on_save: SettingsAction | None = None,
        on_cancel: SettingsAction | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Create a mapping editor without taking ownership of its draft.

        Args:
            editor: Application-owned immutable settings draft editor.
            on_dialog_opened: Neutralizes controller capture before the dialog
                accepts any input.
            on_release_capture: Handles the fixed F12 capture-release action.
            on_save: Saves the application-owned draft and reports success.
            on_cancel: Discards the application-owned draft and reports success.
            parent: Optional Qt parent for dialog ownership.
        """
        super().__init__(parent)
        self.setWindowTitle("キー割り当て")
        self._mapping_model = MappingTableModel(editor, self)
        self._on_dialog_opened = on_dialog_opened
        self._on_release_capture = on_release_capture
        self._on_save = on_save
        self._on_cancel = on_cancel
        self._capture_row: int | None = None
        self._updating_inverted = False
        self._cancel_requested = False
        self._input_filter_application: QApplication | None = None
        self._conflict_confirmation: QMessageBox | None = None

        self.table = QTableView(self)
        self.table.setModel(self._mapping_model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table_header = self.table.horizontalHeader()
        for column in range(3):
            table_header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        table_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.capture_button = QPushButton("次の入力を取得", self)
        self.capture_label = QLabel("入力を取得していません", self)
        self.inverted_checkbox = QCheckBox("反転", self)
        self.inverted_checkbox.setEnabled(False)
        self.save_error_label = QLabel("", self)
        self.restore_button = QPushButton("標準に戻す", self)
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            self,
        )

        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addWidget(self.inverted_checkbox)
        layout.addWidget(self.capture_button)
        layout.addWidget(self.capture_label)
        layout.addWidget(self.save_error_label)
        layout.addWidget(self.restore_button)
        layout.addWidget(self.button_box)
        self.setMinimumSize(640, 520)
        self.resize(720, 640)

        QWidget.setTabOrder(self.table, self.inverted_checkbox)
        QWidget.setTabOrder(self.inverted_checkbox, self.capture_button)
        QWidget.setTabOrder(self.capture_button, self.restore_button)

        self.capture_button.clicked.connect(self.begin_capture)
        self.restore_button.clicked.connect(self.restore_default_profile)
        self.button_box.accepted.connect(self.request_accept)
        self.button_box.rejected.connect(self.request_reject)
        selection_model = self.table.selectionModel()
        if selection_model is not None:
            selection_model.currentRowChanged.connect(self._sync_inverted_checkbox)
        self.inverted_checkbox.toggled.connect(self.set_inverted)

    @property
    def conflict_confirmation(self) -> QMessageBox | None:
        """Return the currently visible binding-conflict confirmation, if any."""
        return self._conflict_confirmation

    def begin_capture(self) -> None:
        """Arm the selected table row for exactly one supported input event."""
        selected = self.table.currentIndex()
        if not selected.isValid():
            self.capture_label.setText("対象を選択してください")
            return
        self._capture_row = selected.row()
        self.capture_label.setText("次のキーまたはマウスボタンを押してください")

    def restore_default_profile(self) -> None:
        """Restore the built-in profile through the application-owned editor."""
        self._mapping_model.restore_default_profile()
        self._capture_row = None
        self.capture_label.setText("標準設定に戻しました")

    def set_source(self, row: int, source: str) -> bool:
        """Update one mapping source while keeping invalid input visible.

        Args:
            row: Selected binding row in the active profile.
            source: Canonical source candidate received by the dialog.

        Returns:
            Whether the draft accepted the candidate source.
        """
        try:
            self._mapping_model.update_source(row, source)
        except DomainValueError:
            self.capture_label.setText("入力を割り当てられません")
            return False
        self.table.selectRow(row)
        self.capture_label.setText(f"入力: {source}")
        return True

    def set_inverted(self, inverted: bool) -> None:
        """Update the selected binding inversion through the draft editor.

        Args:
            inverted: New state requested by the standard check box.
        """
        if self._updating_inverted:
            return
        selected = self.table.currentIndex()
        if not selected.isValid():
            self.inverted_checkbox.setEnabled(False)
            return
        try:
            self._mapping_model.update_inverted(selected.row(), inverted)
        except DomainValueError:
            self.inverted_checkbox.setEnabled(False)
            return
        self.table.selectRow(selected.row())

    def request_accept(self) -> None:
        """Accept immediately or ask for explicit confirmation of conflicts."""
        conflict_summary = self._mapping_model.conflict_summary()
        if not conflict_summary:
            self._save_or_accept()
            return
        if self._conflict_confirmation is not None:
            return
        confirmation = QMessageBox(
            QMessageBox.Icon.Warning,
            "キー割り当ての競合",
            "重複またはローカル操作との競合があります。",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel,
            self,
        )
        confirmation.setInformativeText(conflict_summary)
        confirmation.setDefaultButton(QMessageBox.StandardButton.Cancel)
        confirmation.buttonClicked.connect(self._handle_conflict_confirmation)
        confirmation.finished.connect(self._clear_conflict_confirmation)
        self._conflict_confirmation = confirmation
        confirmation.open()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 - Qt override name.
        """Neutralize capture before accepting dialog-local input events."""
        _invoke(self._on_dialog_opened)
        self._install_input_filter()
        super().showEvent(event)

    def hideEvent(self, event: QHideEvent) -> None:  # noqa: N802 - Qt override name.
        """Stop listening for dialog input once this dialog is hidden."""
        self._capture_row = None
        self._remove_input_filter()
        super().hideEvent(event)

    def request_reject(self) -> None:
        """Discard the draft through the application boundary before closing."""
        self.reject()

    def reject(self) -> None:
        """Discard the active draft before a standard cancel, Esc, or close."""
        if not self._cancel_requested:
            on_cancel = self._on_cancel
            if on_cancel is not None and not on_cancel():
                return
            self._cancel_requested = True
        super().reject()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt override name.
        """Consume a requested binding input before ordinary widget handling."""
        if not self._belongs_to_dialog(watched):
            return False
        if isinstance(event, QKeyEvent) and event.type() is QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_F12:
                self._capture_row = None
                self.capture_label.setText("F12で入力捕捉を解除しました")
                _invoke(self._on_release_capture)
                event.accept()
                return True
            return self._capture_source(key_source_for_event(event))
        if isinstance(event, QMouseEvent) and event.type() is QEvent.Type.MouseButtonPress:
            return self._capture_source(mouse_source_for_event(event))
        return False

    def _capture_source(self, source: str | None) -> bool:
        row = self._capture_row
        if row is None:
            return False
        if source is None:
            return True
        if self.set_source(row, source):
            self._capture_row = None
        return True

    def _sync_inverted_checkbox(self, current: QModelIndex, _previous: QModelIndex) -> None:
        if not current.isValid():
            self.inverted_checkbox.setEnabled(False)
            return
        self._updating_inverted = True
        try:
            self.inverted_checkbox.setEnabled(True)
            self.inverted_checkbox.setChecked(self._mapping_model.inverted_at(current.row()))
        finally:
            self._updating_inverted = False

    def _handle_conflict_confirmation(self, button: QAbstractButton) -> None:
        confirmation = self._conflict_confirmation
        if (
            confirmation is not None
            and confirmation.standardButton(button) == QMessageBox.StandardButton.Save
        ):
            self._save_or_accept()

    def _save_or_accept(self) -> None:
        on_save = self._on_save
        if on_save is not None and not on_save():
            self.save_error_label.setText("設定を保存できませんでした")
            return
        self.save_error_label.clear()
        self.accept()

    def _clear_conflict_confirmation(self, _result: int) -> None:
        self._conflict_confirmation = None

    def _install_input_filter(self) -> None:
        if self._input_filter_application is not None:
            return
        application = QApplication.instance()
        if isinstance(application, QApplication):
            application.installEventFilter(self)
            self._input_filter_application = application

    def _remove_input_filter(self) -> None:
        application = self._input_filter_application
        if application is not None:
            application.removeEventFilter(self)
            self._input_filter_application = None

    def _belongs_to_dialog(self, watched: QObject) -> bool:
        return watched is self or (isinstance(watched, QWidget) and self.isAncestorOf(watched))


def _invoke(callback: CaptureTransition | None) -> None:
    if callback is not None:
        callback()
