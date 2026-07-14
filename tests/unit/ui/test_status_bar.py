from PySide6.QtWidgets import QStatusBar

from demi.application.state import AppState, ConnectionState
from demi.input.relative_pointer import RelativePointerQuality
from demi.ui.status_bar import MainStatusBar, StatusBarState


def test_status_bar_exposes_all_runtime_categories_as_text(qt_application: object) -> None:
    assert qt_application is not None
    status_bar = MainStatusBar()

    assert isinstance(status_bar, QStatusBar)

    status_bar.refresh(
        StatusBarState(
            adapter_label="USB Bluetooth adapter",
            connection_state=ConnectionState.CONNECTED,
            application_state=AppState.CAPTURED,
            pointer_quality=RelativePointerQuality.RAW_UNACCELERATED,
            preview_only=True,
            warning="入力監視タイムアウト",
            error="接続が切断されました",
        )
    )

    assert status_bar.adapter_label.text() == "アダプター: USB Bluetooth adapter"
    assert status_bar.connection_label.text() == "接続: 接続済み"
    assert status_bar.capture_label.text() == "入力: 捕捉中"
    assert status_bar.pointer_label.text() == "ポインター: Raw Input"
    assert status_bar.preview_label.text() == "プレビュー: のみ"
    assert status_bar.notice_label.text() == "エラー: 接続が切断されました"

    status_bar.refresh(
        StatusBarState(
            adapter_label="なし",
            connection_state=ConnectionState.READY,
            application_state=AppState.IDLE,
            pointer_quality=RelativePointerQuality.UNAVAILABLE,
            preview_only=False,
            warning="USB アダプターを選択してください",
            error=None,
        )
    )

    assert status_bar.connection_label.text() == "接続: 準備完了"
    assert status_bar.capture_label.text() == "入力: 停止中"
    assert status_bar.pointer_label.text() == "ポインター: 利用不可"
    assert status_bar.preview_label.text() == "プレビュー: 送信あり"
    assert status_bar.notice_label.text() == "警告: USB アダプターを選択してください"
