"""Qt status bar that renders application state as explicit text."""

from dataclasses import dataclass

from PySide6.QtWidgets import QLabel, QStatusBar, QWidget

from demi.application.state import AppState, ConnectionState
from demi.input.relative_pointer import RelativePointerQuality


@dataclass(frozen=True, slots=True)
class StatusBarState:
    """Describe the values rendered in the main status bar.

    Attributes:
        adapter_label: Safe label for the selected adapter.
        connection_state: Current connection lifecycle state.
        application_state: Current capture and lifecycle state.
        pointer_quality: Provenance of relative pointer values.
        preview_only: Whether frames are displayed without runtime output.
        warning: Current safe warning, if any.
        error: Current safe error, if any.
    """

    adapter_label: str
    connection_state: ConnectionState
    application_state: AppState
    pointer_quality: RelativePointerQuality
    preview_only: bool
    warning: str
    error: str | None


class MainStatusBar(QStatusBar):
    """Render independent application status categories with Qt labels."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create a status bar with permanently visible text fields.

        Args:
            parent: Optional Qt parent for the status bar.
        """
        super().__init__(parent)
        self.adapter_label = QLabel(self)
        self.connection_label = QLabel(self)
        self.capture_label = QLabel(self)
        self.pointer_label = QLabel(self)
        self.preview_label = QLabel(self)
        self.notice_label = QLabel(self)
        for label in (
            self.adapter_label,
            self.connection_label,
            self.capture_label,
            self.pointer_label,
            self.preview_label,
            self.notice_label,
        ):
            self.addPermanentWidget(label)

    def refresh(self, state: StatusBarState) -> None:
        """Render state using text that does not depend on color.

        Args:
            state: Main-thread state snapshot for the status bar.
        """
        self.adapter_label.setText(f"アダプター: {state.adapter_label}")
        self.connection_label.setText(f"接続: {_connection_text(state.connection_state)}")
        self.capture_label.setText(f"入力: {_capture_text(state.application_state)}")
        self.pointer_label.setText(f"ポインター: {_pointer_text(state.pointer_quality)}")
        self.preview_label.setText(
            "プレビュー: のみ" if state.preview_only else "プレビュー: 送信あり"
        )
        if state.error is not None:
            self.notice_label.setText(f"エラー: {state.error}")
        elif state.warning:
            self.notice_label.setText(f"警告: {state.warning}")
        else:
            self.notice_label.setText("通知: なし")


def _connection_text(state: ConnectionState) -> str:
    return {
        ConnectionState.STOPPED: "停止",
        ConnectionState.STARTING: "開始中",
        ConnectionState.READY: "準備完了",
        ConnectionState.DISCOVERING: "検索中",
        ConnectionState.CONNECTING: "接続中",
        ConnectionState.CONNECTED: "接続済み",
        ConnectionState.DISCONNECTING: "切断中",
        ConnectionState.ERROR: "エラー",
        ConnectionState.STOPPING: "停止中",
    }[state]


def _capture_text(state: AppState) -> str:
    return "捕捉中" if state is AppState.CAPTURED else "停止中"


def _pointer_text(quality: RelativePointerQuality) -> str:
    return {
        RelativePointerQuality.RAW_UNACCELERATED: "Raw Input",
        RelativePointerQuality.RELATIVE_ACCELERATED: "OS補正あり",
        RelativePointerQuality.UNAVAILABLE: "利用不可",
    }[quality]
