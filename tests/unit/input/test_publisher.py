from dataclasses import dataclass, field
from math import cos, radians, sin

import pytest

from demi.domain.controller import AccelG, ControllerFrame, GyroRate, LogicalButton, StickVector
from demi.domain.mapping import Binding, BindingTarget, InputProfile, default_profile
from demi.domain.settings import MouseSettings
from demi.input.mouse_rotation_mapper import (
    BASE_PITCH_RADIANS_PER_INPUT_UNIT,
    BASE_YAW_RADIANS_PER_INPUT_UNIT,
)
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
    assert frame.sample_duration_ns == 10_000_000
    assert frame.buttons == frozenset({LogicalButton.A})
    assert frame.gyro_rate.z_radians_per_second < 0.0
    assert frame.accel_g == AccelG(0.0, 0.0, 1.0)


def test_publisher_records_zero_boundary_time_and_configured_catch_up_time() -> None:
    clock = FakeClock()
    publisher = InputPublisher(clock=clock, sink=FakeSink(), evaluation_interval_ms=16)

    initial = publisher.publish(capture_active=True, capture_epoch=1)
    catch_up = publisher.publish(capture_active=True, capture_epoch=1)
    epoch_boundary = publisher.publish(capture_active=True, capture_epoch=2)

    assert initial.sample_duration_ns == 0
    assert catch_up.sample_duration_ns == 16_000_000
    assert epoch_boundary.sample_duration_ns == 0


def test_operational_keyboard_is_evaluated_while_pointer_capture_is_inactive() -> None:
    clock = FakeClock()
    sink = FakeSink()
    publisher = InputPublisher(clock=clock, sink=sink)
    publisher.publish(capture_active=True, pointer_capture_active=False, capture_epoch=1)
    publisher.state.press_key("F")
    publisher.state.press_mouse_button("LEFT")
    publisher.state.add_mouse_motion(2.0, 0.0)
    clock.now_ns += 10_000_000

    frame = publisher.publish(
        capture_active=True,
        pointer_capture_active=False,
        capture_epoch=1,
    )

    assert frame.buttons == frozenset({LogicalButton.A})
    assert frame.gyro_rate == GyroRate(0.0, 0.0, 0.0)
    assert frame.accel_g == AccelG(0.0, 0.0, 1.0)


def test_f12_is_evaluated_as_a_regular_keyboard_binding() -> None:
    profile = InputProfile(
        id="f12",
        name="F12",
        builtin=False,
        bindings=(Binding(source="KEY:F12", target=BindingTarget.BUTTON_A),),
    )
    publisher = InputPublisher(clock=FakeClock(), sink=FakeSink(), profile=profile)
    publisher.state.press_key("F12")

    frame = publisher.publish(
        capture_active=True,
        pointer_capture_active=False,
        capture_epoch=0,
    )

    assert frame.buttons == frozenset({LogicalButton.A})


@pytest.mark.parametrize(
    ("symbol", "target", "expected_gyro"),
    [
        ("U", BindingTarget.GYRO_Y_NEGATIVE, GyroRate(0.0, -1.0, 0.0)),
        ("N", BindingTarget.GYRO_Y_POSITIVE, GyroRate(0.0, 1.0, 0.0)),
        ("H", BindingTarget.GYRO_Z_POSITIVE, GyroRate(0.0, 0.0, 1.0)),
        ("M", BindingTarget.GYRO_Z_NEGATIVE, GyroRate(0.0, 0.0, -1.0)),
    ],
)
def test_profile_diagnostic_keys_emit_constant_gyro_without_regular_mapping(
    symbol: str,
    target: BindingTarget,
    expected_gyro: GyroRate,
) -> None:
    clock = FakeClock()
    conflicting_profile = InputProfile(
        id="conflicting",
        name="Conflicting",
        builtin=False,
        bindings=(
            Binding(f"KEY:{symbol}", target),
            Binding(f"KEY:{symbol}", BindingTarget.RIGHT_STICK_UP),
            Binding(f"KEY:{symbol}", BindingTarget.BUTTON_A),
        ),
    )
    publisher = InputPublisher(
        clock=clock,
        sink=FakeSink(),
        profile=conflicting_profile,
        mouse_settings=MouseSettings(gyro_enabled=False),
    )
    publisher.publish(capture_active=True, capture_epoch=1)
    publisher.state.press_key(symbol)

    for interval_ms in (4, 16):
        clock.now_ns += interval_ms * 1_000_000
        frame = publisher.publish(capture_active=True, capture_epoch=1)

        assert frame.gyro_rate == expected_gyro
        assert frame.buttons == frozenset()
        assert frame.right_stick == StickVector(x=0.0, y=0.0)


