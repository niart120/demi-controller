"""Qt connection settings dialog and adapter presentation model."""

from collections.abc import Callable
from typing import Any, override

from PySide6.QtCore import QAbstractListModel, QModelIndex, QObject, QPersistentModelIndex, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from demi.application.presentation import AdapterOption
from demi.application.settings_editor import SettingsEditor
from demi.domain.errors import DomainValueError

_ROOT_INDEX = QModelIndex()

type RescanAction = Callable[[], object]
type PairingAction = Callable[[], bool]
type PairingCancellation = Callable[[], object]


class AdapterListModel(QAbstractListModel):
    """Expose discovered adapter identities to Qt item views."""

    def __init__(self, parent: QObject | None = None) -> None:
        """Create an empty model that owns no discovery operation.

        Args:
            parent: Optional Qt parent for model ownership.
        """
        super().__init__(parent)
        self._adapters: tuple[AdapterOption, ...] = ()

    @override
    def rowCount(
        self,
        parent: QModelIndex | QPersistentModelIndex = _ROOT_INDEX,
    ) -> int:
        """Return the number of top-level discovered adapters."""
        return 0 if parent.isValid() else len(self._adapters)

    @override
    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        """Return a display label or stable adapter ID for one row."""
        if not index.isValid() or not 0 <= index.row() < len(self._adapters):
            return None
        adapter = self._adapters[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return adapter.label
        if role == Qt.ItemDataRole.UserRole:
            return adapter.id
        return None

    def set_adapters(self, adapters: tuple[AdapterOption, ...]) -> None:
        """Replace the discovery result without performing I/O.

        Args:
            adapters: Safe adapter identities returned by application state.
        """
        self.beginResetModel()
        self._adapters = adapters
        self.endResetModel()

    def index_of(self, adapter_id: str) -> int:
        """Return the row for one exact adapter ID, or ``-1`` if absent."""
        for index, adapter in enumerate(self._adapters):
            if adapter.id == adapter_id:
                return index
        return -1


class ConnectionDialog(QDialog):
    """Request asynchronous adapter discovery through standard Qt controls."""

    def __init__(
        self,
        editor: SettingsEditor,
        *,
        on_rescan: RescanAction,
        on_request_pairing: PairingAction | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Create a connection dialog that does not own runtime discovery.

        Args:
            editor: Application-owned connection settings draft editor.
            on_rescan: Posts an adapter-discovery request at the application
                boundary without returning a result synchronously.
            on_request_pairing: Requests replacement by a pairing confirmation
                dialog after an explicit adapter selection.
            parent: Optional Qt parent for dialog ownership.
        """
        super().__init__(parent)
        self.setWindowTitle("接続設定")
        self._editor = editor
        self._on_rescan = on_rescan
        self._on_request_pairing = on_request_pairing
        self._adapter_model = AdapterListModel(self)
        self._updating_adapters = False

        self.adapter_combo = QComboBox(self)
        self.adapter_combo.setModel(self._adapter_model)
        self.rescan_button = QPushButton("再検索", self)
        self.connect_button = QPushButton("保存して接続", self)
        self.pairing_button = QPushButton("新規ペアリング", self)
        self.discovery_label = QLabel("USBアダプターを検索してください", self)
        self.bond_slot_edit = QLineEdit(editor.draft.connection.bond_slot, self)
        self.timeout_edit = QLineEdit(str(editor.draft.connection.timeout_seconds), self)
        self.connection_error_label = QLabel("", self)
        self.connect_button.setEnabled(False)
        self.pairing_button.setEnabled(False)

        connection_form = QFormLayout()
        connection_form.addRow("ボンドスロット", self.bond_slot_edit)
        connection_form.addRow("接続タイムアウト (秒)", self.timeout_edit)

        layout = QVBoxLayout(self)
        layout.addWidget(self.adapter_combo)
        layout.addLayout(connection_form)
        layout.addWidget(self.rescan_button)
        layout.addWidget(self.connect_button)
        layout.addWidget(self.pairing_button)
        layout.addWidget(self.discovery_label)

        self.rescan_button.clicked.connect(self.request_rescan)
        self.adapter_combo.currentIndexChanged.connect(self.select_adapter)
        self.pairing_button.clicked.connect(self.request_pairing)

    @property
    def adapter_model(self) -> AdapterListModel:
        """Return the Qt model that presents the latest discovery result."""
        return self._adapter_model

    def request_rescan(self) -> None:
        """Post one discovery action without waiting for its runtime result."""
        if not self.rescan_button.isEnabled():
            return
        self.rescan_button.setEnabled(False)
        self.discovery_label.setText("USBアダプターを検索中です")
        self._on_rescan()

    def request_pairing(self) -> None:
        """Request the application-owned pairing confirmation dialog."""
        on_request_pairing = self._on_request_pairing
        if self.pairing_button.isEnabled() and on_request_pairing is not None:
            on_request_pairing()

    def apply_connection_fields(self) -> bool:
        """Validate editable connection fields without saving the draft.

        Returns:
            Whether both controls updated the application-owned draft.
        """
        try:
            self._editor.update_connection(
                bond_slot=self.bond_slot_edit.text(),
                timeout_seconds=float(self.timeout_edit.text()),
            )
        except (DomainValueError, ValueError):
            self.connection_error_label.setText("接続設定の値が正しくありません")
            return False
        self.connection_error_label.clear()
        return True

    def set_adapters(self, adapters: tuple[AdapterOption, ...]) -> None:
        """Present one asynchronously delivered discovery result.

        Args:
            adapters: Latest safe adapter identities from application state.
        """
        self._updating_adapters = True
        try:
            self._adapter_model.set_adapters(adapters)
            saved_adapter_index = self._adapter_model.index_of(
                self._editor.draft.connection.adapter_id
            )
            self.adapter_combo.setCurrentIndex(saved_adapter_index)
        finally:
            self._updating_adapters = False
        self.rescan_button.setEnabled(True)
        has_adapters = bool(adapters)
        self.adapter_combo.setEnabled(has_adapters)
        if not has_adapters:
            self._set_connection_actions_enabled(False)
            self.discovery_label.setText(
                "利用可能なUSBアダプターがありません。接続機器を確認して再検索してください"
            )
            return
        if saved_adapter_index < 0:
            self._set_connection_actions_enabled(False)
            if self._editor.draft.connection.adapter_id:
                self.discovery_label.setText(
                    "保存済みのUSBアダプターが見つかりません。アダプターを選択してください"
                )
                return
            self.discovery_label.setText(f"{len(adapters)}件のUSBアダプターを検出しました")
            return
        self._set_connection_actions_enabled(True)
        self.discovery_label.setText(f"{len(adapters)}件のUSBアダプターを検出しました")

    def select_adapter(self, index: int) -> None:
        """Store one explicit adapter selection in the application-owned draft.

        Args:
            index: Selected `QComboBox` row, or a negative value when none is
                selected.
        """
        if self._updating_adapters:
            return
        adapter_id = self.adapter_combo.itemData(index)
        if not isinstance(adapter_id, str):
            self._set_connection_actions_enabled(False)
            return
        self._editor.update_connection(adapter_id=adapter_id)
        self._set_connection_actions_enabled(True)
        self.discovery_label.setText(f"選択中のUSBアダプター: {self.adapter_combo.itemText(index)}")

    def _set_connection_actions_enabled(self, enabled: bool) -> None:
        self.connect_button.setEnabled(enabled)
        self.pairing_button.setEnabled(enabled)


class PairingConfirmationDialog(QDialog):
    """Require explicit confirmation before a pairing command is requested."""

    def __init__(
        self,
        *,
        on_confirm: PairingAction,
        on_cancel: PairingCancellation,
        busy: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        """Create one pairing confirmation without owning connection state.

        Args:
            on_confirm: Starts pairing after a user explicitly accepts.
            on_cancel: Returns from confirmation without posting a pairing command.
            busy: Whether an existing pairing transition prevents interaction.
            parent: Optional Qt parent for dialog ownership.
        """
        super().__init__(parent)
        self.setWindowTitle("新規ペアリングの確認")
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel
        self._busy = False
        self.message_label = QLabel(self)
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )

        layout = QVBoxLayout(self)
        layout.addWidget(self.message_label)
        layout.addWidget(self.button_box)

        self.button_box.accepted.connect(self.confirm)
        self.button_box.rejected.connect(self.reject)
        self.set_busy(busy)

    def set_busy(self, busy: bool) -> None:
        """Enable or disable pairing confirmation controls.

        Args:
            busy: Whether a current pairing transition owns the dialog state.
        """
        self._busy = busy
        self.message_label.setText(
            "ペアリング処理中です" if busy else "新規ペアリングを開始しますか?"
        )
        for button in (
            self.button_box.button(QDialogButtonBox.StandardButton.Ok),
            self.button_box.button(QDialogButtonBox.StandardButton.Cancel),
        ):
            if button is not None:
                button.setEnabled(not busy)

    def confirm(self) -> None:
        """Start pairing only after a non-busy confirmation."""
        if not self._busy and self._on_confirm():
            self.accept()

    def reject(self) -> None:
        """Return to editable connection settings without starting pairing."""
        if self._busy:
            return
        self._on_cancel()
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt override name.
        """Treat a window close as cancellation unless pairing is busy."""
        if self._busy:
            event.ignore()
            return
        self.reject()
        event.accept()
