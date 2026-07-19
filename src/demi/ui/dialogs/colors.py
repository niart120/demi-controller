"""Qt dialog for editable controller preview colors."""

from collections.abc import Callable

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractButton,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from demi.application.settings_editor import ColorField, SettingsEditor
from demi.domain.errors import DomainValueError
from demi.domain.settings import ControllerColorSettings

type PreviewAction = Callable[[ControllerColorSettings], object]
type SaveAction = Callable[[], bool]
type CancelAction = Callable[[], bool]
type ReconnectAction = Callable[[], object]

_COLOR_LABELS: dict[ColorField, str] = {
    "body": "Body",
    "buttons": "Buttons",
    "left_grip": "Left grip",
    "right_grip": "Right grip",
}


class ControllerColorsDialog(QDialog):
    """Edit a color draft through standard Qt color-selection controls."""

    def __init__(
        self,
        editor: SettingsEditor,
        *,
        connected: bool,
        on_preview: PreviewAction,
        on_save: SaveAction,
        on_cancel: CancelAction,
        on_defer_reconnect: ReconnectAction,
        on_reconnect: ReconnectAction,
        parent: QWidget | None = None,
    ) -> None:
        """Create a color dialog without directly persisting widget values.

        Args:
            editor: Application-owned immutable settings draft editor.
            connected: Whether a saved color needs an explicit reconnect choice.
            on_preview: Applies the current draft colors to the local preview.
            on_save: Persists the draft and reports whether it succeeded.
            on_cancel: Discards the draft and reports whether it succeeded.
            on_defer_reconnect: Leaves saved colors for a later reconnect.
            on_reconnect: Requests an immediate reconnect with saved colors.
            parent: Optional Qt parent for dialog ownership.
        """
        super().__init__(parent)
        self.setWindowTitle(self.tr("Controller colors"))
        self._editor = editor
        self._saved_colors = editor.draft.controller_colors
        self._connected = connected
        self._on_preview = on_preview
        self._on_save = on_save
        self._on_cancel = on_cancel
        self._on_defer_reconnect = on_defer_reconnect
        self._on_reconnect = on_reconnect
        self._color_dialog: QColorDialog | None = None
        self._reconnect_confirmation: QMessageBox | None = None
        self._cancel_requested = False

        self.color_buttons: dict[ColorField, QPushButton] = {}
        color_form = QFormLayout()
        for field, label in _COLOR_LABELS.items():
            button = QPushButton(self)
            button.clicked.connect(
                lambda _checked=False, selected_field=field: self.open_color_dialog(selected_field)
            )
            self.color_buttons[field] = button
            color_form.addRow(label, button)

        self.save_error_label = QLabel("", self)
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        layout = QVBoxLayout(self)
        layout.addLayout(color_form)
        layout.addWidget(self.save_error_label)
        layout.addWidget(self.button_box)

        self.button_box.accepted.connect(self.request_save)
        self.button_box.rejected.connect(self.request_cancel)
        self._refresh_color_buttons(self._saved_colors)

    @property
    def reconnect_confirmation(self) -> QMessageBox | None:
        """Return the visible reconnect choice after a successful save, if any."""
        return self._reconnect_confirmation

    @property
    def color_dialog(self) -> QColorDialog | None:
        """Return the currently open standard color picker, if any."""
        return self._color_dialog

    def set_color(self, field: ColorField, value: str) -> bool:
        """Update one draft color and immediately refresh the local preview.

        Args:
            field: One editable controller color field.
            value: Candidate `#RRGGBB` color accepted by the domain editor.
        """
        try:
            self._editor.update_color(field, value)
        except DomainValueError:
            self.save_error_label.setText(self.tr("The color format is invalid"))
            return False
        colors = self._editor.draft.controller_colors
        self._refresh_color_buttons(colors)
        self.save_error_label.clear()
        self._on_preview(colors)
        return True

    def open_color_dialog(self, field: ColorField) -> None:
        """Open the standard non-blocking color picker for one field.

        Args:
            field: Draft color field to update when a color is selected.
        """
        previous_dialog = self._color_dialog
        if previous_dialog is not None:
            previous_dialog.close()
        dialog = QColorDialog(QColor(self._color_value(field)), self)
        dialog.colorSelected.connect(
            lambda color, selected_field=field: self.set_color(selected_field, color.name())
        )
        dialog.finished.connect(self._clear_color_dialog)
        self._color_dialog = dialog
        dialog.open()

    def request_save(self) -> None:
        """Persist the draft, then request a reconnect choice if connected."""
        if not self._on_save():
            self.save_error_label.setText(self.tr("Could not save settings"))
            return
        self.save_error_label.clear()
        if not self._connected:
            self.accept()
            return
        self._open_reconnect_confirmation()

    def request_cancel(self) -> None:
        """Discard the draft and restore the saved colors in the local preview."""
        self.reject()

    def reject(self) -> None:
        """Discard the active draft before a standard cancel, Esc, or close."""
        if not self._cancel_requested:
            if not self._on_cancel():
                return
            self._cancel_requested = True
            self._on_preview(self._saved_colors)
        super().reject()

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

    def _refresh_color_buttons(self, colors: ControllerColorSettings) -> None:
        for field, button in self.color_buttons.items():
            color = self._color_value(field, colors)
            button.setText("")
            button.setProperty("swatchColor", color)
            button.setStyleSheet(f"background-color: {color};")

    def _color_value(
        self,
        field: ColorField,
        colors: ControllerColorSettings | None = None,
    ) -> str:
        current_colors = self._editor.draft.controller_colors if colors is None else colors
        return getattr(current_colors, field)

    def _clear_color_dialog(self, _result: int) -> None:
        self._color_dialog = None

    def _clear_reconnect_confirmation(self, _result: int) -> None:
        self._reconnect_confirmation = None
