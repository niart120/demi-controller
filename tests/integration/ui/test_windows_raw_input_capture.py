import asyncio
from dataclasses import dataclass, field
from math import cos, hypot, radians, sin
from pathlib import Path

import pytest
from PySide6.QtCore import QByteArray
from swbt import InputState

from demi.app import ApplicationSession
from demi.application.coordinator import CaptureCoordinator
from demi.application.state import AppState
from demi.config.paths import SettingsPaths
from demi.config.repository import SettingsLoadResult, SettingsLoadStatus
from demi.controller.swbt_adapter import SwbtControllerAdapter, frame_to_input_state
from demi.domain.controller import ControllerFrame
from demi.domain.settings import AppSettings, ControllerColorSettings, MouseSettings
from demi.input.mouse_rotation_mapper import BASE_YAW_RADIANS_PER_INPUT_UNIT
from demi.input.publisher import InputPublisher
from demi.platform.windows_raw_input import (
    MOUSE_MOVE_ABSOLUTE,
    WM_INPUT,
    NativeWindowsMessage,
    RawInputDevice,
    RawMousePacket,
    WindowsRawInputBackend,
)


@dataclass
class FakeClock:
    """Provide deterministic input evaluation times."""

    now_ns: int = 1_000_000_000

    def monotonic_ns(self) -> int:
        """Return the configured monotonic timestamp."""
        return self.now_ns


@dataclass
class RecordingFrameSink:
    """Store frames produced by the integration boundary."""

    frames: list[ControllerFrame] = field(default_factory=list)

    def offer_frame(self, frame: ControllerFrame) -> None:
        """Store one evaluated frame."""
        self.frames.append(frame)


@dataclass
class RecordingGamepad:
    """Record complete swbt states without opening Bluetooth hardware."""

    applied_states: list[InputState] = field(default_factory=list)

    async def open(self) -> None:
        """Accept the transport-open boundary."""

    async def reconnect(self, timeout: float | None = None) -> None:  # noqa: ASYNC109
        """Accept a saved-bond reconnect without hardware."""
        del timeout

    async def connect(
        self,
        *,
        timeout: float | None = None,  # noqa: ASYNC109
        allow_pairing: bool = False,
    ) -> None:
        """Accept an explicit connection without hardware."""
        del timeout, allow_pairing

    async def apply(self, state: InputState) -> None:
        """Record one complete state passed to the public swbt boundary."""
        self.applied_states.append(state)

    async def close(self, *, neutral: bool = True) -> None:
        """Accept transport cleanup without hardware."""
        del neutral


@dataclass
class FakeRawInputRegistrar:
    """Accept registrations without invoking the Windows API."""

    devices: list[RawInputDevice] = field(default_factory=list)

    def register(self, device: RawInputDevice) -> None:
        """Record one logical raw-input device selection."""
        self.devices.append(device)


@dataclass
class FakeNativeMessageReader:
    """Translate fixture addresses into native message values."""

    messages: dict[int, NativeWindowsMessage]

    def read(self, message_address: int) -> NativeWindowsMessage:
        """Return the native message represented by an address fixture."""
        return self.messages[message_address]


@dataclass
class FakeRawInputReader:
    """Translate raw-input handles into decoded mouse packets."""

    packets: dict[int, RawMousePacket]

    def read_mouse(self, raw_input_handle: int) -> RawMousePacket | None:
        """Return the decoded packet represented by a handle fixture."""
        return self.packets[raw_input_handle]


@dataclass
class FakePointerCapture:
    """Record capture visibility changes without using Qt."""

    calls: list[bool] = field(default_factory=list)

    def set_pointer_capture(self, enabled: bool) -> None:
        """Record one pointer capture transition."""
        self.calls.append(enabled)


@dataclass
class FailingRelativePointerCapture:
    """Fail raw-input registration with an unsafe native detail."""

    start_epochs: list[int] = field(default_factory=list)
    stop_calls: int = 0

    def start_relative_pointer_capture(self, capture_epoch: int) -> None:
        """Record then reject registration."""
        self.start_epochs.append(capture_epoch)
        raise OSError("HRAWINPUT=0xC0FFEE")

    def stop_relative_pointer_capture(self) -> None:
        """Record cleanup of a partially-started registration."""
        self.stop_calls += 1


