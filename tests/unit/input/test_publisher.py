from dataclasses import dataclass, field

import pytest

from demi.domain.controller import AccelG, ControllerFrame, GyroRate, LogicalButton, StickVector
from demi.domain.mapping import default_profile
from demi.domain.settings import MouseSettings
from demi.input.publisher import InputPublisher
from demi.input.yaw_pitch_model import BASE_YAW_RADIANS_PER_INPUT_UNIT


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


def test_publisher_exposes_recent_input_evaluation_metrics() -> None:
    clock = FakeClock()
    publisher = InputPublisher(clock=clock, sink=FakeSink())

    publisher.publish(capture_active=False, capture_epoch=1)
    for interval_ms in (8, 8, 16, 8, 8):
        clock.now_ns += interval_ms * 1_000_000
        publisher.publish(capture_active=False, capture_epoch=1)

    metrics = publisher.timing_metrics

    assert metrics.sample_count == 5
    assert metrics.mean_interval_ms == 9.6
    assert metrics.p95_interval_ms == 16.0
    assert metrics.p99_interval_ms == 16.0


def test_publisher_preserves_constant_gyro_rate_across_irregular_intervals() -> None:
    clock = FakeClock()
    publisher = InputPublisher(clock=clock, sink=FakeSink())
    publisher.publish(capture_active=True, capture_epoch=1)
    mouse_units_per_second = 500.0
    gyro_z_rates: list[float] = []

    for interval_ms in (4, 8, 16, 12, 5):
        publisher.state.add_mouse_motion(
            mouse_units_per_second * interval_ms / 1_000,
            0.0,
        )
        clock.now_ns += interval_ms * 1_000_000
        frame = publisher.publish(capture_active=True, capture_epoch=1)
        gyro_z_rates.append(frame.gyro_rate.z_radians_per_second)

    assert gyro_z_rates[0] < 0.0
    assert gyro_z_rates == pytest.approx([gyro_z_rates[0]] * len(gyro_z_rates))


def test_publisher_smooths_sparse_mouse_counts_without_changing_total_rotation() -> None:
    clock = FakeClock()
    publisher = InputPublisher(clock=clock, sink=FakeSink())
    publisher.publish(capture_active=True, capture_epoch=1)
    interval_seconds = 0.008
    gyro_z_rates: list[float] = []

    for dx in (1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 0.0):
        publisher.state.add_mouse_motion(dx, 0.0)
        clock.now_ns += 8_000_000
        frame = publisher.publish(capture_active=True, capture_epoch=1)
        gyro_z_rates.append(frame.gyro_rate.z_radians_per_second)

    assert all(rate < 0.0 for rate in gyro_z_rates[:-1]), gyro_z_rates
    assert gyro_z_rates[-1] == 0.0
    assert sum(rate * interval_seconds for rate in gyro_z_rates) == pytest.approx(
        -3 * BASE_YAW_RADIANS_PER_INPUT_UNIT
    )


def test_publisher_reconfigures_input_settings_and_resets_held_state() -> None:
    clock = FakeClock()
    publisher = InputPublisher(clock=clock, sink=FakeSink())
    publisher.state.press_key("F")
    publisher.reconfigure(
        profile=default_profile(),
        mouse_settings=MouseSettings(gyro_enabled=False),
        circular_limit=True,
        evaluation_interval_ms=16,
    )

    frame = publisher.publish(capture_active=True, capture_epoch=1)

    assert publisher.evaluation_interval_ms == 16
    assert frame.buttons == frozenset()
    assert frame.gyro_rate == GyroRate(0.0, 0.0, 0.0)
