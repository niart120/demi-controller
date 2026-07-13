from dataclasses import dataclass, field

from PySide6.QtCore import Qt, QTimer

from demi.app import WindowSpec
from demi.application.coordinator import CaptureCoordinator
from demi.application.frame_fanout import ControllerFrameFanout
from demi.domain.controller import ControllerFrame
from demi.input.publisher import InputPublisher
from demi.platform.windows_raw_input import RawInputDevice, WindowsRawInputBackend
from demi.ui.main_window import MainWindow


@dataclass
class FakeClock:
    """Provide deterministic timestamps for scheduled input evaluation."""

    now_ns: int = 1_000_000_000

    def monotonic_ns(self) -> int:
        """Return the current test timestamp."""
        return self.now_ns


@dataclass
class RecordingRuntime:
    """Observe the exact frames offered to the controller runtime boundary."""

    frames: list[ControllerFrame] = field(default_factory=list)

    def offer_frame(self, frame: ControllerFrame) -> bool:
        """Store one frame and accept it."""
        self.frames.append(frame)
        return True


@dataclass
class FakeRawInputRegistrar:
    """Avoid platform registration while exercising the main-window lifecycle."""

    devices: list[RawInputDevice] = field(default_factory=list)

    def register(self, device: RawInputDevice) -> None:
        """Record one logical registration."""
        self.devices.append(device)


def test_precise_evaluation_timer_fans_out_the_same_frame_to_runtime_and_preview(
    qt_application: object,
) -> None:
    assert qt_application is not None
    clock = FakeClock()
    runtime = RecordingRuntime()
    window = MainWindow(WindowSpec(width=960, height=640, maximized=False))
    publisher = InputPublisher(
        clock=clock,
        sink=ControllerFrameFanout(runtime=runtime, preview=window),
    )
    coordinator = CaptureCoordinator(
        publisher=publisher,
        pointer_capture=window,
        relative_pointer_capture=window,
    )
    window.configure_input(
        publisher=publisher,
        coordinator=coordinator,
        raw_input_backend=WindowsRawInputBackend(registrar=FakeRawInputRegistrar()),
    )

    assert window.input_evaluation_interval_ms == 8
    assert window.input_evaluation_timer_type is Qt.TimerType.PreciseTimer
    assert coordinator.start_capture() is True
    runtime.frames.clear()
    clock.now_ns += 8_000_000
    timer = window.findChild(QTimer)
    assert timer is not None
    assert timer.isActive() is True

    timer.timeout.emit()

    frame = runtime.frames[0]
    assert runtime.frames == [frame]
    assert window.last_frame is frame
    assert runtime.frames[0] is window.last_frame
    coordinator.begin_shutdown()
