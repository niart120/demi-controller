"""Model/view presentation for editable controller input bindings."""

from typing import Any, override

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    Qt,
)

from demi.application.settings_editor import BindingConflict, SettingsEditor
from demi.domain.mapping import Binding

_ROOT_INDEX = QModelIndex()


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

    def restore_default_profile(self) -> None:
        """Restore the standard profile through the application-owned editor."""
        self._editor.reset_profile()
        self._reset_from_editor()

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