@dataclass
class FakeRuntime:
    """Satisfy the application session's ordered runtime boundary."""

    frames: list[ControllerFrame] = field(default_factory=list)

    def start(self) -> None:
        """Accept worker startup without side effects."""

    def post(self, command: object) -> None:
        """Accept one runtime command without executing it."""
        del command

    def offer_frame(self, frame: ControllerFrame) -> bool:
        """Record a controller frame."""
        self.frames.append(frame)
        return True

    def close(self) -> None:
        """Accept orderly runtime shutdown."""


@dataclass
class FakeRepository:
    """Provide the settings boundary required by one application session."""

    settings: AppSettings

    def load(self) -> SettingsLoadResult:
        """Return the configured settings as an ordinary loaded result."""
        return SettingsLoadResult(self.settings, SettingsLoadStatus.LOADED)

    def save(self, settings: AppSettings) -> None:
        """Accept a settings save without touching the filesystem."""
        self.settings = settings


@dataclass
class FailingRawInputReader:
    """Raise a native-style read error for every raw-input packet."""

    calls: int = 0

    def read_mouse(self, raw_input_handle: int) -> RawMousePacket | None:
        """Reject the handle without exposing its detail through the UI."""
        self.calls += 1
        raise OSError(f"HRAWINPUT=0x{raw_input_handle:X}")


@dataclass
class BackendRelativePointerCapture:
    """Adapt one Windows backend to the coordinator's relative-capture port."""

    backend: WindowsRawInputBackend
    target_window_handle: int = 0x1234
    start_epochs: list[int] = field(default_factory=list)
    stop_calls: int = 0

    def start_relative_pointer_capture(self, capture_epoch: int) -> None:
        """Register the backend for one capture epoch."""
        self.start_epochs.append(capture_epoch)
        self.backend.start_capture(self.target_window_handle, capture_epoch=capture_epoch)

    def stop_relative_pointer_capture(self) -> None:
        """Remove the backend registration after capture ends."""
        self.stop_calls += 1
        self.backend.stop_capture()


def _session_for(coordinator: CaptureCoordinator) -> ApplicationSession:
    settings = AppSettings.default()
    session = ApplicationSession(
        settings=settings,
        paths=SettingsPaths(Path("config"), Path("data"), Path("log")),
        repository=FakeRepository(settings),
        runtime=FakeRuntime(),
        coordinator=coordinator,
    )
    coordinator.set_capture_failure_reporter(session.report_capture_failure)
    return session


