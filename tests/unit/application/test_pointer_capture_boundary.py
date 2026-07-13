from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from demi.application.coordinator import CaptureCoordinator
from demi.input.publisher import InputPublisher

if TYPE_CHECKING:
    from demi.application.coordinator import PointerCapturePort
    from demi.domain.controller import ControllerFrame


@dataclass
class FakeClock:
    """Deterministic clock for pointer capture tests."""

    def monotonic_ns(self) -> int:
        """Return a stable timestamp."""
        return 1_000_000_000


@dataclass
class FakeSink:
    """Frame sink for capture lifecycle tests."""

    frames: list[ControllerFrame] = field(default_factory=list)

    def offer_frame(self, frame: ControllerFrame) -> None:
        """Store one offered frame."""
        self.frames.append(frame)


@dataclass
class FakePointerCapture:
    """Framework-independent pointer capture fake."""

    requests: list[bool] = field(default_factory=list)

    def set_pointer_capture(self, enabled: bool) -> None:
        """Record a capture request."""
        self.requests.append(enabled)


def test_capture_coordinator_depends_on_a_framework_independent_pointer_port() -> None:
    pointer_capture: PointerCapturePort = FakePointerCapture()
    sink = FakeSink()
    coordinator = CaptureCoordinator(
        publisher=InputPublisher(clock=FakeClock(), sink=sink),
        pointer_capture=pointer_capture,
    )

    assert coordinator.start_capture() is True
    assert coordinator.stop_capture() is not None
    assert pointer_capture.requests == [True, False]

    root = Path(__file__).parents[3] / "src" / "demi"
    for directory in (root / "application", root / "domain"):
        for path in directory.rglob("*.py"):
            assert "PySide6" not in path.read_text(encoding="utf-8")
