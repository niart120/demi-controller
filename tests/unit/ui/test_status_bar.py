from demi.application.state import AppState, ConnectionState
from demi.ui.status_bar import StatusBar


def test_status_bar_shows_connection_capture_interval_and_warning() -> None:
    status_bar = StatusBar()

    model = status_bar.update(
        adapter_label="usb:0",
        connection_state=ConnectionState.CONNECTED,
        app_state=AppState.CAPTURED,
        preview_only=False,
    )

    assert model.text == "Adapter: usb:0 | 接続済み | Input: Captured | 8 ms"
    assert model.warning == ""


def test_status_bar_explains_preview_only_capture_without_connection() -> None:
    status_bar = StatusBar()

    model = status_bar.update(
        adapter_label="なし",
        connection_state=ConnectionState.READY,
        app_state=AppState.CAPTURED,
        preview_only=True,
    )

    assert "Input: Captured" in model.text
    assert model.warning == "プレビューのみ。対象機器へは送信していない"
    assert model.text.endswith(model.warning)