def test_absolute_outside_stale_and_other_window_raw_events_do_not_reach_a_frame() -> None:
    clock = FakeClock()
    publisher = InputPublisher(clock=clock, sink=RecordingFrameSink())
    expected_clock = FakeClock()
    expected_publisher = InputPublisher(clock=expected_clock, sink=RecordingFrameSink())
    messages = FakeNativeMessageReader(
        {
            1: NativeWindowsMessage(message=WM_INPUT, l_param=101, window_handle=0x1234),
            2: NativeWindowsMessage(message=WM_INPUT, l_param=102, window_handle=0x1234),
            3: NativeWindowsMessage(message=WM_INPUT, l_param=103, window_handle=0x9876),
            4: NativeWindowsMessage(message=WM_INPUT, l_param=104, window_handle=0x1234),
        }
    )
    packets = FakeRawInputReader(
        {
            101: RawMousePacket(flags=0, dx=4, dy=-2),
            102: RawMousePacket(flags=MOUSE_MOVE_ABSOLUTE, dx=500, dy=500),
            103: RawMousePacket(flags=0, dx=300, dy=300),
            104: RawMousePacket(flags=0, dx=200, dy=200),
        }
    )
    outside_capture = WindowsRawInputBackend(
        registrar=FakeRawInputRegistrar(),
        on_relative_motion=publisher.state.add_mouse_motion,
        message_reader=messages,
        raw_input_reader=packets,
    )
    active_capture = WindowsRawInputBackend(
        registrar=FakeRawInputRegistrar(),
        on_relative_motion=publisher.state.add_mouse_motion,
        message_reader=messages,
        raw_input_reader=packets,
    )

    publisher.publish(capture_active=True, capture_epoch=2)
    expected_publisher.publish(capture_active=True, capture_epoch=2)
    expected_publisher.state.add_mouse_motion(4.0, -2.0)

    assert (
        outside_capture.handle_native_event(
            QByteArray(b"windows_generic_MSG"),
            1,
            capture_epoch=2,
        )
        is False
    )

    active_capture.start_capture(0x1234, capture_epoch=2)
    assert active_capture.nativeEventFilter(QByteArray(b"windows_generic_MSG"), 1) is False
    assert (
        active_capture.handle_native_event(
            QByteArray(b"windows_generic_MSG"),
            2,
            capture_epoch=2,
        )
        is False
    )
    assert (
        active_capture.handle_native_event(
            QByteArray(b"windows_generic_MSG"),
            3,
            capture_epoch=2,
        )
        is False
    )
    assert (
        active_capture.handle_native_event(
            QByteArray(b"windows_generic_MSG"),
            4,
            capture_epoch=1,
        )
        is False
    )

    assert (publisher.state.accumulated_dx, publisher.state.accumulated_dy) == (4.0, -2.0)

    clock.now_ns += 8_000_000
    expected_clock.now_ns += 8_000_000
    frame = publisher.publish(capture_active=True, capture_epoch=2)
    expected_frame = expected_publisher.publish(capture_active=True, capture_epoch=2)

    assert frame == expected_frame
    assert publisher.state.consume_mouse_motion() == (0.0, 0.0)


def test_raw_input_registration_failure_keeps_idle_and_reports_a_safe_warning() -> None:
    publisher = InputPublisher(clock=FakeClock(), sink=RecordingFrameSink())
    pointer_capture = FakePointerCapture()
    relative_pointer_capture = FailingRelativePointerCapture()
    coordinator = CaptureCoordinator(
        publisher=publisher,
        pointer_capture=pointer_capture,
        relative_pointer_capture=relative_pointer_capture,
    )
    session = _session_for(coordinator)

    assert session.toggle_capture() is False

    assert coordinator.app_state is AppState.IDLE
    assert coordinator.capture_epoch == 1
    assert pointer_capture.calls == []
    assert relative_pointer_capture.start_epochs == [1]
    assert relative_pointer_capture.stop_calls == 1
    assert session.presentation.model.warning == "Could not start relative mouse input"
    assert "0xC0FFEE" not in session.presentation.model.warning


def test_repeated_raw_input_read_failures_stop_capture_with_a_safe_warning() -> None:
    publisher = InputPublisher(clock=FakeClock(), sink=RecordingFrameSink())
    pointer_capture = FakePointerCapture()
    coordinator_ref: list[CaptureCoordinator] = []

    def on_read_failure() -> object:
        """Route a repeated backend failure to the active coordinator."""
        return coordinator_ref[0].on_relative_input_read_failure()

    backend = WindowsRawInputBackend(
        registrar=FakeRawInputRegistrar(),
        on_relative_motion=publisher.state.add_mouse_motion,
        message_reader=FakeNativeMessageReader(
            {
                1: NativeWindowsMessage(message=WM_INPUT, l_param=0xCAFE, window_handle=0x1234),
                2: NativeWindowsMessage(message=WM_INPUT, l_param=0xCAFE, window_handle=0x1234),
            }
        ),
        raw_input_reader=FailingRawInputReader(),
        on_read_failure=on_read_failure,
        maximum_consecutive_read_failures=2,
    )
    relative_pointer_capture = BackendRelativePointerCapture(backend)
    coordinator = CaptureCoordinator(
        publisher=publisher,
        pointer_capture=pointer_capture,
        relative_pointer_capture=relative_pointer_capture,
    )
    coordinator_ref.append(coordinator)
    session = _session_for(coordinator)

    assert session.toggle_capture() is True
    publisher.state.add_mouse_motion(1.0, 1.0)

    assert backend.nativeEventFilter(QByteArray(b"windows_generic_MSG"), 1) is False
    assert coordinator.app_state is AppState.CAPTURED
    assert backend.nativeEventFilter(QByteArray(b"windows_generic_MSG"), 2) is False

    assert coordinator.app_state is AppState.IDLE
    assert pointer_capture.calls == [True, False]
    assert relative_pointer_capture.start_epochs == [1]
    assert relative_pointer_capture.stop_calls == 1
    assert publisher.state.consume_mouse_motion() == (0.0, 0.0)
    assert session.presentation.model.warning == "Relative mouse input stopped"
    assert "0xCAFE" not in session.presentation.model.warning


