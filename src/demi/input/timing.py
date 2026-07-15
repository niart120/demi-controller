"""Input evaluation interval metrics without a GUI or runtime dependency."""

from collections import deque
from dataclasses import dataclass
from math import ceil


@dataclass(frozen=True, slots=True)
class InputTimingSnapshot:
    """Summarize observed input evaluation intervals.

    Attributes:
        sample_count: Number of positive evaluation intervals retained.
        mean_interval_ms: Arithmetic mean of retained intervals, or ``None``
            before a second evaluation.
        p95_interval_ms: Nearest-rank 95th percentile, or ``None`` without
            an interval sample.
        p99_interval_ms: Nearest-rank 99th percentile, or ``None`` without
            an interval sample.
    """

    sample_count: int
    mean_interval_ms: float | None
    p95_interval_ms: float | None
    p99_interval_ms: float | None


class InputEvaluationMetrics:
    """Retain a bounded sample of input evaluation intervals."""

    def __init__(self, *, max_samples: int = 512) -> None:
        """Create an empty metrics collector.

        Args:
            max_samples: Maximum recent intervals retained for percentile
                calculation.

        Raises:
            ValueError: The requested sample capacity is not positive.
        """
        if isinstance(max_samples, bool) or not isinstance(max_samples, int) or max_samples <= 0:
            raise ValueError
        self._intervals_ns: deque[int] = deque(maxlen=max_samples)
        self._last_monotonic_ns: int | None = None

    @property
    def snapshot(self) -> InputTimingSnapshot:
        """Return a value snapshot of the currently retained intervals."""
        intervals_ns = tuple(self._intervals_ns)
        if not intervals_ns:
            return InputTimingSnapshot(
                sample_count=0,
                mean_interval_ms=None,
                p95_interval_ms=None,
                p99_interval_ms=None,
            )
        sorted_intervals = tuple(sorted(intervals_ns))
        return InputTimingSnapshot(
            sample_count=len(intervals_ns),
            mean_interval_ms=sum(intervals_ns) / len(intervals_ns) / 1_000_000,
            p95_interval_ms=self._percentile_ms(sorted_intervals, 0.95),
            p99_interval_ms=self._percentile_ms(sorted_intervals, 0.99),
        )

    def note_evaluation(self, monotonic_ns: int) -> None:
        """Record one evaluation timestamp when it advances monotonically.

        Args:
            monotonic_ns: Timestamp sampled at the input evaluation boundary.

        Raises:
            ValueError: The timestamp is not a nonnegative integer.
        """
        if isinstance(monotonic_ns, bool) or not isinstance(monotonic_ns, int) or monotonic_ns < 0:
            raise ValueError
        last_monotonic_ns = self._last_monotonic_ns
        if last_monotonic_ns is None:
            self._last_monotonic_ns = monotonic_ns
            return
        interval_ns = monotonic_ns - last_monotonic_ns
        if interval_ns <= 0:
            return
        self._intervals_ns.append(interval_ns)
        self._last_monotonic_ns = monotonic_ns

    @staticmethod
    def _percentile_ms(intervals_ns: tuple[int, ...], percentile: float) -> float:
        """Return a nearest-rank percentile from sorted interval samples."""
        rank = max(0, ceil(len(intervals_ns) * percentile) - 1)
        return intervals_ns[rank] / 1_000_000
