"""Keep Windows native messages at the platform boundary."""

from PySide6.QtCore import QAbstractNativeEventFilter, QByteArray

type NativeEventType = QByteArray | bytes | bytearray | memoryview


class WindowsRawInputFilter(QAbstractNativeEventFilter):
    """Receive native events without suppressing Qt's normal event delivery."""

    def nativeEventFilter(  # noqa: N802 - Qt override name.
        self,
        event_type: NativeEventType,
        message: int,
    ) -> bool:
        """Leave an event available to Qt until a later raw-input handler reads it.

        Args:
            event_type: Runtime-specific native event category supplied by Qt.
            message: Address of the platform-native event structure.

        Returns:
            False so Qt continues its normal event conversion and delivery.
        """
        del event_type, message
        return False