def test_steady_low_speed_raw_mouse_motion_has_no_zero_gyro_gaps() -> None:
    """Reject stop-start gyro output while a slow mouse move remains in progress."""
    clock = FakeClock()
    publisher = InputPublisher(clock=clock, sink=RecordingFrameSink())
    messages = FakeNativeMessageReader(
        {
            index: NativeWindowsMessage(
                message=WM_INPUT,
                l_param=100 + index,
                window_handle=0x1234,
            )
            for index in range(1, 6)
        }
    )
    packets = FakeRawInputReader(
        {100 + index: RawMousePacket(flags=0, dx=1, dy=0) for index in range(1, 6)}
    )
    backend = WindowsRawInputBackend(
        registrar=FakeRawInputRegistrar(),
        on_relative_motion=publisher.state.add_mouse_motion,
        message_reader=messages,
        raw_input_reader=packets,
    )
    backend.start_capture(0x1234, capture_epoch=1)
    publisher.publish(capture_active=True, capture_epoch=1)

    frames: list[ControllerFrame] = []
    for tick in range(1, 10):
        if tick % 2 == 1:
            assert (
                backend.handle_native_event(
                    QByteArray(b"windows_generic_MSG"),
                    (tick + 1) // 2,
                    capture_epoch=1,
                )
                is False
            )
        clock.now_ns += 8_000_000
        frame = publisher.publish(capture_active=True, capture_epoch=1)
        frames.append(frame)

    gamepad = RecordingGamepad()
    adapter = SwbtControllerAdapter(
        gamepad_factory=lambda **_kwargs: gamepad,
        adapter_lister=lambda: (),
    )

    async def apply_frames() -> None:
        await adapter.connect_saved(
            "usb:0",
            Path("bonds/default.json"),
            1.0,
            ControllerColorSettings(),
        )
        for frame in frames:
            await adapter.apply_frame(frame)
        await adapter.close()

    asyncio.run(apply_frames())

    gyro_z_rates = [state.imu_frames[0].to_gyro_rate()[2] for state in gamepad.applied_states]

    assert all(rate < 0.0 for rate in gyro_z_rates), gyro_z_rates
    assert len(set(gyro_z_rates)) == 1, gyro_z_rates
    assert all(
        len({imu.to_gyro_rate()[2] for imu in state.imu_frames}) == 1
        for state in gamepad.applied_states
    )


