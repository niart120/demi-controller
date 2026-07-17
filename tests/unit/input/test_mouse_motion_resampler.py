import pytest

from demi.input.mouse_motion_resampler import MouseMotionResampler


def test_constant_motion_preserves_speed_across_irregular_intervals() -> None:
    resampler = MouseMotionResampler()
    emitted_x: list[float] = []

    for interval_ms in (4, 8, 16, 12, 5):
        dt_seconds = interval_ms / 1_000
        dx = 500.0 * dt_seconds
        emitted_dx, emitted_dy = resampler.resample(dx, 0.0, dt_seconds)
        emitted_x.append(emitted_dx)
        assert emitted_dy == 0.0

    assert emitted_x[0] == pytest.approx(1.0)
    assert emitted_x[1:] == pytest.approx([4.0, 8.0, 6.0, 2.5])


def test_sparse_motion_stays_nonzero_and_preserves_total_displacement() -> None:
    resampler = MouseMotionResampler()
    emitted_x = [
        resampler.resample(dx, 0.0, 0.008)[0] for dx in (1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 0.0)
    ]

    assert all(dx > 0.0 for dx in emitted_x[:-1])
    assert emitted_x[-1] == 0.0
    assert sum(emitted_x) == pytest.approx(3.0)


def test_sparse_motion_preserves_displacement_across_irregular_intervals() -> None:
    resampler = MouseMotionResampler()
    emitted_x = [
        resampler.resample(dx, 0.0, interval_ms / 1_000)[0]
        for dx, interval_ms in ((1.0, 4), (0.0, 16), (1.0, 12), (0.0, 5), (0.0, 8))
    ]

    assert all(dx > 0.0 for dx in emitted_x[:-1])
    assert emitted_x[-1] == 0.0
    assert sum(emitted_x) == pytest.approx(2.0)


def test_direction_reversal_is_emitted_without_a_zero_interval() -> None:
    resampler = MouseMotionResampler()

    forward = resampler.resample(1.0, 0.0, 0.008)[0]
    reversed_motion = resampler.resample(-1.0, 0.0, 0.008)[0]

    assert forward > 0.0
    assert reversed_motion < 0.0


def test_direction_reversal_does_not_overshoot_input_displacement() -> None:
    resampler = MouseMotionResampler()
    emitted_x = [
        resampler.resample(dx, 0.0, interval_ms / 1_000)[0]
        for dx, interval_ms in ((1.0, 4), (-1.0, 16), (0.0, 8))
    ]
    cumulative_x: list[float] = []
    total_x = 0.0
    for dx in emitted_x:
        total_x += dx
        cumulative_x.append(total_x)

    assert max(cumulative_x) <= 1.0
    assert cumulative_x[-1] == pytest.approx(0.0)


def test_reset_discards_both_axes_history_and_unemitted_motion() -> None:
    resampler = MouseMotionResampler()
    resampler.resample(1.0, -2.0, 0.004)

    resampler.reset()
    emitted_motion = resampler.resample(0.0, 0.0, 0.008)

    assert emitted_motion == (0.0, 0.0)