def test_pointer_epoch_preserves_opposed_ijkl_keys_without_residual_gyro() -> None:
    clock = FakeClock()
    publisher = InputPublisher(
        clock=clock,
        sink=FakeSink(),
        mouse_settings=MouseSettings(gyro_enabled=False),
    )
    publisher.publish(capture_active=True, capture_epoch=1)
    for symbol in ("I", "K", "J", "L"):
        publisher.state.press_key(symbol)
    clock.now_ns += 8_000_000

    cancelled = publisher.publish(capture_active=True, capture_epoch=1)

    assert cancelled.gyro_rate == GyroRate(0.0, 0.0, 0.0)
    assert cancelled.right_stick == StickVector(x=0.0, y=0.0)

    publisher.state.release_key("K")
    publisher.state.release_key("L")
    clock.now_ns += 8_000_000
    remaining = publisher.publish(capture_active=True, capture_epoch=1)

    assert remaining.gyro_rate.x_radians_per_second == pytest.approx(sin(0.004))
    assert remaining.gyro_rate.y_radians_per_second == -1.0
    assert remaining.gyro_rate.z_radians_per_second == pytest.approx(cos(0.004))

    epoch_reset = publisher.publish(capture_active=True, capture_epoch=2)

    assert epoch_reset.gyro_rate == GyroRate(0.0, 0.0, 0.0)
    assert {source.symbol for source in publisher.state.held_keys} == {"I", "J"}

    publisher.state.press_key("I")
    released = publisher.publish(capture_active=False, capture_epoch=3)

    assert released.gyro_rate == GyroRate(0.0, 0.0, 0.0)
    assert publisher.state.held_keys == set()


def test_keyboard_pitch_gyro_updates_pose_consistent_acceleration() -> None:
    clock = FakeClock()
    publisher = InputPublisher(
        clock=clock,
        sink=FakeSink(),
        mouse_settings=MouseSettings(gyro_enabled=False),
    )
    publisher.publish(capture_active=True, capture_epoch=1)
    publisher.state.press_key("I")
    clock.now_ns += 250_000_000

    frame = publisher.publish(capture_active=True, capture_epoch=1)

    expected_pitch = -0.25
    assert frame.gyro_rate == GyroRate(0.0, -1.0, 0.0)
    assert frame.accel_g.x_g == pytest.approx(-sin(expected_pitch))
    assert frame.accel_g.y_g == 0.0
    assert frame.accel_g.z_g == pytest.approx(cos(expected_pitch))


def test_keyboard_pitch_pose_persists_after_release_and_projects_yaw_keys() -> None:
    clock = FakeClock()
    publisher = InputPublisher(
        clock=clock,
        sink=FakeSink(),
        mouse_settings=MouseSettings(gyro_enabled=False),
    )
    publisher.publish(capture_active=True, capture_epoch=1)
    publisher.state.press_key("K")
    clock.now_ns += 100_000_000
    moving = publisher.publish(capture_active=True, capture_epoch=1)

    publisher.state.release_key("K")
    clock.now_ns += 100_000_000
    released = publisher.publish(capture_active=True, capture_epoch=1)
    publisher.state.press_key("J")
    clock.now_ns += 100_000_000
    yaw_only = publisher.publish(capture_active=True, capture_epoch=1)

    assert moving.accel_g.x_g == pytest.approx(-sin(0.1))
    assert moving.accel_g.z_g == pytest.approx(cos(0.1))
    assert released.gyro_rate == GyroRate(0.0, 0.0, 0.0)
    assert released.accel_g == moving.accel_g
    assert yaw_only.gyro_rate.x_radians_per_second == pytest.approx(-sin(0.1))
    assert yaw_only.gyro_rate.y_radians_per_second == 0.0
    assert yaw_only.gyro_rate.z_radians_per_second == pytest.approx(cos(0.1))
    assert yaw_only.accel_g == released.accel_g


