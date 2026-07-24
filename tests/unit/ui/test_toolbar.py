from PySide6.QtWidgets import QMenu, QToolBar, QToolButton

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
    assert not hasattr(toolbar, "capture_action")
    assert toolbar.mouse_input_status.text() == "Mouse input: OFF (F5)"
    assert "#7A1F1F" in toolbar.mouse_input_status.styleSheet()
    assert isinstance(toolbar.settings_button, QToolButton)
    assert toolbar.settings_button.text() == "Settings"
    assert isinstance(toolbar.settings_menu, QMenu)
    assert toolbar.settings_button.menu() is toolbar.settings_menu
    assert toolbar.settings_menu.actions() == [
        toolbar.connection_settings_action,
        toolbar.bindings_action,
        toolbar.mouse_action,
        toolbar.colors_action,
    ]
    assert [action.text() for action in toolbar.settings_menu.actions()] == [
        "Connection",
        "Bindings",
        "Mouse",
        "Colors",
    ]
    assert not hasattr(toolbar, "mapping_action")
    assert toolbar.connection_settings_action not in toolbar.actions()
    assert toolbar.bindings_action not in toolbar.actions()
    assert toolbar.mouse_action not in toolbar.actions()
    assert toolbar.colors_action not in toolbar.actions()
    assert toolbar.settings_button.isEnabled() is True
    assert toolbar.connection_settings_action.isEnabled() is True
    assert toolbar.bindings_action.isEnabled() is True
    assert toolbar.mouse_action.isEnabled() is True
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
    assert toolbar.mouse_input_status.text() == "Mouse input: ON (F5)"
    assert "#176B3A" in toolbar.mouse_input_status.styleSheet()
    assert toolbar.bindings_action.isEnabled() is True

    toolbar.refresh(
        ToolbarState(
            application_state=AppState.CONFIGURING,
            connection_state=ConnectionState.CONNECTING,
            dialog_open=True,
        )
    )

    assert toolbar.connection_action.isEnabled() is False
    assert toolbar.connection_settings_action.isEnabled() is False
    assert toolbar.bindings_action.isEnabled() is False
    assert toolbar.mouse_action.isEnabled() is False
    assert toolbar.colors_action.isEnabled() is False
    assert toolbar.settings_button.isEnabled() is False

    toolbar.refresh(
        ToolbarState(
            application_state=AppState.SHUTTING_DOWN,
            connection_state=ConnectionState.STOPPING,
            dialog_open=False,
        )
    )

    assert all(action.isEnabled() is False for action in toolbar.actions())
    assert toolbar.settings_button.isEnabled() is False
