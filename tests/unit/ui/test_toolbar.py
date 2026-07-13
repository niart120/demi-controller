from demi.application.state import AppState, ConnectionState
from demi.ui.toolbar import Toolbar


def test_toolbar_exposes_capture_and_connection_actions_for_idle_state() -> None:
    toolbar = Toolbar()

    model = toolbar.update(
        app_state=AppState.IDLE,
        connection_state=ConnectionState.READY,
        focused=True,
        dialog_open=False,
    )

    assert model.connection_label == "切断"
    assert model.connection_action_label == "接続"
    assert model.connection_action_enabled is True
    assert model.capture_label == "入力開始"
    assert model.capture_enabled is True


def test_toolbar_disables_capture_for_focus_loss_or_dialog() -> None:
    toolbar = Toolbar()

    suspended = toolbar.update(
        app_state=AppState.SUSPENDED,
        connection_state=ConnectionState.CONNECTED,
        focused=False,
        dialog_open=False,
    )
    configuring = toolbar.update(
        app_state=AppState.CONFIGURING,
        connection_state=ConnectionState.CONNECTED,
        focused=True,
        dialog_open=True,
    )

    assert suspended.capture_enabled is False
    assert suspended.capture_label == "入力開始"
    assert configuring.capture_enabled is False
    assert configuring.connection_action_enabled is False


def test_toolbar_exposes_hit_testable_controls_and_omits_disabled_actions() -> None:
    toolbar = Toolbar()
    toolbar.update(
        app_state=AppState.IDLE,
        connection_state=ConnectionState.READY,
        focused=True,
        dialog_open=False,
    )

    controls = toolbar.controls(width=800, height=520)
    capture = next(control for control in controls if control.action == "capture")

    assert [control.action for control in controls] == [
        "connection",
        "capture",
        "mapping",
        "connection_settings",
        "colors",
    ]
    assert toolbar.hit_test(capture.x + 1, capture.y + 1, width=800, height=520) == capture

    toolbar.update(
        app_state=AppState.CONFIGURING,
        connection_state=ConnectionState.CONNECTED,
        focused=True,
        dialog_open=True,
    )
    disabled_capture = next(
        control
        for control in toolbar.controls(width=800, height=520)
        if control.action == "capture"
    )

    assert disabled_capture.enabled is False
    assert (
        toolbar.hit_test(
            disabled_capture.x + 1,
            disabled_capture.y + 1,
            width=800,
            height=520,
        )
        is None
    )


def test_toolbar_disables_connect_without_a_discovered_adapter_but_keeps_disconnect() -> None:
    toolbar = Toolbar()

    unavailable = toolbar.update(
        app_state=AppState.IDLE,
        connection_state=ConnectionState.READY,
        focused=True,
        dialog_open=False,
        adapter_available=False,
    )
    connected = toolbar.update(
        app_state=AppState.IDLE,
        connection_state=ConnectionState.CONNECTED,
        focused=True,
        dialog_open=False,
        adapter_available=False,
    )

    assert unavailable.connection_action_enabled is False
    assert connected.connection_action_enabled is True