def test_keyboard_pitch_pose_survives_pointer_epoch_and_resets_when_inactive() -> None:
    clock = FakeClock()
    publisher = InputPublisher(
        clock=clock,
        sink=FakeSink(),
        mouse_settings=MouseSettings(gyro_enabled=False),
    )
    publisher.publish(capture_active=True, capture_epoch=1)
    publisher.state.press_key("K")
    clock.now_ns += 100_000_000
    tilted = publisher.publish(capture_active=True, capture_epoch=1)

    epoch_reset = publisher.publish(capture_active=True, capture_epoch=2)
    publisher.state.press_key("K")
    clock.now_ns += 100_000_000
    publisher.publish(capture_active=True, capture_epoch=2)
    capture_released = publisher.publish(capture_active=False, capture_epoch=3)

    assert tilted.accel_g != AccelG(0.0, 0.0, 1.0)
    assert epoch_reset.accel_g == tilted.accel_g
    assert epoch_reset.gyro_rate == GyroRate(0.0, 0.0, 0.0)
    assert capture_released.accel_g == AccelG(0.0, 0.0, 1.0)
    assert capture_released.gyro_rate == GyroRate(0.0, 0.0, 0.0)


def test_mouse_and_ijkl_rotation_are_combined_before_pose_projection() -> None:
    clock = FakeClock()
    baseline = InputPublisher(clock=clock, sink=FakeSink())
    combined = InputPublisher(clock=clock, sink=FakeSink())
    baseline.publish(capture_active=True, capture_epoch=1)
    combined.publish(capture_active=True, capture_epoch=1)
    baseline.state.add_mouse_motion(2.0, 3.0)
    combined.state.add_mouse_motion(2.0, 3.0)
    combined.state.press_key("I")
    combined.state.press_key("J")
    clock.now_ns += 8_000_000

    mouse_only = baseline.publish(capture_active=True, capture_epoch=1)
    mouse_and_keys = combined.publish(capture_active=True, capture_epoch=1)

    expected_pitch = 1.5 * BASE_PITCH_RADIANS_PER_INPUT_UNIT - 0.008
    expected_yaw = -BASE_YAW_RADIANS_PER_INPUT_UNIT + 0.008
    middle_pitch = expected_pitch * 0.5
    assert mouse_and_keys.gyro_rate.x_radians_per_second == pytest.approx(
        -sin(middle_pitch) * expected_yaw / 0.008
    )
    assert mouse_and_keys.gyro_rate.y_radians_per_second == pytest.approx(expected_pitch / 0.008)
    assert mouse_and_keys.gyro_rate.z_radians_per_second == pytest.approx(
        cos(middle_pitch) * expected_yaw / 0.008
    )
    assert mouse_and_keys.accel_g.x_g == pytest.approx(-sin(expected_pitch))
    assert mouse_and_keys.accel_g.y_g == 0.0
    assert mouse_and_keys.accel_g.z_g == pytest.approx(cos(expected_pitch))
    assert mouse_and_keys.accel_g != mouse_only.accel_g


@pytest.mark.parametrize(
    ("dy", "key"),
    [
        (-2.0, "I"),
        (2.0, "K"),
    ],
)
def test_default_mouse_vertical_direction_matches_ijkl(dy: float, key: str) -> None:
    clock = FakeClock()
    mouse = InputPublisher(clock=clock, sink=FakeSink())
    keyboard = InputPublisher(clock=clock, sink=FakeSink())
    mouse.publish(capture_active=True, capture_epoch=1)
    keyboard.publish(capture_active=True, capture_epoch=1)
    mouse.state.add_mouse_motion(0.0, dy)
    keyboard.state.press_key(key)
    clock.now_ns += 8_000_000

    mouse_frame = mouse.publish(capture_active=True, capture_epoch=1)
    keyboard_frame = keyboard.publish(capture_active=True, capture_epoch=1)

    assert (
        mouse_frame.gyro_rate.y_radians_per_second * keyboard_frame.gyro_rate.y_radians_per_second
        > 0.0
    )


