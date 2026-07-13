"""Modal dialog state owned by the application layer."""

from dataclasses import dataclass
from enum import StrEnum


class DialogKind(StrEnum):
    """Modal kinds available to the settings and error UI."""

    NONE = "none"
    MAPPING = "mapping"
    CONNECTION = "connection"
    COLORS = "colors"
    PAIRING_CONFIRMATION = "pairing_confirmation"
    ERROR_DETAILS = "error_details"


@dataclass(frozen=True, slots=True)
class DialogModel:
    """Immutable presentation state for the currently open modal."""

    kind: DialogKind
    title: str
    visible: bool


_DIALOG_TITLES = {
    DialogKind.NONE: "",
    DialogKind.MAPPING: "キー割り当て",
    DialogKind.CONNECTION: "接続設定",
    DialogKind.COLORS: "コントローラーカラー",
    DialogKind.PAIRING_CONFIRMATION: "新規ペアリングの確認",
    DialogKind.ERROR_DETAILS: "エラー詳細",
}


class DialogManager:
    """Allow exactly one modal dialog to be active at a time."""

    def __init__(self) -> None:
        """Initialize with no open dialog."""
        self._kind = DialogKind.NONE

    @property
    def model(self) -> DialogModel:
        """Return the current display-free dialog model."""
        return DialogModel(
            kind=self._kind,
            title=_DIALOG_TITLES[self._kind],
            visible=self._kind is not DialogKind.NONE,
        )

    def open(self, kind: DialogKind) -> bool:
        """Open a modal when no other modal is active."""
        if kind is DialogKind.NONE or self._kind is not DialogKind.NONE:
            return False
        self._kind = kind
        return True

    def replace(self, kind: DialogKind) -> bool:
        """Replace the active modal without leaving configuration mode.

        Args:
            kind: Non-empty modal that supersedes the current modal.

        Returns:
            ``True`` when an existing modal was replaced.
        """
        if kind is DialogKind.NONE or self._kind is DialogKind.NONE:
            return False
        self._kind = kind
        return True

    def close(self) -> None:
        """Close the current modal; repeated calls are safe."""
        self._kind = DialogKind.NONE
