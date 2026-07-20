import logging

import pytest

from demi.controller.mailbox import LatestFrameMailbox
from demi.domain.controller import AccelG, ControllerFrame, GyroRate, StickVector


def make_frame(
    *,
    sequence: int,
    epoch: int,
    capture_active: bool = True,
    duration_ns: int = 0,
    gyro_z: float = 0.0,
) -> ControllerFrame:
    """Build a minimal valid frame for mailbox tests."""
    return ControllerFrame(
        sequence=sequence,
        capture_epoch=epoch,
        monotonic_ns=sequence,
        buttons=frozenset(),
        left_stick=StickVector(x=0.0, y=0.0),
        right_stick=StickVector(x=0.0, y=0.0),
        gyro_rate=GyroRate(0.0, 0.0, gyro_z),
        accel_g=AccelG(0.0, 0.0, 1.0),
        capture_active=capture_active,
        sample_duration_ns=duration_ns,
    )


def test_mailbox_keeps_only_the_newest_accepted_frame() -> None:
    mailbox = LatestFrameMailbox()
    first = make_frame(sequence=1, epoch=1)
    newest = make_frame(sequence=2, epoch=1)

    assert mailbox.offer(first) is True
    assert mailbox.offer(newest) is True
    assert mailbox.take() == newest
    assert mailbox.take() is None


def test_mailbox_rejects_old_sequence_and_old_epoch() -> None:
    mailbox = LatestFrameMailbox()
    current = make_frame(sequence=5, epoch=2)

    assert mailbox.offer(current) is True
    assert mailbox.offer(make_frame(sequence=5, epoch=2)) is False
    assert mailbox.offer(make_frame(sequence=4, epoch=2)) is False
    assert mailbox.offer(make_frame(sequence=6, epoch=1)) is False
    assert mailbox.peek() == current


def test_mailbox_accepts_a_new_epoch_and_capture_release_frame() -> None:
    mailbox = LatestFrameMailbox()
    active = make_frame(sequence=1, epoch=1)
    released = make_frame(sequence=2, epoch=1, capture_active=False)
    next_capture = make_frame(sequence=3, epoch=2)

    assert mailbox.offer(active) is True
    assert mailbox.offer(released) is True
    assert mailbox.offer(next_capture) is True
    assert mailbox.current_epoch == 2
    assert mailbox.peek() == next_capture


def test_mailbox_coalesces_pending_gyro_angle_while_keeping_latest_state(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="demi.controller.mailbox")
    mailbox = LatestFrameMailbox()
    first = make_frame(sequence=1, epoch=1, duration_ns=4_000_000, gyro_z=3.0)
    newest = make_frame(sequence=2, epoch=1, duration_ns=12_000_000, gyro_z=-1.0)

    assert mailbox.offer(first) is True
    assert mailbox.offer(newest) is True

    sent = mailbox.take()

    assert sent is not None
    assert sent.sequence == 2
    assert sent.sample_duration_ns == 16_000_000
    assert sent.gyro_rate.z_radians_per_second == pytest.approx(0.0)
    assert mailbox.peek() == newest
    assert any(
        "count=2 sequence=1..2 duration_ns=16000000" in message for message in caplog.messages
    )


def test_mailbox_discards_pending_frame_without_losing_latest_view() -> None:
    mailbox = LatestFrameMailbox()
    frame = make_frame(sequence=1, epoch=1, duration_ns=8_000_000, gyro_z=1.0)

    assert mailbox.offer(frame) is True
    assert mailbox.discard_pending(reason="test") is True
    assert mailbox.take() is None
    assert mailbox.peek() == frame
