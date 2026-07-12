from dataclasses import dataclass, field

from demi.domain.controller import AccelG, ControllerFrame, GyroRate, LogicalButton, StickVector
from demi.input.publisher import InputPublisher


@dataclass
class FakeClock:
    """Deterministic monotonic clock for publisher tests."""

    now_ns: int = 1_000_000_000

    def monotonic_ns(self) -> int:
        """Return the configured fake time."""
        return self.now_ns


@dataclass
class FakeSink:
    """In-memory frame sink for publisher tests."""

    frames: list[ControllerFrame] = field(default_factory=list)

    def offer_frame(self, frame: ControllerFrame) -> None:
        """Store the offered frame."""
        self.frames.append(frame)


def test_publisher_emits_an_initial_neutral_frame_with_sequence_and_epoch() -> None:
    clock = FakeClock()
    sink = FakeSink()
    publisher = InputPublisher(clock=clock, sink=sink)

    frame = publisher.publish(capture_active=True, capture_epoch=4)

    assert frame == sink.frames[0]
    assert frame.sequence == 1
    assert frame.capture_epoch == 4
    assert frame.monotonic_ns == clock.now_ns
    assert frame.buttons == frozenset()
    assert frame.left_stick == StickVector(x=0.0, y=0.0)
    assert frame.right_stick == StickVector(x=0.0, y=0.0)
    assert frame.gyro_rate == GyroRate(0.0, 0.0, 0.0)
    assert frame.accel_g == AccelG(0.0, 0.0, 1.0)


def test_publisher_uses_elapsed_clock_time_and_current_input_state() -> None:
    clock = FakeClock()
    sink = FakeSink()
    publisher = InputPublisher(clock=clock, sink=sink)
    publisher.publish(capture_active=True, capture_epoch=1)
    publisher.state.press_key("F")
    publisher.state.add_mouse_motion(2.0, 0.0)
    clock.now_ns += 10_000_000

    frame = publisher.publish(capture_active=True, capture_epoch=1)

    assert frame.sequence == 2
    assert frame.buttons == frozenset({LogicalButton.A})
    assert frame.gyro_rate.z_radians_per_second < 0.0
    assert frame.accel_g == AccelG(0.0, 0.0, 1.0)


def test_capture_release_emits_neutral_and_clears_held_input() -> None:
    clock = FakeClock()
    sink = FakeSink()
    publisher = InputPublisher(clock=clock, sink=sink)
    publisher.publish(capture_active=True, capture_epoch=2)
    publisher.state.press_key("F")
    publisher.state.add_mouse_motion(5.0, 0.0)

    frame = publisher.publish(capture_active=False, capture_epoch=3)

    assert frame.capture_active is False
    assert frame.buttons == frozenset()
    assert frame.left_stick == StickVector(x=0.0, y=0.0)
    assert frame.gyro_rate == GyroRate(0.0, 0.0, 0.0)
    assert frame.accel_g == AccelG(0.0, 0.0, 1.0)
    assert publisher.state.held_keys == set()
    assert publisher.state.consume_mouse_motion() == (0.0, 0.0)


def test_publisher_exposes_the_eight_millisecond_evaluation_contract() -> None:
    publisher = InputPublisher(clock=FakeClock(), sink=FakeSink())

    assert publisher.evaluation_interval_ms == 8
