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
            warning="Input monitoring timed out",
            error="Connection lost",
        )
    )

    assert status_bar.adapter_label.text() == "Adapter: USB Bluetooth adapter"
    assert status_bar.connection_label.text() == "Connection: Connected"
    assert status_bar.capture_label.text() == "Mouse capture: On"
    assert status_bar.pointer_label.text() == "Pointer: Raw Input"
    assert status_bar.preview_label.text() == "Preview: only"
    assert status_bar.notice_label.text() == "Error: Connection lost"

    status_bar.refresh(
        StatusBarState(
            adapter_label="None",
            connection_state=ConnectionState.READY,
            application_state=AppState.IDLE,
            pointer_quality=RelativePointerQuality.UNAVAILABLE,
            preview_only=False,
            warning="Select a USB adapter",
            error=None,
        )
    )

    assert status_bar.connection_label.text() == "Connection: Ready"
    assert status_bar.capture_label.text() == "Mouse capture: Off"
    assert status_bar.pointer_label.text() == "Pointer: Unavailable"
    assert status_bar.preview_label.text() == "Preview: transmitting"
    assert status_bar.notice_label.text() == "Warning: Select a USB adapter"
