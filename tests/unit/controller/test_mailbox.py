from demi.controller.mailbox import LatestFrameMailbox
from demi.domain.controller import AccelG, ControllerFrame, GyroRate, StickVector


def make_frame(*, sequence: int, epoch: int, capture_active: bool = True) -> ControllerFrame:
    """Build a minimal valid frame for mailbox tests."""
    return ControllerFrame(
        sequence=sequence,
        capture_epoch=epoch,
        monotonic_ns=sequence,
        buttons=frozenset(),
        left_stick=StickVector(x=0.0, y=0.0),
        right_stick=StickVector(x=0.0, y=0.0),
        gyro_rate=GyroRate(0.0, 0.0, 0.0),
        accel_g=AccelG(0.0, 0.0, 1.0),
        capture_active=capture_active,
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
