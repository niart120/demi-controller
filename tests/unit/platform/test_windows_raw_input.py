from PySide6.QtCore import QAbstractNativeEventFilter, QByteArray

from demi.platform.windows_raw_input import WindowsRawInputFilter


def test_native_event_filter_leaves_non_raw_messages_for_qt() -> None:
    native_filter = WindowsRawInputFilter()

    assert isinstance(native_filter, QAbstractNativeEventFilter)
    assert (
        native_filter.nativeEventFilter(
            QByteArray(b"windows_generic_MSG"),
            0,
        )
        is False
    )
    assert native_filter.nativeEventFilter(QByteArray(b"xcb_generic_event_t"), 0) is False
