from demi.application.presentation import AdapterOption, PresentationStore
from demi.application.state import ConnectionState


def test_presentation_keeps_an_unacknowledged_error_across_ready() -> None:
    presentation = PresentationStore()

    presentation.set_error("保存済み接続に失敗しました")
    presentation.set_connection(ConnectionState.READY)

    assert presentation.model.connection_state is ConnectionState.READY
    assert presentation.model.error == "保存済み接続に失敗しました"
    assert presentation.model.warning == "保存済み接続に失敗しました"

    presentation.set_connection(
        ConnectionState.CONNECTED, adapter_id="usb:0", adapter_label="Adapter"
    )

    assert presentation.model.error is None
    assert presentation.model.warning == ""
    assert presentation.model.adapter_label == "Adapter"


def test_presentation_tracks_adapter_choices_and_color_reconnect_prompt() -> None:
    presentation = PresentationStore()
    options = (AdapterOption("usb:0", "Adapter 0"), AdapterOption("usb:1", "Adapter 1"))

    presentation.set_adapters(options)
    presentation.set_color_reconnect_pending(True)

    assert presentation.model.adapters == options
    assert presentation.model.color_reconnect_pending is True
    assert presentation.has_adapter("usb:1") is True
    assert presentation.has_adapter("usb:9") is False


def test_presentation_acknowledges_only_the_rendered_recovery_notice() -> None:
    presentation = PresentationStore()
    presentation.set_recovery_notice("設定を復旧しました")

    assert presentation.acknowledge_recovery_notice("異なる通知") is False
    assert presentation.model.recovery_notice == "設定を復旧しました"
    assert presentation.acknowledge_recovery_notice("設定を復旧しました") is True
    assert presentation.model.recovery_notice is None
    assert presentation.acknowledge_recovery_notice("設定を復旧しました") is False
