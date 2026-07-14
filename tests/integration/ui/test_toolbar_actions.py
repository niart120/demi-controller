from dataclasses import dataclass

from demi.application.state import AppState, ConnectionState
from demi.ui.toolbar import MainToolBar, ToolbarState


@dataclass
class FakeApplicationActions:
    """Record semantic requests received from a toolbar."""

    connection_requests: int = 0

    def connection_action(self) -> None:
        """Record one state-dependent connect or disconnect request."""
        self.connection_requests += 1


def test_connection_action_delegates_once_when_ready_or_connected_and_not_when_busy(
    qt_application: object,
) -> None:
    assert qt_application is not None
    toolbar = MainToolBar()
    actions = FakeApplicationActions()
    toolbar.bind_connection_action(actions.connection_action)

    toolbar.refresh(
        ToolbarState(
            application_state=AppState.IDLE,
            connection_state=ConnectionState.READY,
            dialog_open=False,
        )
    )
    toolbar.connection_action.trigger()

    assert actions.connection_requests == 1

    toolbar.refresh(
        ToolbarState(
            application_state=AppState.IDLE,
            connection_state=ConnectionState.CONNECTING,
            dialog_open=False,
        )
    )
    toolbar.connection_action.trigger()

    assert actions.connection_requests == 1

    toolbar.refresh(
        ToolbarState(
            application_state=AppState.IDLE,
            connection_state=ConnectionState.CONNECTED,
            dialog_open=False,
        )
    )
    toolbar.connection_action.trigger()

    assert actions.connection_requests == 2
