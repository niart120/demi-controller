"""Qt connection settings dialog and adapter presentation model."""

from collections.abc import Callable
from typing import Any, override

from PySide6.QtCore import QAbstractListModel, QModelIndex, QObject, QPersistentModelIndex, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QAbstractButton,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from demi.application.presentation import AdapterOption
from demi.application.settings_editor import SettingsEditor
from demi.domain.errors import DomainValueError
from demi.domain.settings import DiagnosticLevel

_ROOT_INDEX = QModelIndex()

type RescanAction = Callable[[], object]
type PairingAction = Callable[[], bool]
type PairingCancellation = Callable[[], object]
type SettingsAction = Callable[[], bool]


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
        on_save: SettingsAction | None = None,
        on_delete_profile: SettingsAction | None = None,
        on_cancel: SettingsAction | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Create a connection dialog that does not own runtime discovery.

        Args:
            editor: Application-owned connection settings draft editor.
            on_rescan: Posts an adapter-discovery request at the application
                boundary without returning a result synchronously.
            on_request_pairing: Requests replacement by a pairing confirmation
                dialog after an explicit adapter selection.
            on_save: Saves the edited draft without requesting a connection.
            on_delete_profile: Deletes the fixed controller connection profile.
            on_cancel: Discards the active settings draft before the dialog closes.
            parent: Optional Qt parent for dialog ownership.
        """
        super().__init__(parent)
        self.setWindowTitle(self.tr("Connection settings"))
        self._editor = editor
        self._on_rescan = on_rescan
        self._on_request_pairing = on_request_pairing
        self._on_save = on_save
        self._on_delete_profile = on_delete_profile
        self._on_cancel = on_cancel
        self._adapter_model = AdapterListModel(self)
        self._updating_adapters = False
        self._cancel_requested = False
        self._profile_exists = False
        self._profile_delete_confirmation: QMessageBox | None = None

        self.adapter_combo = QComboBox(self)
        self.adapter_combo.setModel(self._adapter_model)
        self.rescan_button = QPushButton(self.tr("Rescan"), self)
        self.pairing_button = QPushButton(self.tr("Pair new controller"), self)
        self.delete_profile_button = QPushButton(self.tr("Delete profile"), self)
        self.discovery_label = QLabel(self.tr("Search for USB adapters"), self)
        self.controller_type_label = QLabel("Pro Controller", self)
        self.profile_status_label = QLabel(self.tr("Not saved"), self)
        self.reconnect_on_start_checkbox = QCheckBox(self.tr("Enabled"), self)
        self.reconnect_on_start_checkbox.setChecked(editor.draft.connection.reconnect_on_start)
        self.diagnostic_level_combo = QComboBox(self)
        for diagnostic_level in DiagnosticLevel:
            self.diagnostic_level_combo.addItem(diagnostic_level.value, diagnostic_level)
        self.diagnostic_level_combo.setCurrentText(editor.draft.connection.diagnostic_level.value)
        self.connection_error_label = QLabel("", self)
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        save_button = self.button_box.button(QDialogButtonBox.StandardButton.Save)
        if save_button is None:
            raise RuntimeError
        self.save_button = save_button
        self.pairing_button.setEnabled(False)
        self.delete_profile_button.setEnabled(False)

        self.profile_group = QGroupBox(self.tr("Controller profile"), self)
        profile_form = QFormLayout(self.profile_group)
        profile_form.addRow(self.tr("Controller type"), self.controller_type_label)
        profile_form.addRow(self.tr("Status"), self.profile_status_label)
        profile_actions = QHBoxLayout()
        profile_actions.addWidget(self.pairing_button)
        profile_actions.addWidget(self.delete_profile_button)
        profile_form.addRow(profile_actions)

        self.global_settings_group = QGroupBox(self.tr("Global settings"), self)
        global_settings_form = QFormLayout(self.global_settings_group)
        adapter_actions = QHBoxLayout()
        adapter_actions.addWidget(self.adapter_combo, 1)
        adapter_actions.addWidget(self.rescan_button)
        global_settings_form.addRow(self.tr("USB adapter"), adapter_actions)
        global_settings_form.addRow(
            self.tr("Reconnect on startup"), self.reconnect_on_start_checkbox
        )
        global_settings_form.addRow(self.tr("Diagnostic log level"), self.diagnostic_level_combo)
        global_settings_form.addRow(self.discovery_label)

        layout = QVBoxLayout(self)
        layout.addWidget(self.global_settings_group)
        layout.addWidget(self.profile_group)
        layout.addWidget(self.connection_error_label)
        layout.addWidget(self.button_box)

        self.rescan_button.clicked.connect(self.request_rescan)
        self.adapter_combo.currentIndexChanged.connect(self.select_adapter)
        self.pairing_button.clicked.connect(self.request_pairing)
        self.delete_profile_button.clicked.connect(self.request_delete_profile)
        self.button_box.accepted.connect(self.request_save)
        self.button_box.rejected.connect(self.reject)

    @property
    def adapter_model(self) -> AdapterListModel:
        """Return the Qt model that presents the latest discovery result."""
        return self._adapter_model

    @property
    def profile_delete_confirmation(self) -> QMessageBox | None:
        """Return the visible profile-deletion confirmation, if any."""
        return self._profile_delete_confirmation

    def request_rescan(self) -> None:
        """Post one discovery action without waiting for its runtime result."""
        if not self.rescan_button.isEnabled():
            return
        self.rescan_button.setEnabled(False)
        self.discovery_label.setText(self.tr("Searching for USB adapters"))
        self._on_rescan()

    def request_pairing(self) -> None:
        """Request the application-owned pairing confirmation dialog."""
        on_request_pairing = self._on_request_pairing
        if (
            self.pairing_button.isEnabled()
            and on_request_pairing is not None
            and self.apply_connection_fields()
        ):
            on_request_pairing()

    def request_save(self) -> None:
        """Save the validated global settings without starting a connection."""
        if not self.save_button.isEnabled() or not self.apply_connection_fields():
            return
        on_save = self._on_save
        if on_save is not None and not on_save():
            self.connection_error_label.setText(self.tr("Could not save settings"))
            return
        self.connection_error_label.clear()
        self.accept()

    def reject(self) -> None:
        """Discard the active draft before a standard cancel, Esc, or close."""
        if not self._cancel_requested:
            on_cancel = self._on_cancel
            if on_cancel is not None and not on_cancel():
                return
            self._cancel_requested = True
        super().reject()

    def apply_connection_fields(self) -> bool:
        """Apply editable application-wide connection fields to the draft.

        Returns:
            Whether the controls updated the application-owned draft.
        """
        try:
            self._editor.update_connection(
                reconnect_on_start=self.reconnect_on_start_checkbox.isChecked(),
                diagnostic_level=self._selected_diagnostic_level(),
            )
        except DomainValueError:
            self.connection_error_label.setText(self.tr("Connection settings are invalid"))
            self.diagnostic_level_combo.setFocus()
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
            self._set_pairing_enabled(False)
            self.discovery_label.setText(
                self.tr("No USB adapters are available. Check the device and rescan.")
            )
            return
        if saved_adapter_index < 0:
            self._set_pairing_enabled(False)
            if self._editor.draft.connection.adapter_id:
                self.discovery_label.setText(
                    self.tr("The saved USB adapter was not found. Select an adapter.")
                )
                return
            self.discovery_label.setText(
                self.tr("{count} USB adapters found").format(count=len(adapters))
            )
            return
        self._set_pairing_enabled(True)
        self.discovery_label.setText(
            self.tr("{count} USB adapters found").format(count=len(adapters))
        )

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
            self._set_pairing_enabled(False)
            return
        self._editor.update_connection(adapter_id=adapter_id)
        self._set_pairing_enabled(True)
        self.discovery_label.setText(
            self.tr("Selected USB adapter: {adapter}").format(
                adapter=self.adapter_combo.itemText(index)
            )
        )

    def set_profile_exists(self, exists: bool) -> None:
        """Render whether the fixed controller connection profile exists."""
        self._profile_exists = exists
        self.profile_status_label.setText(self.tr("Saved") if exists else self.tr("Not saved"))
        self.delete_profile_button.setEnabled(exists and self._on_delete_profile is not None)

    def request_delete_profile(self) -> None:
        """Ask for confirmation before deleting the fixed profile."""
        if (
            not self._profile_exists
            or self._on_delete_profile is None
            or self._profile_delete_confirmation is not None
        ):
            return
        confirmation = QMessageBox(
            QMessageBox.Icon.Warning,
            self.tr("Delete controller profile?"),
            self.tr("The saved controller profile will be permanently deleted."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            self,
        )
        confirmation.setDefaultButton(QMessageBox.StandardButton.Cancel)
        delete_button = confirmation.button(QMessageBox.StandardButton.Yes)
        if delete_button is not None:
            delete_button.setText(self.tr("Delete"))
        confirmation.buttonClicked.connect(self._handle_profile_delete)
        confirmation.finished.connect(self._clear_profile_delete_confirmation)
        self._profile_delete_confirmation = confirmation
        confirmation.open()

    def _handle_profile_delete(self, button: QAbstractButton) -> None:
        confirmation = self._profile_delete_confirmation
        on_delete_profile = self._on_delete_profile
        if (
            confirmation is None
            or on_delete_profile is None
            or confirmation.standardButton(button) != QMessageBox.StandardButton.Yes
        ):
            return
        if not on_delete_profile():
            self.connection_error_label.setText(self.tr("Could not delete controller profile"))
            return
        self.connection_error_label.clear()
        self.set_profile_exists(False)

    def _clear_profile_delete_confirmation(self, _result: int) -> None:
        self._profile_delete_confirmation = None

    def _set_pairing_enabled(self, enabled: bool) -> None:
        self.pairing_button.setEnabled(enabled)

    def _selected_diagnostic_level(self) -> DiagnosticLevel:
        try:
            return DiagnosticLevel(self.diagnostic_level_combo.currentText())
        except ValueError:
            raise DomainValueError from None


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
        self.setWindowTitle(self.tr("Confirm new pairing"))
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
            self.tr("Pairing in progress") if busy else self.tr("Start a new pairing?")
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
