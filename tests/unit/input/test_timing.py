from demi.input.timing import InputEvaluationMetrics


def test_input_evaluation_metrics_report_mean_and_high_percentiles() -> None:
    metrics = InputEvaluationMetrics()

    now_ns = 1_000_000_000
    metrics.note_evaluation(now_ns)
    for interval_ms in (8, 8, 16, 8, 8):
        now_ns += interval_ms * 1_000_000
        metrics.note_evaluation(now_ns)

    snapshot = metrics.snapshot

    assert snapshot.sample_count == 5
    assert snapshot.mean_interval_ms == 9.6
    assert snapshot.p95_interval_ms == 16.0
    assert snapshot.p99_interval_ms == 16.0


def test_input_evaluation_metrics_ignore_nonpositive_clock_deltas() -> None:
    metrics = InputEvaluationMetrics()

    metrics.note_evaluation(1_000_000_000)
    metrics.note_evaluation(1_008_000_000)
    metrics.note_evaluation(1_008_000_000)
    metrics.note_evaluation(1_006_000_000)

    assert metrics.snapshot.sample_count == 1