def test_sparse_raw_mouse_and_keyboard_rotation_reach_limited_three_slot_imu() -> None:
    clock = FakeClock()
    publisher = InputPublisher(
        clock=clock,
        sink=RecordingFrameSink(),
        mouse_settings=MouseSettings(pitch_limit_degrees=10.0),
    )
    messages = FakeNativeMessageReader(
        {
            index: NativeWindowsMessage(
                message=WM_INPUT,
                l_param=500 + index,
                window_handle=0x1234,
            )
            for index in range(1, 4)
        }
    )
    packets = FakeRawInputReader(
        {500 + index: RawMousePacket(flags=0, dx=1, dy=0) for index in range(1, 4)}
    )
    backend = WindowsRawInputBackend(
        registrar=FakeRawInputRegistrar(),
        on_relative_motion=publisher.state.add_mouse_motion,
        message_reader=messages,
        raw_input_reader=packets,
    )
    backend.start_capture(0x1234, capture_epoch=1)
    publisher.publish(capture_active=True, capture_epoch=1)
    publisher.state.press_key("K")

    frames: list[ControllerFrame] = []
    raw_event_index = 0
    for tick in range(1, 26):
        if tick in {1, 3, 5}:
            raw_event_index += 1
            assert (
                backend.handle_native_event(
                    QByteArray(b"windows_generic_MSG"),
                    raw_event_index,
                    capture_epoch=1,
                )
                is False
            )
        clock.now_ns += 8_000_000
        frames.append(publisher.publish(capture_active=True, capture_epoch=1))

    gamepad = RecordingGamepad()
    adapter = SwbtControllerAdapter(
        gamepad_factory=lambda **_kwargs: gamepad,
        adapter_lister=lambda: (),
    )

    async def apply_frames() -> None:
        await adapter.connect_saved(
            "usb:0",
            Path("bonds/default.json"),
            1.0,
            ControllerColorSettings(),
        )
        for frame in frames:
            await adapter.apply_frame(frame)
        await adapter.close()

    asyncio.run(apply_frames())

    converted_imu = [state.imu_frames[0] for state in gamepad.applied_states]
    total_yaw = sum(
        -hypot(gyro_x, gyro_z) * 0.008
        for gyro_x, _gyro_y, gyro_z in (imu.to_gyro_rate() for imu in converted_imu)
        if gyro_z < 0.0
    )
    total_pitch = sum(imu.to_gyro_rate()[1] * 0.008 for imu in converted_imu)
    final_accel = converted_imu[-1].to_accel_g()

    assert total_yaw == pytest.approx(
        -3.0 * BASE_YAW_RADIANS_PER_INPUT_UNIT,
        abs=5e-5,
    )
    assert total_pitch == pytest.approx(radians(10.0), abs=3e-4)
    assert final_accel == pytest.approx(
        (-sin(radians(10.0)), 0.0, cos(radians(10.0))),
        abs=5e-4,
    )
    assert all(
        len({(imu.to_gyro_rate(), imu.to_accel_g()) for imu in state.imu_frames}) == 1
        for state in gamepad.applied_states
    )


def test_windows_timer_catch_up_does_not_overwrite_gyro_motion_with_zero() -> None:
    """Keep the latest gyro state moving after a same-timestamp timer catch-up."""
    clock = FakeClock()
    publisher = InputPublisher(clock=clock, sink=RecordingFrameSink())
    messages = FakeNativeMessageReader(
        {
            index: NativeWindowsMessage(
                message=WM_INPUT,
                l_param=200 + index,
                window_handle=0x1234,
            )
            for index in range(1, 6)
        }
    )
    packets = FakeRawInputReader(
        {200 + index: RawMousePacket(flags=0, dx=1, dy=0) for index in range(1, 6)}
    )
    backend = WindowsRawInputBackend(
        registrar=FakeRawInputRegistrar(),
        on_relative_motion=publisher.state.add_mouse_motion,
        message_reader=messages,
        raw_input_reader=packets,
    )
    backend.start_capture(0x1234, capture_epoch=1)
    publisher.publish(capture_active=True, capture_epoch=1)

    catch_up_gyro_z_rates: list[float] = []
    for tick in range(1, 6):
        assert (
            backend.handle_native_event(
                QByteArray(b"windows_generic_MSG"),
                tick,
                capture_epoch=1,
            )
            is False
        )
        clock.now_ns += 16_000_000
        publisher.publish(capture_active=True, capture_epoch=1)
        catch_up_frame = publisher.publish(capture_active=True, capture_epoch=1)
        converted = frame_to_input_state(catch_up_frame)
        catch_up_gyro_z_rates.append(converted.imu_frames[0].to_gyro_rate()[2])

    assert all(rate < 0.0 for rate in catch_up_gyro_z_rates), catch_up_gyro_z_rates
    assert len(set(catch_up_gyro_z_rates)) == 1, catch_up_gyro_z_rates