def test_profile_accel_zero_is_temporary_without_resetting_pitch() -> None:
    clock = FakeClock()
    profile = InputProfile(
        id="diagnostic",
        name="Diagnostic",
        builtin=False,
        bindings=(
            Binding("KEY:P", BindingTarget.ACCEL_ZERO),
            Binding("KEY:U", BindingTarget.GYRO_Y_NEGATIVE),
            Binding("KEY:P", BindingTarget.BUTTON_A),
        ),
    )
    publisher = InputPublisher(clock=clock, sink=FakeSink(), profile=profile)
    publisher.publish(capture_active=True, capture_epoch=1)
    publisher.state.add_mouse_motion(0.0, 4.0)
    for _ in range(3):
        clock.now_ns += 8_000_000
        normal = publisher.publish(capture_active=True, capture_epoch=1)

    assert normal.accel_g != AccelG(0.0, 0.0, 1.0)

    publisher.state.press_key("P")
    publisher.state.press_key("U")
    clock.now_ns += 8_000_000
    zero_g = publisher.publish(capture_active=True, capture_epoch=1)

    assert zero_g.accel_g == AccelG(0.0, 0.0, 0.0)
    assert zero_g.gyro_rate == GyroRate(0.0, -1.0, 0.0)
    assert zero_g.buttons == frozenset()

    publisher.state.release_key("P")
    publisher.state.release_key("U")
    clock.now_ns += 8_000_000
    restored = publisher.publish(capture_active=True, capture_epoch=1)

    expected_pitch = 4.0 * BASE_PITCH_RADIANS_PER_INPUT_UNIT - 0.008
    assert restored.accel_g.x_g == pytest.approx(-sin(expected_pitch))
    assert restored.accel_g.y_g == 0.0
    assert restored.accel_g.z_g == pytest.approx(cos(expected_pitch))
    assert restored.gyro_rate == GyroRate(0.0, 0.0, 0.0)

    publisher.state.press_key("P")
    released = publisher.publish(capture_active=False, capture_epoch=2)

    assert released.accel_g == AccelG(0.0, 0.0, 1.0)
    assert publisher.state.held_keys == set()


def test_accel_zero_keeps_updating_the_shared_pitch_limited_pose() -> None:
    clock = FakeClock()
    publisher = InputPublisher(
        clock=clock,
        sink=FakeSink(),
        mouse_settings=MouseSettings(pitch_limit_degrees=10.0),
    )
    publisher.publish(capture_active=True, capture_epoch=1)
    publisher.state.press_key("K")
    publisher.state.press_key("O")
    clock.now_ns += 400_000_000

    zero_g = publisher.publish(capture_active=True, capture_epoch=1)

    assert zero_g.accel_g == AccelG(0.0, 0.0, 0.0)
    assert zero_g.gyro_rate.y_radians_per_second == pytest.approx(radians(10.0) / 0.4)

    publisher.state.release_key("K")
    publisher.state.release_key("O")
    clock.now_ns += 8_000_000
    restored = publisher.publish(capture_active=True, capture_epoch=1)

    assert restored.gyro_rate == GyroRate(0.0, 0.0, 0.0)
    assert restored.accel_g.x_g == pytest.approx(-sin(radians(10.0)))
    assert restored.accel_g.y_g == 0.0
    assert restored.accel_g.z_g == pytest.approx(cos(radians(10.0)))


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

    expected_rate = -mouse_units_per_second * BASE_YAW_RADIANS_PER_INPUT_UNIT
    assert gyro_z_rates[0] == pytest.approx(expected_rate * 0.5)
    assert gyro_z_rates[1:] == pytest.approx([expected_rate] * (len(gyro_z_rates) - 1))


def test_publisher_resamples_sparse_mouse_counts_without_changing_total_rotation() -> None:
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


def test_publisher_preserves_sparse_rotation_across_irregular_intervals() -> None:
    clock = FakeClock()
    publisher = InputPublisher(clock=clock, sink=FakeSink())
    publisher.publish(capture_active=True, capture_epoch=1)
    gyro_z_samples: list[tuple[float, float]] = []

    for dx, interval_ms in ((1.0, 4), (0.0, 16), (1.0, 12), (0.0, 5), (0.0, 8)):
        publisher.state.add_mouse_motion(dx, 0.0)
        clock.now_ns += interval_ms * 1_000_000
        frame = publisher.publish(capture_active=True, capture_epoch=1)
        gyro_z_samples.append((frame.gyro_rate.z_radians_per_second, interval_ms / 1_000))

    assert all(rate < 0.0 for rate, _interval in gyro_z_samples[:-1])
    assert gyro_z_samples[-1][0] == 0.0
    assert sum(rate * interval for rate, interval in gyro_z_samples) == pytest.approx(
        -2 * BASE_YAW_RADIANS_PER_INPUT_UNIT
    )


