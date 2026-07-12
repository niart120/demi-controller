"""Toolbar state presentation for the main window."""

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
_CONNECTION_ACTIONS = {
    ConnectionState.STOPPED: "接続設定",
    ConnectionState.READY: "接続",
    ConnectionState.CONNECTED: "切断",
    ConnectionState.ERROR: "再試行",
}
_BUSY_CONNECTION_STATES = frozenset(
    {
        ConnectionState.STARTING,
        ConnectionState.DISCOVERING,
        ConnectionState.CONNECTING,
        ConnectionState.DISCONNECTING,
        ConnectionState.STOPPING,
    }
)


@dataclass(frozen=True, slots=True)
class ToolbarModel:
    """Labels and enabled flags presented by the toolbar."""

    connection_label: str
    connection_action_label: str
    connection_action_enabled: bool
    capture_label: str
    capture_enabled: bool
    settings_enabled: bool


class Toolbar:
    """Derive toolbar presentation from application and connection state."""

    def __init__(self) -> None:
        """Initialize the toolbar with an idle, unconfigured presentation."""
        self._model = ToolbarModel(
            connection_label=_CONNECTION_LABELS[ConnectionState.STOPPED],
            connection_action_label=_CONNECTION_ACTIONS[ConnectionState.STOPPED],
            connection_action_enabled=True,
            capture_label="入力開始",
            capture_enabled=True,
            settings_enabled=True,
        )

    @property
    def model(self) -> ToolbarModel:
        """Return the latest toolbar presentation."""
        return self._model

    def update(
        self,
        *,
        app_state: AppState,
        connection_state: ConnectionState,
        focused: bool,
        dialog_open: bool,
    ) -> ToolbarModel:
        """Update labels and action availability for current UI state.

        Args:
            app_state: Application lifecycle state.
            connection_state: Connection lifecycle state.
            focused: Whether the main window has keyboard focus.
            dialog_open: Whether a modal dialog owns UI input.

        Returns:
            The updated toolbar presentation.
        """
        capture_enabled = (
            focused and not dialog_open and app_state in {AppState.IDLE, AppState.CAPTURED}
        )
        connection_action_enabled = (
            not dialog_open and connection_state not in _BUSY_CONNECTION_STATES
        )
        action_label = _CONNECTION_ACTIONS.get(connection_state, "待機中")
        self._model = ToolbarModel(
            connection_label=_CONNECTION_LABELS[connection_state],
            connection_action_label=action_label,
            connection_action_enabled=connection_action_enabled,
            capture_label="入力停止" if app_state is AppState.CAPTURED else "入力開始",
            capture_enabled=capture_enabled,
            settings_enabled=focused and not dialog_open and app_state is AppState.IDLE,
        )
        return self._model
