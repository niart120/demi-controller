"""Status bar presentation for connection and capture state."""

from dataclasses import dataclass

from demi.application.state import AppState, ConnectionState

_CONNECTION_LABELS = {
    ConnectionState.STOPPED: "未設定",
    ConnectionState.STARTING: "起動中",
    ConnectionState.READY: "切断",
    ConnectionState.DISCOVERING: "検索中",
    ConnectionState.CONNECTING: "接続中",
    ConnectionState.CONNECTED: "接続済み",
    ConnectionState.DISCONNECTING: "切断中",
    ConnectionState.ERROR: "エラー",
    ConnectionState.STOPPING: "停止中",
}
_PREVIEW_WARNING = "プレビューのみ。対象機器へは送信していない"


@dataclass(frozen=True, slots=True)
class StatusBarModel:
    """Text values displayed in the persistent status bar."""

    text: str
    adapter_label: str
    connection_label: str
    capture_label: str
    evaluation_interval_ms: int
    warning: str


class StatusBar:
    """Build a compact status line without exposing protocol internals."""

    def __init__(self, *, evaluation_interval_ms: int = 8) -> None:
        """Initialize a status bar with the input evaluation interval."""
        self._evaluation_interval_ms = evaluation_interval_ms
        self._model = self._build_model(
            adapter_label="なし",
            connection_state=ConnectionState.STOPPED,
            app_state=AppState.IDLE,
            preview_only=False,
            warning=None,
        )

    @property
    def model(self) -> StatusBarModel:
        """Return the latest status bar presentation."""
        return self._model

    def update(
        self,
        *,
        adapter_label: str,
        connection_state: ConnectionState,
        app_state: AppState,
        preview_only: bool,
        warning: str | None = None,
    ) -> StatusBarModel:
        """Update status text for the current connection and capture state.

        Args:
            adapter_label: Safe display name for the selected adapter.
            connection_state: Current connection state.
            app_state: Current application lifecycle state.
            preview_only: Whether capture is not connected to a target device.
            warning: Optional warning that takes precedence over preview text.

        Returns:
            The updated status bar model.
        """
        self._model = self._build_model(
            adapter_label=adapter_label,
            connection_state=connection_state,
            app_state=app_state,
            preview_only=preview_only,
            warning=warning,
        )
        return self._model

    def _build_model(
        self,
        *,
        adapter_label: str,
        connection_state: ConnectionState,
        app_state: AppState,
        preview_only: bool,
        warning: str | None,
    ) -> StatusBarModel:
        connection_label = _CONNECTION_LABELS[connection_state]
        capture_label = {
            AppState.CAPTURED: "Captured",
            AppState.SUSPENDED: "Suspended",
        }.get(app_state, "Idle")
        warning_text = warning or (_PREVIEW_WARNING if preview_only else "")
        parts = [
            f"Adapter: {adapter_label}",
            connection_label,
            f"Input: {capture_label}",
            f"{self._evaluation_interval_ms} ms",
        ]
        if warning_text:
            parts.append(warning_text)
        return StatusBarModel(
            text=" | ".join(parts),
            adapter_label=adapter_label,
            connection_label=connection_label,
            capture_label=capture_label,
            evaluation_interval_ms=self._evaluation_interval_ms,
            warning=warning_text,
        )