def test_publisher_does_not_overshoot_rotation_when_mouse_direction_reverses() -> None:
    clock = FakeClock()
    publisher = InputPublisher(clock=clock, sink=FakeSink())
    publisher.publish(capture_active=True, capture_epoch=1)
    emitted_mouse_units: list[float] = []

    for dx, interval_ms in ((1.0, 4), (-1.0, 16), (0.0, 8)):
        publisher.state.add_mouse_motion(dx, 0.0)
        clock.now_ns += interval_ms * 1_000_000
        frame = publisher.publish(capture_active=True, capture_epoch=1)
        emitted_mouse_units.append(
            -frame.gyro_rate.z_radians_per_second
            * (interval_ms / 1_000)
            / BASE_YAW_RADIANS_PER_INPUT_UNIT
        )

    cumulative_mouse_units: list[float] = []
    total_mouse_units = 0.0
    for emitted_mouse_unit in emitted_mouse_units:
        total_mouse_units += emitted_mouse_unit
        cumulative_mouse_units.append(total_mouse_units)

    assert max(cumulative_mouse_units) <= 1.0
    assert cumulative_mouse_units[-1] == pytest.approx(0.0)


def test_publisher_applies_mouse_direction_reversal_without_a_zero_frame() -> None:
    clock = FakeClock()
    publisher = InputPublisher(clock=clock, sink=FakeSink())
    publisher.publish(capture_active=True, capture_epoch=1)

    publisher.state.add_mouse_motion(1.0, 0.0)
    clock.now_ns += 8_000_000
    forward = publisher.publish(capture_active=True, capture_epoch=1)

    publisher.state.add_mouse_motion(-1.0, 0.0)
    clock.now_ns += 8_000_000
    reversed_frame = publisher.publish(capture_active=True, capture_epoch=1)

    assert forward.gyro_rate.z_radians_per_second < 0.0
    assert reversed_frame.gyro_rate.z_radians_per_second > 0.0


def test_capture_boundary_discards_unemitted_resampled_mouse_motion() -> None:
    clock = FakeClock()
    publisher = InputPublisher(clock=clock, sink=FakeSink())
    publisher.publish(capture_active=True, capture_epoch=1)
    publisher.state.add_mouse_motion(1.0, 0.0)
    clock.now_ns += 8_000_000
    moving = publisher.publish(capture_active=True, capture_epoch=1)

    released = publisher.publish(capture_active=False, capture_epoch=2)
    restarted = publisher.publish(capture_active=True, capture_epoch=3)
    clock.now_ns += 8_000_000
    empty_tick = publisher.publish(capture_active=True, capture_epoch=3)

    assert moving.gyro_rate.z_radians_per_second < 0.0
    assert released.gyro_rate == GyroRate(0.0, 0.0, 0.0)
    assert restarted.gyro_rate == GyroRate(0.0, 0.0, 0.0)
    assert empty_tick.gyro_rate == GyroRate(0.0, 0.0, 0.0)


def test_publisher_reconfigures_input_settings_and_resets_held_state() -> None:
    clock = FakeClock()
    publisher = InputPublisher(clock=clock, sink=FakeSink())
    publisher.publish(capture_active=True, capture_epoch=1)
    publisher.state.press_key("K")
    clock.now_ns += 100_000_000
    tilted = publisher.publish(capture_active=True, capture_epoch=1)
    publisher.state.press_key("F")
    publisher.reconfigure(
        profile=default_profile(),
        mouse_settings=MouseSettings(gyro_enabled=False),
        circular_limit=True,
        evaluation_interval_ms=16,
    )

    frame = publisher.publish(capture_active=True, capture_epoch=1)

    assert publisher.evaluation_interval_ms == 16
    assert tilted.accel_g != AccelG(0.0, 0.0, 1.0)
    assert frame.buttons == frozenset()
    assert frame.gyro_rate == GyroRate(0.0, 0.0, 0.0)
    assert frame.accel_g == AccelG(0.0, 0.0, 1.0)
