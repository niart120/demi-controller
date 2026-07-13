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


@dataclass(frozen=True, slots=True)
class ToolbarControl:
    """One positioned, hit-testable toolbar action."""

    action: str
    label: str
    enabled: bool
    x: float
    y: float
    width: float
    height: float

    def contains(self, x: float, y: float) -> bool:
        """Return whether a logical window coordinate is inside this control."""
        return self.x <= x <= self.x + self.width and self.y <= y <= self.y + self.height


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
        adapter_available: bool = True,
    ) -> ToolbarModel:
        """Update labels and action availability for current UI state.

        Args:
            app_state: Application lifecycle state.
            connection_state: Connection lifecycle state.
            focused: Whether the main window has keyboard focus.
            dialog_open: Whether a modal dialog owns UI input.
            adapter_available: Whether discovery currently has any adapter
                available for a saved connection request.

        Returns:
            The updated toolbar presentation.
        """
        capture_enabled = (
            focused and not dialog_open and app_state in {AppState.IDLE, AppState.CAPTURED}
        )
        connection_action_enabled = (
            not dialog_open
            and connection_state not in _BUSY_CONNECTION_STATES
            and (
                adapter_available
                or connection_state in {ConnectionState.STOPPED, ConnectionState.CONNECTED}
            )
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

    def controls(self, *, width: int, height: int) -> tuple[ToolbarControl, ...]:
        """Return positioned controls for the current main-window dimensions.

        Args:
            width: Logical window width in pixels.
            height: Logical window height in pixels.

        Returns:
            Ordered action controls with state-derived enabled flags.
        """
        del width
        y = float(height - 44)
        height_px = 32.0
        x = 126.0
        definitions = (
            (
                "connection",
                self._model.connection_action_label,
                self._model.connection_action_enabled,
                100.0,
            ),
            ("capture", self._model.capture_label, self._model.capture_enabled, 100.0),
            ("mapping", "割当", self._model.settings_enabled, 64.0),
            ("connection_settings", "接続設定", self._model.settings_enabled, 84.0),
            ("colors", "色", self._model.settings_enabled, 64.0),
        )
        controls: list[ToolbarControl] = []
        for action, label, enabled, control_width in definitions:
            controls.append(
                ToolbarControl(
                    action=action,
                    label=label,
                    enabled=enabled,
                    x=x,
                    y=y,
                    width=control_width,
                    height=height_px,
                )
            )
            x += control_width + 8.0
        return tuple(controls)

    def hit_test(
        self,
        x: float,
        y: float,
        *,
        width: int,
        height: int,
    ) -> ToolbarControl | None:
        """Return the enabled toolbar control at a logical window coordinate."""
        for control in self.controls(width=width, height=height):
            if control.enabled and control.contains(x, y):
                return control
        return None
