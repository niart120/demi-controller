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
from PySide6.QtGui import QAction, QHideEvent, QKeyEvent, QKeySequence, QMouseEvent, QShowEvent
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
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from demi.application.settings_editor import (
    RESERVED_BINDING_SOURCES,
    BindingConflict,
    SettingsEditor,
)
from demi.domain.errors import DomainValueError
from demi.domain.mapping import Binding, BindingTarget, is_button_target
from demi.input.qt_adapter import key_source_for_event, mouse_source_for_event

_ROOT_INDEX = QModelIndex()

type CaptureTransition = Callable[[], object]
type SettingsAction = Callable[[], bool]
type RowAction = Callable[[int], object]

_BINDING_TARGET_GROUPS = (
    ("Buttons", tuple(target for target in BindingTarget if target.value.startswith("BUTTON:"))),
    (
        "Left stick",
        tuple(target for target in BindingTarget if target.value.startswith("LEFT_STICK:")),
    ),
    (
        "Right stick",
        tuple(target for target in BindingTarget if target.value.startswith("RIGHT_STICK:")),
    ),
    (
        "Diagnostics",
        tuple(
            target
            for target in BindingTarget
            if target.value.startswith(("GYRO:", "ACCEL:"))
        ),
    ),
)


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

    _HEADERS = ("Target", "Input", "Inverted", "Conflict", "Action", "Remove")

    def __init__(self, editor: SettingsEditor, parent: QObject | None = None) -> None:
        """Create a table model backed by one application-owned draft.

        Args:
            editor: Immutable settings draft editor used for all changes.
            parent: Optional Qt parent for model ownership.
        """
        super().__init__(parent)
        self._editor = editor
        self._capture_row: int | None = None
        self._row_status: dict[int, str] = {}

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
        if not index.isValid():
            return None
        binding = self._bindings()[index.row()]
        if index.column() == 1 and role in {
            Qt.ItemDataRole.UserRole,
            Qt.ItemDataRole.ToolTipRole,
            Qt.ItemDataRole.AccessibleDescriptionRole,
        }:
            return binding.source
        if index.column() == 2:
            if role == Qt.ItemDataRole.CheckStateRole and is_button_target(binding.target):
                return (
                    Qt.CheckState.Checked
                    if binding.inverted
                    else Qt.CheckState.Unchecked
                )
            if role == Qt.ItemDataRole.DisplayRole:
                return None
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        input_text = (
            self.tr("Press a key or mouse button")
            if index.row() == self._capture_row
            else _friendly_source(binding.source)
        )
        action_text = self.tr("Cancel") if index.row() == self._capture_row else self.tr("Remap")
        values = (
            binding.target.value,
            input_text,
            None,
            self._row_status.get(index.row()) or self._conflict_text(index.row()),
            action_text,
            self.tr("Remove"),
        )
        return values[index.column()]

    @override
    def flags(self, index: QModelIndex | QPersistentModelIndex) -> Qt.ItemFlag:
        """Return checkbox editing support only for invertible binding rows."""
        flags = super().flags(index)
        if (
            index.isValid()
            and index.column() == 2
            and self.is_invertible_at(index.row())
        ):
            return flags | Qt.ItemFlag.ItemIsUserCheckable
        return flags

    @override
    def setData(
        self,
        index: QModelIndex | QPersistentModelIndex,
        value: Any,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        """Update an invertible row from the standard table checkbox."""
        if (
            not index.isValid()
            or index.column() != 2
            or role != Qt.ItemDataRole.CheckStateRole
            or not self.is_invertible_at(index.row())
        ):
            return False
        checked = value == Qt.CheckState.Checked
        self._editor.update_binding(index.row(), inverted=checked)
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
        return True

    @property
    def capture_row(self) -> int | None:
        """Return the row currently waiting for an input source."""
        return self._capture_row

    def begin_capture(self, row: int) -> None:
        """Mark one binding row as waiting for its replacement source."""
        if not 0 <= row < self.rowCount():
            raise DomainValueError
        if self._capture_row is not None:
            self._row_status.pop(self._capture_row, None)
        self._capture_row = row
        self._row_status.pop(row, None)
        self._reset_from_editor()

    def cancel_capture(self) -> None:
        """Clear the waiting row without changing the settings draft."""
        if self._capture_row is None:
            return
        self._row_status.pop(self._capture_row, None)
        self._capture_row = None
        self._reset_from_editor()

    def set_row_status(self, row: int, message: str) -> None:
        """Show transient feedback in the affected row's status column."""
        if not 0 <= row < self.rowCount():
            raise DomainValueError
        self._row_status[row] = message
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
        self._row_status.pop(row, None)
        self._reset_from_editor()

    def replace_source(self, row: int, source: str) -> None:
        """Assign a source and unassign every conflicting row atomically."""
        self._editor.replace_binding_source(row, source)
        self._capture_row = None
        self._row_status.pop(row, None)
        self._reset_from_editor()

    def conflicting_rows(self, row: int, source: str) -> tuple[int, ...]:
        """Return other binding rows that already use a source."""
        return tuple(
            candidate
            for candidate, binding in enumerate(self._bindings())
            if candidate != row and binding.source == source
        )

    def target_at(self, row: int) -> str:
        """Return the canonical target for one binding row."""
        return self._bindings()[row].target.value

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
        self._row_status.clear()
        self._reset_from_editor()

    def add_binding(self, target: BindingTarget) -> None:
        """Append one unassigned row for a selected binding target."""
        if not isinstance(target, BindingTarget):
            raise DomainValueError
        row = self.rowCount()
        self.beginInsertRows(_ROOT_INDEX, row, row)
        self._editor.add_binding(target)
        self.endInsertRows()

    def remove_binding(self, row: int) -> None:
        """Remove one existing binding row."""
        if not 0 <= row < self.rowCount():
            raise DomainValueError
        self.beginRemoveRows(_ROOT_INDEX, row, row)
        self._editor.remove_binding(row)
        self._capture_row = None
        self._row_status.clear()
        self.endRemoveRows()

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
        self._cancel_requested = False
        self._input_filter_application: QApplication | None = None
        self._conflict_confirmation: QMessageBox | None = None
        self._binding_replacement_confirmation: QMessageBox | None = None
        self._pending_binding_replacement: tuple[int, str] | None = None

        self.table = QTableView(self)
        self.table.setModel(self._mapping_model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        self.assign_escape_action = QAction(self.tr("Assign Escape"), self.table)
        self.assign_escape_action.setShortcut(QKeySequence("Ctrl+Shift+E"))
        self.assign_escape_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.table.addAction(self.assign_escape_action)
        self._mapping_action_delegate = MappingActionDelegate(
            on_activated=self._activate_row_action,
            parent=self.table,
        )
        self._remove_binding_delegate = MappingActionDelegate(
            on_activated=self._remove_binding_row,
            parent=self.table,
        )
        self.table.setItemDelegateForColumn(4, self._mapping_action_delegate)
        self.table.setItemDelegateForColumn(5, self._remove_binding_delegate)
        table_header = self.table.horizontalHeader()
        for column in range(3):
            table_header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        table_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        table_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        table_header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.add_binding_menu = QMenu(self)
        self.add_binding_group_menus: dict[str, QMenu] = {}
        translated_group_labels = {
            "Buttons": self.tr("Buttons"),
            "Left stick": self.tr("Left stick"),
            "Right stick": self.tr("Right stick"),
            "Diagnostics": self.tr("Diagnostics"),
        }
        for group_label, targets in _BINDING_TARGET_GROUPS:
            group_menu = QMenu(translated_group_labels[group_label], self.add_binding_menu)
            self.add_binding_menu.addMenu(group_menu)
            self.add_binding_group_menus[group_label] = group_menu
            for target in targets:
                action = group_menu.addAction(target.value)
                action.setData(target)
                action.triggered.connect(
                    lambda _checked=False, selected_target=target: self.add_binding(
                        selected_target
                    )
                )
        self.add_binding_button = QToolButton(self)
        self.add_binding_button.setText(self.tr("Add binding"))
        self.add_binding_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.add_binding_button.setMenu(self.add_binding_menu)
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

        self.bindings_page = QWidget(self)
        bindings_layout = QVBoxLayout(self.bindings_page)
        binding_actions = QHBoxLayout()
        binding_actions.addWidget(self.add_binding_button)
        binding_actions.addStretch()
        binding_actions.addWidget(self.restore_button)
        bindings_layout.addLayout(binding_actions)
        bindings_layout.addWidget(self.table)
        self.mouse_page = QWidget(self)
        mouse_layout = QVBoxLayout(self.mouse_page)
        mouse_layout.addWidget(self.mouse_gyro_group)
        mouse_layout.addStretch()
        self.tabs = QTabWidget(self)
        self.tabs.addTab(self.bindings_page, self.tr("Bindings"))
        self.tabs.addTab(self.mouse_page, self.tr("Mouse gyro"))

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        layout.addWidget(self.save_error_label)
        layout.addWidget(self.button_box)
        self.setMinimumSize(760, 520)
        self.resize(840, 640)

        QWidget.setTabOrder(self.add_binding_button, self.table)
        QWidget.setTabOrder(self.table, self.restore_button)
        QWidget.setTabOrder(self.restore_button, self.mouse_gyro_enabled_checkbox)
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
        QWidget.setTabOrder(self.pitch_limit_spinbox, self.button_box)

        self.assign_escape_action.triggered.connect(self.assign_escape)
        self.tabs.currentChanged.connect(self._handle_tab_changed)
        self.restore_button.clicked.connect(self.restore_default_profile)
        self.button_box.accepted.connect(self.request_accept)
        self.button_box.rejected.connect(self.request_reject)
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
    def binding_replacement_confirmation(self) -> QMessageBox | None:
        """Return the visible per-source replacement confirmation, if any."""
        return self._binding_replacement_confirmation

    @property
    def mapping_model(self) -> MappingTableModel:
        """Return the binding table model for row-oriented dialog actions."""
        return self._mapping_model

    def take_pages(self) -> tuple[QWidget, QWidget]:
        """Detach the binding and mouse pages for a flat parent tab widget."""
        while self.tabs.count():
            self.tabs.removeTab(0)
        return self.bindings_page, self.mouse_page

    def activate_input_handling(self) -> None:
        """Start input handling for direct or embedded dialog use."""
        if self._input_filter_application is not None:
            return
        _invoke(self._on_dialog_opened)
        self._install_input_filter()

    def deactivate_input_handling(self) -> None:
        """Stop remapping and input handling when the owner is hidden."""
        self._capture_row = None
        self._mapping_model.cancel_capture()
        self._remove_input_filter()

    def begin_capture_row(self, row: int) -> None:
        """Arm one explicit binding row for the next supported input event."""
        self._capture_row = row
        self._mapping_model.begin_capture(row)
        self.table.selectRow(row)

    def _activate_row_action(self, row: int) -> None:
        if self._capture_row == row:
            self.cancel_capture()
            return
        self.begin_capture_row(row)

    def cancel_capture(self) -> None:
        """Stop the active row remap without changing or closing the draft."""
        self._capture_row = None
        self._mapping_model.cancel_capture()

    def _handle_tab_changed(self, index: int) -> None:
        if index != 0 and self._capture_row is not None:
            self.cancel_capture()

    def assign_escape(self) -> None:
        """Assign Escape to the selected row through an explicit action."""
        selected = self.table.currentIndex()
        if not selected.isValid():
            return
        self.cancel_capture()
        self.set_source(selected.row(), "KEY:ESCAPE")

    def restore_default_profile(self) -> None:
        """Restore the built-in profile through the application-owned editor."""
        self._mapping_model.restore_default_profile()
        self._capture_row = None
        self._mapping_model.cancel_capture()

    def add_binding(self, target: BindingTarget) -> None:
        """Append and select an unassigned row for the chosen target."""
        self.cancel_capture()
        try:
            self._mapping_model.add_binding(target)
        except DomainValueError:
            return
        self.table.selectRow(self._mapping_model.rowCount() - 1)

    def _remove_binding_row(self, row: int) -> None:
        """Remove the activated binding row while preserving surrounding order."""
        self.cancel_capture()
        try:
            self._mapping_model.remove_binding(row)
        except DomainValueError:
            return
        remaining = self._mapping_model.rowCount()
        if remaining:
            self.table.selectRow(min(row, remaining - 1))

    def set_source(self, row: int, source: str) -> bool:
        """Update one mapping source while keeping invalid input visible.

        Args:
            row: Selected binding row in the active profile.
            source: Canonical source candidate received by the dialog.

        Returns:
            Whether the draft accepted the candidate source.
        """
        conflicting_rows = self._mapping_model.conflicting_rows(row, source)
        if conflicting_rows:
            self._open_binding_replacement(row, source, conflicting_rows)
            return False
        try:
            self._mapping_model.update_source(row, source)
        except DomainValueError:
            self._mapping_model.set_row_status(row, self.tr("Input cannot be assigned"))
            return False
        self.table.selectRow(row)
        return True

    def _open_binding_replacement(
        self,
        row: int,
        source: str,
        conflicting_rows: tuple[int, ...],
    ) -> None:
        if self._binding_replacement_confirmation is not None:
            return
        existing_targets = ", ".join(
            self._mapping_model.target_at(conflicting_row) for conflicting_row in conflicting_rows
        )
        confirmation = QMessageBox(
            QMessageBox.Icon.Warning,
            self.tr("Replace existing binding?"),
            self.tr("The input {source} is already assigned.").format(source=source),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            self,
        )
        confirmation.setInformativeText(
            self.tr("{source}: replace {existing} with {target}").format(
                source=source,
                existing=existing_targets,
                target=self._mapping_model.target_at(row),
            )
        )
        confirmation.setDefaultButton(QMessageBox.StandardButton.Cancel)
        self._pending_binding_replacement = (row, source)
        confirmation.buttonClicked.connect(self._handle_binding_replacement)
        confirmation.finished.connect(self._clear_binding_replacement)
        self._binding_replacement_confirmation = confirmation
        confirmation.open()

    def _handle_binding_replacement(self, button: QAbstractButton) -> None:
        confirmation = self._binding_replacement_confirmation
        pending = self._pending_binding_replacement
        if (
            confirmation is None
            or pending is None
            or confirmation.standardButton(button) != QMessageBox.StandardButton.Yes
        ):
            return
        row, source = pending
        self._mapping_model.replace_source(row, source)
        self._capture_row = None
        self.table.selectRow(row)

    def _clear_binding_replacement(self, _result: int) -> None:
        self._binding_replacement_confirmation = None
        self._pending_binding_replacement = None

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
        self.activate_input_handling()
        super().showEvent(event)

    def hideEvent(self, event: QHideEvent) -> None:  # noqa: N802 - Qt override name.
        """Stop listening for dialog input once this dialog is hidden."""
        self.deactivate_input_handling()
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
            current = self.table.currentIndex()
            if (
                watched is self.table
                and current.column() == 4
                and event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space}
            ):
                self._activate_row_action(current.row())
                event.accept()
                return True
            if (
                watched is self.table
                and current.column() == 2
                and event.key() == Qt.Key.Key_Space
            ):
                state = self._mapping_model.data(
                    current,
                    Qt.ItemDataRole.CheckStateRole,
                )
                if state is not None:
                    self._mapping_model.setData(
                        current,
                        (
                            Qt.CheckState.Unchecked
                            if state == Qt.CheckState.Checked
                            else Qt.CheckState.Checked
                        ),
                        Qt.ItemDataRole.CheckStateRole,
                    )
                    event.accept()
                    return True
            if (
                watched is self.table
                and current.column() == 5
                and event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space}
            ):
                self._remove_binding_row(current.row())
                event.accept()
                return True
            if event.key() == Qt.Key.Key_Escape and self._capture_row is not None:
                self.cancel_capture()
                event.accept()
                return True
            if event.key() == Qt.Key.Key_F4 and "KEY:F4" in RESERVED_BINDING_SOURCES:
                if self._capture_row is not None:
                    self._mapping_model.set_row_status(
                        self._capture_row,
                        self.tr("F4 is reserved for mouse capture release"),
                    )
                else:
                    _invoke(self._on_release_capture)
                event.accept()
                return True
            return self._capture_source(key_source_for_event(event))
        if isinstance(event, QMouseEvent) and event.type() is QEvent.Type.MouseButtonPress:
            if watched is self.table.viewport():
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
        return (
            watched is self
            or watched is self.table
            or (
                isinstance(watched, QWidget)
                and (self.isAncestorOf(watched) or self.table.isAncestorOf(watched))
            )
        )


def _invoke(callback: CaptureTransition | None) -> None:
    if callback is not None:
        callback()


def _friendly_source(source: str) -> str:
    translate = QCoreApplication.translate
    if source == "KEY:UNASSIGNED":
        return translate("MappingTableModel", "Unassigned")
    if source.startswith("KEY:"):
        return " + ".join(part.replace("_", " ").title() for part in source[4:].split("+"))
    mouse_name = {
        "MOUSE:LEFT": "Left mouse",
        "MOUSE:RIGHT": "Right mouse",
        "MOUSE:MIDDLE": "Middle mouse",
        "MOUSE:BUTTON_4": "Back mouse",
        "MOUSE:BUTTON_5": "Forward mouse",
    }.get(source, source.removeprefix("MOUSE:").replace("_", " ").title())
    return translate("MappingTableModel", mouse_name)


def _sensitivity_spinbox(parent: QWidget, value: float) -> QDoubleSpinBox:
    spinbox = QDoubleSpinBox(parent)
    spinbox.setRange(0.1, 10.0)
    spinbox.setDecimals(2)
    spinbox.setSingleStep(0.1)
    spinbox.setValue(value)
    return spinbox
