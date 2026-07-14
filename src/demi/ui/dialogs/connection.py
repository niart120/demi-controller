"""Qt connection settings dialog and adapter presentation model."""

from collections.abc import Callable
from typing import Any, override

from PySide6.QtCore import QAbstractListModel, QModelIndex, QObject, QPersistentModelIndex, Qt
from PySide6.QtWidgets import QComboBox, QDialog, QLabel, QPushButton, QVBoxLayout, QWidget

from demi.application.presentation import AdapterOption

_ROOT_INDEX = QModelIndex()

type RescanAction = Callable[[], object]


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


class ConnectionDialog(QDialog):
    """Request asynchronous adapter discovery through standard Qt controls."""

    def __init__(
        self,
        *,
        on_rescan: RescanAction,
        parent: QWidget | None = None,
    ) -> None:
        """Create a connection dialog that does not own runtime discovery.

        Args:
            on_rescan: Posts an adapter-discovery request at the application
                boundary without returning a result synchronously.
            parent: Optional Qt parent for dialog ownership.
        """
        super().__init__(parent)
        self.setWindowTitle("接続設定")
        self._on_rescan = on_rescan
        self._adapter_model = AdapterListModel(self)

        self.adapter_combo = QComboBox(self)
        self.adapter_combo.setModel(self._adapter_model)
        self.rescan_button = QPushButton("再検索", self)
        self.connect_button = QPushButton("保存して接続", self)
        self.pairing_button = QPushButton("新規ペアリング", self)
        self.discovery_label = QLabel("USBアダプターを検索してください", self)
        self.connect_button.setEnabled(False)
        self.pairing_button.setEnabled(False)

        layout = QVBoxLayout(self)
        layout.addWidget(self.adapter_combo)
        layout.addWidget(self.rescan_button)
        layout.addWidget(self.connect_button)
        layout.addWidget(self.pairing_button)
        layout.addWidget(self.discovery_label)

        self.rescan_button.clicked.connect(self.request_rescan)

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

    def set_adapters(self, adapters: tuple[AdapterOption, ...]) -> None:
        """Present one asynchronously delivered discovery result.

        Args:
            adapters: Latest safe adapter identities from application state.
        """
        self._adapter_model.set_adapters(adapters)
        self.rescan_button.setEnabled(True)
        has_adapters = bool(adapters)
        self.adapter_combo.setEnabled(has_adapters)
        self.connect_button.setEnabled(False)
        self.pairing_button.setEnabled(False)
        if not has_adapters:
            self.discovery_label.setText(
                "利用可能なUSBアダプターがありません。接続機器を確認して再検索してください"
            )
            return
        self.discovery_label.setText(f"{len(adapters)}件のUSBアダプターを検出しました")
