from dataclasses import dataclass

from demi.controller.watchdog import FrameWatchdog
from demi.domain.controller import AccelG, ControllerFrame, GyroRate, StickVector


@dataclass
class FakeClock:
    """Monotonic clock controlled by the watchdog test."""

    now_ns: int = 1_000_000_000

    def monotonic_ns(self) -> int:
        """Return the current fake timestamp."""
        return self.now_ns


def make_frame(*, sequence: int, epoch: int, active: bool) -> ControllerFrame:
    """Build a valid frame for watchdog input."""
    return ControllerFrame(
        sequence=sequence,
        capture_epoch=epoch,
        monotonic_ns=sequence,
        buttons=frozenset(),
        left_stick=StickVector(x=0.0, y=0.0),
        right_stick=StickVector(x=0.0, y=0.0),
        gyro_rate=GyroRate(0.0, 0.0, 0.0),
        accel_g=AccelG(0.0, 0.0, 1.0),
        capture_active=active,
    )


def test_watchdog_ignores_before_250ms_and_trips_once_at_threshold() -> None:
    clock = FakeClock()
    watchdog = FrameWatchdog(clock=clock)
    watchdog.set_connected(True)
    watchdog.note_frame(make_frame(sequence=1, epoch=4, active=True))

    clock.now_ns += 199_000_000
    assert watchdog.check() is False
    clock.now_ns += 51_000_000
    assert watchdog.check() is True
    assert watchdog.check() is False


def test_watchdog_requires_connected_capture_and_resets_for_a_new_epoch() -> None:
    clock = FakeClock()
    watchdog = FrameWatchdog(clock=clock)
    watchdog.note_frame(make_frame(sequence=1, epoch=1, active=True))
    clock.now_ns += 300_000_000
    assert watchdog.check() is False

    watchdog.set_connected(True)
    watchdog.note_frame(make_frame(sequence=2, epoch=1, active=False))
    clock.now_ns += 300_000_000
    assert watchdog.check() is False

    watchdog.note_frame(make_frame(sequence=3, epoch=2, active=True))
    clock.now_ns += 250_000_000
    assert watchdog.check() is True
