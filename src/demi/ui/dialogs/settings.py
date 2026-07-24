"""Unified Qt settings dialog with mapping, connection, and color tabs."""

from collections.abc import Callable
from enum import IntEnum

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractButton,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from demi.application.settings_editor import SettingsEditor
from demi.domain.settings import ControllerColorSettings

from .colors import ControllerColorsDialog
from .connection import ConnectionDialog
from .mapping import MappingDialog

type Action = Callable[[], object]
type BooleanAction = Callable[[], bool]
type PreviewAction = Callable[[ControllerColorSettings], object]


class SettingsTab(IntEnum):
    """Stable tab indices for the three settings entry points."""

    MAPPINGS = 0
    CONNECTION = 1
    COLORS = 2


class SettingsDialog(QDialog):
    """Edit one shared settings draft through three tabbed settings pages."""

    def __init__(
        self,
        editor: SettingsEditor,
        *,
        initial_tab: SettingsTab,
        connected: bool,
        on_rescan: Action,
        on_save: BooleanAction,
        on_cancel: BooleanAction,
        on_preview: PreviewAction,
        on_delete_profile: BooleanAction,
        on_request_pairing: BooleanAction,
        on_defer_reconnect: Action,
        on_reconnect: Action,
        on_dialog_opened: Action | None = None,
        on_release_capture: Action | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Create one modal that owns common Save and Cancel actions.

        Args:
            editor: Application-owned settings draft shared by every tab.
            initial_tab: Tab requested by the toolbar entry point.
            connected: Whether a color change needs a reconnect choice.
            on_rescan: Requests asynchronous USB adapter discovery.
            on_save: Persists the complete shared draft.
            on_cancel: Discards the complete shared draft.
            on_preview: Applies draft colors to the local controller preview.
            on_delete_profile: Deletes the fixed controller connection profile.
            on_request_pairing: Replaces this dialog with pairing confirmation.
            on_defer_reconnect: Keeps saved colors for a later connection.
            on_reconnect: Reconnects to apply saved colors.
            on_dialog_opened: Neutralizes active input capture.
            on_release_capture: Executes the fixed capture-release action.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self.setWindowTitle(self.tr("Settings"))
        self._editor = editor
        self._saved_colors = editor.draft.controller_colors
        self._connected = connected
        self._on_save = on_save
        self._on_cancel = on_cancel
        self._on_preview = on_preview
        self._on_defer_reconnect = on_defer_reconnect
        self._on_reconnect = on_reconnect
        self._cancel_requested = False
        self._conflict_confirmation: QMessageBox | None = None
        self._reconnect_confirmation: QMessageBox | None = None

        self.mapping_page = MappingDialog(
            editor,
            on_dialog_opened=on_dialog_opened,
            on_release_capture=on_release_capture,
            on_cancel=self._cancel_from_page,
            parent=self,
        )
        self.connection_page = ConnectionDialog(
            editor,
            on_rescan=on_rescan,
            on_request_pairing=on_request_pairing,
            on_delete_profile=on_delete_profile,
            on_cancel=self._cancel_from_page,
            parent=self,
        )
        self.colors_page = ControllerColorsDialog(
            editor,
            connected=False,
            on_preview=on_preview,
            on_save=lambda: True,
            on_cancel=self._cancel_from_page,
            on_defer_reconnect=lambda: None,
            on_reconnect=lambda: None,
            parent=self,
        )
        for page in (self.mapping_page, self.connection_page, self.colors_page):
            page.setWindowFlags(Qt.WindowType.Widget)
            page.setMinimumSize(0, 0)
            page.button_box.hide()

        self.tabs = QTabWidget(self)
        self.tabs.addTab(self.mapping_page, self.tr("Mappings"))
        self.tabs.addTab(self.connection_page, self.tr("Connection"))
        self.tabs.addTab(self.colors_page, self.tr("Colors"))
        self.tabs.setCurrentIndex(int(initial_tab))

        self.save_error_label = QLabel("", self)
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        layout.addWidget(self.save_error_label)
        layout.addWidget(self.button_box)
        self.setMinimumSize(760, 520)
        self.resize(860, 680)

        self.button_box.accepted.connect(self.request_save)
        self.button_box.rejected.connect(self.reject)

    @property
    def current_tab(self) -> SettingsTab:
        """Return the currently visible settings tab."""
        return SettingsTab(self.tabs.currentIndex())

    @property
    def conflict_confirmation(self) -> QMessageBox | None:
        """Return the visible mapping-conflict confirmation, if any."""
        return self._conflict_confirmation

    @property
    def reconnect_confirmation(self) -> QMessageBox | None:
        """Return the visible color-reconnect confirmation, if any."""
        return self._reconnect_confirmation

    def request_save(self) -> None:
        """Validate every page, then save the shared draft once."""
        if not self.connection_page.apply_connection_fields():
            self.tabs.setCurrentIndex(int(SettingsTab.CONNECTION))
            return
        conflict_summary = self.mapping_page.mapping_model.conflict_summary()
        if conflict_summary:
            self._open_conflict_confirmation(conflict_summary)
            return
        self._save()

    def reject(self) -> None:
        """Discard all tab changes and restore the saved color preview."""
        if not self._cancel_requested:
            if not self._on_cancel():
                return
            self._cancel_requested = True
            self._on_preview(self._saved_colors)
        super().reject()

    def _cancel_from_page(self) -> bool:
        """Route an embedded page cancellation to the shared draft owner."""
        self.reject()
        return self._cancel_requested

    def _open_conflict_confirmation(self, summary: str) -> None:
        if self._conflict_confirmation is not None:
            return
        confirmation = QMessageBox(
            QMessageBox.Icon.Warning,
            self.tr("Key mapping conflicts"),
            self.tr("Mappings conflict with duplicates or local actions."),
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel,
            self,
        )
        confirmation.setInformativeText(summary)
        confirmation.setDefaultButton(QMessageBox.StandardButton.Cancel)
        confirmation.buttonClicked.connect(self._handle_conflict_choice)
        confirmation.finished.connect(self._clear_conflict_confirmation)
        self._conflict_confirmation = confirmation
        confirmation.open()

    def _handle_conflict_choice(self, button: QAbstractButton) -> None:
        confirmation = self._conflict_confirmation
        if (
            confirmation is not None
            and confirmation.standardButton(button) == QMessageBox.StandardButton.Save
        ):
            self._save()

    def _save(self) -> None:
        colors_changed = self._editor.draft.controller_colors != self._saved_colors
        if not self._on_save():
            self.save_error_label.setText(self.tr("Could not save settings"))
            return
        self.save_error_label.clear()
        if self._connected and colors_changed:
            self._open_reconnect_confirmation()
            return
        self.accept()

    def _open_reconnect_confirmation(self) -> None:
        if self._reconnect_confirmation is not None:
            return
        confirmation = QMessageBox(self)
        confirmation.setIcon(QMessageBox.Icon.Information)
        confirmation.setWindowTitle(self.tr("Apply display colors"))
        confirmation.setText(self.tr("Reconnect to apply the display colors to the target device."))
        confirmation.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        confirmation.setDefaultButton(QMessageBox.StandardButton.No)
        reconnect_button = confirmation.button(QMessageBox.StandardButton.Yes)
        if reconnect_button is not None:
            reconnect_button.setText(self.tr("Reconnect"))
        defer_button = confirmation.button(QMessageBox.StandardButton.No)
        if defer_button is not None:
            defer_button.setText(self.tr("Later"))
        confirmation.buttonClicked.connect(self._handle_reconnect_choice)
        confirmation.finished.connect(self._clear_reconnect_confirmation)
        self._reconnect_confirmation = confirmation
        confirmation.open()

    def _handle_reconnect_choice(self, button: QAbstractButton) -> None:
        confirmation = self._reconnect_confirmation
        if confirmation is None:
            return
        if confirmation.standardButton(button) == QMessageBox.StandardButton.Yes:
            self._on_reconnect()
        else:
            self._on_defer_reconnect()
        self.accept()

    def _clear_conflict_confirmation(self, _result: int) -> None:
        self._conflict_confirmation = None

    def _clear_reconnect_confirmation(self, _result: int) -> None:
        self._reconnect_confirmation = None
