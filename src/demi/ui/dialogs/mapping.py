"""Model/view presentation for editable controller input bindings."""

from collections.abc import Callable
from typing import Any, override

from PySide6.QtCore import (
    QAbstractItemModel,
    QAbstractTableModel,
    QCoreApplication,
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
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from demi.application.settings_editor import BindingConflict, SettingsEditor
from demi.domain.errors import DomainValueError
from demi.domain.mapping import Binding, is_button_target
from demi.input.qt_adapter import key_source_for_event, mouse_source_for_event

_ROOT_INDEX = QModelIndex()

type CaptureTransition = Callable[[], object]
type SettingsAction = Callable[[], bool]
type RowAction = Callable[[int], object]


class MappingActionDelegate(QStyledItemDelegate):
    """Turn one painted action cell into a mouse and keyboard row command."""

    def __init__(
        self,
        *,
        on_activated: RowAction,
        parent: QObject | None = None,
    ) -> None:
        """Create a delegate that reports the activated model row.

        Args:
            on_activated: Command receiving the activated binding row.
            parent: Optional Qt owner.
        """
        super().__init__(parent)
        self._on_activated = on_activated

    @override
    def editorEvent(
        self,
        event: QEvent,
        model: QAbstractItemModel,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> bool:
        """Activate the indexed row from a left click, Enter, or Space."""
        del model
        if isinstance(event, QMouseEvent):
            if (
                event.type() is QEvent.Type.MouseButtonRelease
                and event.button() is Qt.MouseButton.LeftButton
                and option.rect.contains(event.position().toPoint())
            ):
                self._on_activated(index.row())
                return True
            return False
        if (
            isinstance(event, QKeyEvent)
            and event.type() is QEvent.Type.KeyPress
            and event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space}
        ):
            self._on_activated(index.row())
            return True
        return False


class MappingTableModel(QAbstractTableModel):
    """Expose the active settings draft as a Qt table model."""

    _HEADERS = ("Target", "Input", "Inverted", "Conflict", "Action")

    def __init__(self, editor: SettingsEditor, parent: QObject | None = None) -> None:
        """Create a table model backed by one application-owned draft.

        Args:
            editor: Immutable settings draft editor used for all changes.
            parent: Optional Qt parent for model ownership.
        """
        super().__init__(parent)
        self._editor = editor
        self._capture_row: int | None = None

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
        input_text = (
            self.tr("Press a key or mouse button")
            if index.row() == self._capture_row
            else binding.source
        )
        action_text = self.tr("Cancel") if index.row() == self._capture_row else self.tr("Remap")
        values = (
            binding.target.value,
            input_text,
            self.tr("Yes") if binding.inverted else self.tr("No"),
            self._conflict_text(index.row()),
            action_text,
        )
        return values[index.column()]

    @property
    def capture_row(self) -> int | None:
        """Return the row currently waiting for an input source."""
        return self._capture_row

    def begin_capture(self, row: int) -> None:
        """Mark one binding row as waiting for its replacement source."""
        if not 0 <= row < self.rowCount():
            raise DomainValueError
        self._capture_row = row
        self._reset_from_editor()

    def cancel_capture(self) -> None:
        """Clear the waiting row without changing the settings draft."""
        if self._capture_row is None:
            return
        self._capture_row = None
        self._reset_from_editor()

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
            return self.tr(self._HEADERS[section])
        return super().headerData(section, orientation, role)

    def update_source(self, row: int, source: str) -> None:
        """Replace one source through the application-owned draft editor.

        Args:
            row: Active profile binding row.
            source: Canonical source string selected by the dialog.
        """
        self._editor.update_binding(row, source=source)
        self._capture_row = None
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

    def is_invertible_at(self, row: int) -> bool:
        """Return whether one active profile row supports inversion."""
        return is_button_target(self._bindings()[row].target)

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
            return QCoreApplication.translate("MappingTableModel", "Local action: {action}").format(
                action=conflict.local_action
            )
        return QCoreApplication.translate("MappingTableModel", "Duplicate: {source}").format(
            source=conflict.source
        )

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
            on_release_capture: Handles the fixed F4 capture-release action.
            on_save: Saves the application-owned draft and reports success.
            on_cancel: Discards the application-owned draft and reports success.
            parent: Optional Qt parent for dialog ownership.
        """
        super().__init__(parent)
        self.setWindowTitle(self.tr("Key mappings"))
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
        self._mapping_action_delegate = MappingActionDelegate(
            on_activated=self._activate_row_action,
            parent=self.table,
        )
        self.table.setItemDelegateForColumn(4, self._mapping_action_delegate)
        table_header = self.table.horizontalHeader()
        for column in range(3):
            table_header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        table_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        table_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.capture_button = QPushButton(self.tr("Capture next input"), self)
        self.capture_label = QLabel(self.tr("No input captured"), self)
        self.inverted_checkbox = QCheckBox(self.tr("Inverted"), self)
        self.inverted_checkbox.setEnabled(False)
        mouse_settings = editor.draft.input.mouse
        self.mouse_gyro_group = QGroupBox(self.tr("Mouse gyro settings"), self)
        mouse_gyro_form = QFormLayout(self.mouse_gyro_group)
        self.mouse_gyro_enabled_checkbox = QCheckBox(self.tr("Enabled"), self.mouse_gyro_group)
        self.mouse_gyro_enabled_checkbox.setChecked(mouse_settings.gyro_enabled)
        self.horizontal_sensitivity_spinbox = _sensitivity_spinbox(
            self.mouse_gyro_group,
            mouse_settings.horizontal_sensitivity,
        )
        self.vertical_sensitivity_spinbox = _sensitivity_spinbox(
            self.mouse_gyro_group,
            mouse_settings.vertical_sensitivity,
        )
        self.invert_x_checkbox = QCheckBox(self.tr("Invert horizontally"), self.mouse_gyro_group)
        self.invert_x_checkbox.setChecked(mouse_settings.invert_x)
        self.invert_y_checkbox = QCheckBox(self.tr("Invert vertically"), self.mouse_gyro_group)
        self.invert_y_checkbox.setChecked(mouse_settings.invert_y)
        self.pitch_limit_spinbox = QDoubleSpinBox(self.mouse_gyro_group)
        self.pitch_limit_spinbox.setRange(1.0, 89.0)
        self.pitch_limit_spinbox.setDecimals(1)
        self.pitch_limit_spinbox.setSingleStep(1.0)
        self.pitch_limit_spinbox.setSuffix(" °")
        self.pitch_limit_spinbox.setValue(mouse_settings.pitch_limit_degrees)
        mouse_gyro_form.addRow(self.mouse_gyro_enabled_checkbox)
        mouse_gyro_form.addRow(
            self.tr("Horizontal sensitivity"), self.horizontal_sensitivity_spinbox
        )
        mouse_gyro_form.addRow(self.tr("Vertical sensitivity"), self.vertical_sensitivity_spinbox)
        mouse_gyro_form.addRow(self.invert_x_checkbox)
        mouse_gyro_form.addRow(self.invert_y_checkbox)
        mouse_gyro_form.addRow(self.tr("Pitch limit"), self.pitch_limit_spinbox)
        self.save_error_label = QLabel("", self)
        self.restore_button = QPushButton(self.tr("Restore defaults"), self)
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            self,
        )

        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addWidget(self.inverted_checkbox)
        layout.addWidget(self.capture_button)
        layout.addWidget(self.capture_label)
        layout.addWidget(self.mouse_gyro_group)
        layout.addWidget(self.save_error_label)
        layout.addWidget(self.restore_button)
        layout.addWidget(self.button_box)
        self.setMinimumSize(760, 520)
        self.resize(840, 640)

        QWidget.setTabOrder(self.table, self.inverted_checkbox)
        QWidget.setTabOrder(self.inverted_checkbox, self.capture_button)
        QWidget.setTabOrder(self.capture_button, self.mouse_gyro_enabled_checkbox)
        QWidget.setTabOrder(
            self.mouse_gyro_enabled_checkbox,
            self.horizontal_sensitivity_spinbox,
        )
        QWidget.setTabOrder(
            self.horizontal_sensitivity_spinbox,
            self.vertical_sensitivity_spinbox,
        )
        QWidget.setTabOrder(self.vertical_sensitivity_spinbox, self.invert_x_checkbox)
        QWidget.setTabOrder(self.invert_x_checkbox, self.invert_y_checkbox)
        QWidget.setTabOrder(self.invert_y_checkbox, self.pitch_limit_spinbox)
        QWidget.setTabOrder(self.pitch_limit_spinbox, self.restore_button)

        self.capture_button.clicked.connect(self.begin_capture)
        self.restore_button.clicked.connect(self.restore_default_profile)
        self.button_box.accepted.connect(self.request_accept)
        self.button_box.rejected.connect(self.request_reject)
        selection_model = self.table.selectionModel()
        if selection_model is not None:
            selection_model.currentRowChanged.connect(self._sync_inverted_checkbox)
        self.inverted_checkbox.toggled.connect(self.set_inverted)
        self.mouse_gyro_enabled_checkbox.toggled.connect(
            lambda enabled: editor.update_mouse(gyro_enabled=enabled)
        )
        self.horizontal_sensitivity_spinbox.valueChanged.connect(
            lambda value: editor.update_mouse(horizontal_sensitivity=value)
        )
        self.vertical_sensitivity_spinbox.valueChanged.connect(
            lambda value: editor.update_mouse(vertical_sensitivity=value)
        )
        self.invert_x_checkbox.toggled.connect(
            lambda enabled: editor.update_mouse(invert_x=enabled)
        )
        self.invert_y_checkbox.toggled.connect(
            lambda enabled: editor.update_mouse(invert_y=enabled)
        )
        self.pitch_limit_spinbox.valueChanged.connect(
            lambda value: editor.update_mouse(pitch_limit_degrees=value)
        )

    @property
    def conflict_confirmation(self) -> QMessageBox | None:
        """Return the currently visible binding-conflict confirmation, if any."""
        return self._conflict_confirmation

    @property
    def mapping_model(self) -> MappingTableModel:
        """Return the binding table model for row-oriented dialog actions."""
        return self._mapping_model

    def begin_capture_row(self, row: int) -> None:
        """Arm one explicit binding row for the next supported input event."""
        self._capture_row = row
        self._mapping_model.begin_capture(row)
        self.table.selectRow(row)
        self.capture_label.setText(self.tr("Press the next key or mouse button"))

    def _activate_row_action(self, row: int) -> None:
        if self._capture_row == row:
            self.cancel_capture()
            return
        self.begin_capture_row(row)

    def cancel_capture(self) -> None:
        """Stop the active row remap without changing or closing the draft."""
        self._capture_row = None
        self._mapping_model.cancel_capture()
        self.capture_label.setText(self.tr("Input capture cancelled"))

    def begin_capture(self) -> None:
        """Arm the selected table row for exactly one supported input event."""
        selected = self.table.currentIndex()
        if not selected.isValid():
            self.capture_label.setText(self.tr("Select a target"))
            return
        self.begin_capture_row(selected.row())

    def restore_default_profile(self) -> None:
        """Restore the built-in profile through the application-owned editor."""
        self._mapping_model.restore_default_profile()
        self._capture_row = None
        self._mapping_model.cancel_capture()
        self.capture_label.setText(self.tr("Defaults restored"))

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
            self.capture_label.setText(self.tr("Input cannot be assigned"))
            return False
        self.table.selectRow(row)
        self.capture_label.setText(self.tr("Input: {source}").format(source=source))
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
            self.tr("Key mapping conflicts"),
            self.tr("Mappings conflict with duplicates or local actions."),
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
        self._mapping_model.cancel_capture()
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
            if event.key() == Qt.Key.Key_Escape and self._capture_row is not None:
                self.cancel_capture()
                event.accept()
                return True
            if event.key() == Qt.Key.Key_F4:
                self._capture_row = None
                self.capture_label.setText(self.tr("Input capture released with F4"))
                _invoke(self._on_release_capture)
                event.accept()
                return True
            return self._capture_source(key_source_for_event(event))
        if isinstance(event, QMouseEvent) and event.type() is QEvent.Type.MouseButtonPress:
            if watched is self.table.viewport():
                index = self.table.indexAt(event.position().toPoint())
                if index.column() == 4 and index.row() == self._capture_row:
                    return False
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
            self.inverted_checkbox.setEnabled(self._mapping_model.is_invertible_at(current.row()))
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
            self.save_error_label.setText(self.tr("Could not save settings"))
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


def _sensitivity_spinbox(parent: QWidget, value: float) -> QDoubleSpinBox:
    spinbox = QDoubleSpinBox(parent)
    spinbox.setRange(0.1, 10.0)
    spinbox.setDecimals(2)
    spinbox.setSingleStep(0.1)
    spinbox.setValue(value)
    return spinbox
