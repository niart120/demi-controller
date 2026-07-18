from PySide6.QtWidgets import QToolBar

from demi.application.state import AppState, ConnectionState
from demi.ui.toolbar import MainToolBar, ToolbarState


def test_toolbar_actions_follow_application_connection_capture_dialog_and_shutdown_state(
    qt_application: object,
) -> None:
    assert qt_application is not None
    toolbar = MainToolBar()

    assert isinstance(toolbar, QToolBar)

    toolbar.refresh(
        ToolbarState(
            application_state=AppState.IDLE,
            connection_state=ConnectionState.READY,
            dialog_open=False,
        )
    )

    assert toolbar.connection_action.text() == "Connect"
    assert toolbar.connection_action.isEnabled() is True
    assert toolbar.capture_action.text() == "Start input"
    assert toolbar.capture_action.isChecked() is False
    assert toolbar.capture_action.isEnabled() is True
    assert toolbar.mapping_action.isEnabled() is True
    assert toolbar.connection_settings_action.isEnabled() is True
    assert toolbar.colors_action.isEnabled() is True

    toolbar.refresh(
        ToolbarState(
            application_state=AppState.CAPTURED,
            connection_state=ConnectionState.CONNECTED,
            dialog_open=False,
        )
    )

    assert toolbar.connection_action.text() == "Disconnect"
    assert toolbar.connection_action.isEnabled() is True
    assert toolbar.capture_action.text() == "Stop input"
    assert toolbar.capture_action.isChecked() is True
    assert toolbar.capture_action.isEnabled() is True
    assert toolbar.mapping_action.isEnabled() is True

    toolbar.refresh(
        ToolbarState(
            application_state=AppState.CONFIGURING,
            connection_state=ConnectionState.CONNECTING,
            dialog_open=True,
        )
    )

    assert toolbar.connection_action.isEnabled() is False
    assert toolbar.capture_action.isEnabled() is False
    assert toolbar.mapping_action.isEnabled() is False
    assert toolbar.connection_settings_action.isEnabled() is False
    assert toolbar.colors_action.isEnabled() is False

    toolbar.refresh(
        ToolbarState(
            application_state=AppState.SHUTTING_DOWN,
            connection_state=ConnectionState.STOPPING,
            dialog_open=False,
        )
    )

    assert all(action.isEnabled() is False for action in toolbar.actions())
