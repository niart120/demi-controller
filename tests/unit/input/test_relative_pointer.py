from demi.input.relative_pointer import (
    QtRelativePointerBackend,
    RelativeMotion,
    RelativePointerQuality,
)


def test_qt_fallback_reports_accelerated_or_unavailable_without_claiming_raw() -> None:
    fallback = QtRelativePointerBackend(on_relative_motion=lambda motion: motion)
    unavailable = QtRelativePointerBackend(
        on_relative_motion=lambda motion: motion,
        available=False,
    )

    assert fallback.capability.quality is RelativePointerQuality.RELATIVE_ACCELERATED
    assert unavailable.capability.quality is RelativePointerQuality.UNAVAILABLE
    assert fallback.capability.quality is not RelativePointerQuality.RAW_UNACCELERATED
    assert unavailable.capability.quality is not RelativePointerQuality.RAW_UNACCELERATED


def test_qt_fallback_emits_current_epoch_accelerated_delta_only() -> None:
    received: list[RelativeMotion] = []
    backend = QtRelativePointerBackend(on_relative_motion=received.append)

    backend.start_relative_pointer_capture(7)

    assert backend.handle_position(100.0, 80.0, capture_epoch=7) is False
    assert backend.handle_position(102.5, 77.0, capture_epoch=6) is False
    assert backend.handle_position(102.5, 77.0, capture_epoch=7) is True

    assert received == [
        RelativeMotion(
            dx=2.5,
            dy=-3.0,
            quality=RelativePointerQuality.RELATIVE_ACCELERATED,
        )
    ]


def test_unavailable_qt_fallback_does_not_emit_relative_motion() -> None:
    received: list[RelativeMotion] = []
    backend = QtRelativePointerBackend(on_relative_motion=received.append, available=False)

    backend.start_relative_pointer_capture(3)

    assert backend.handle_position(10.0, 10.0, capture_epoch=3) is False
    assert backend.handle_position(12.0, 10.0, capture_epoch=3) is False
    assert received == []
