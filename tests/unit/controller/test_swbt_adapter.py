import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from swbt import Button, IMUFrame, InputState, Stick

from demi.controller.swbt_adapter import SwbtControllerAdapter
from demi.domain.controller import AccelG, ControllerFrame, GyroRate, LogicalButton, StickVector
from demi.domain.settings import ControllerColorSettings


@dataclass
class RecordingGamepad:
    """Public-gamepad-shaped fake used to observe translated input states."""

    applied_states: list[InputState] = field(default_factory=list)

    async def open(self) -> None:
        """Open the fake gamepad."""

    async def reconnect(self, timeout: float | None = None) -> None:  # noqa: ASYNC109
        """Reconnect the fake gamepad."""
        del timeout

    async def connect(
        self,
        *,
        timeout: float | None = None,  # noqa: ASYNC109
        allow_pairing: bool = False,
    ) -> None:
        """Connect the fake gamepad."""
        del timeout, allow_pairing

    async def apply(self, state: InputState) -> None:
        """Record one complete public input state."""
        self.applied_states.append(state)

    async def close(self, *, neutral: bool = True) -> None:
        """Close the fake gamepad."""
        del neutral


def test_controller_frame_is_converted_to_one_public_input_state() -> None:
    gamepad = RecordingGamepad()

    def gamepad_factory(**kwargs: object) -> RecordingGamepad:
        del kwargs
        return gamepad

    adapter = SwbtControllerAdapter(
        gamepad_factory=gamepad_factory,
        adapter_lister=lambda: (),
    )
    frame = ControllerFrame(
        sequence=1,
        capture_epoch=1,
        monotonic_ns=1,
        buttons=frozenset({LogicalButton.A, LogicalButton.ZR}),
        left_stick=StickVector(x=-1.0, y=0.25),
        right_stick=StickVector(x=0.5, y=-1.0),
        gyro_rate=GyroRate(1.0, -2.0, 3.0),
        accel_g=AccelG(0.25, -0.5, 0.75),
        capture_active=True,
    )

    async def exercise() -> None:
        await adapter.connect_saved(
            "usb:0",
            Path("bond.json"),
            30.0,
            ControllerColorSettings(),
        )
        await adapter.apply_frame(frame)

    asyncio.run(exercise())

    assert len(gamepad.applied_states) == 1
    state = gamepad.applied_states[0]
    assert state.buttons == frozenset({Button.A, Button.ZR})
    assert state.left_stick == Stick.normalized(x=-1.0, y=0.25)
    assert state.right_stick == Stick.normalized(x=0.5, y=-1.0)
    expected_imu = IMUFrame.gyro_rate(
        x_rad_s=1.0,
        y_rad_s=-2.0,
        z_rad_s=3.0,
    ).with_accel_g(x_g=0.25, y_g=-0.5, z_g=0.75)
    assert state.imu_frames == (expected_imu, expected_imu, expected_imu)


def test_neutral_frame_uses_one_g_acceleration_in_all_three_imu_slots() -> None:
    gamepad = RecordingGamepad()

    def gamepad_factory(**kwargs: object) -> RecordingGamepad:
        del kwargs
        return gamepad

    adapter = SwbtControllerAdapter(
        gamepad_factory=gamepad_factory,
        adapter_lister=lambda: (),
    )
    neutral_frame = ControllerFrame(
        sequence=2,
        capture_epoch=1,
        monotonic_ns=2,
        buttons=frozenset(),
        left_stick=StickVector(x=0.0, y=0.0),
        right_stick=StickVector(x=0.0, y=0.0),
        gyro_rate=GyroRate(0.0, 0.0, 0.0),
        accel_g=AccelG(0.0, 0.0, 1.0),
        capture_active=False,
    )

    async def exercise() -> None:
        await adapter.connect_saved(
            "usb:0",
            Path("bond.json"),
            30.0,
            ControllerColorSettings(),
        )
        await adapter.apply_frame(neutral_frame)

    asyncio.run(exercise())

    state = gamepad.applied_states[0]
    expected_imu = IMUFrame.gyro_rate().with_accel_g(x_g=0.0, y_g=0.0, z_g=1.0)
    assert state.buttons == frozenset()
    assert state.left_stick == Stick.center()
    assert state.right_stick == Stick.center()
    assert state.imu_frames == (expected_imu, expected_imu, expected_imu)
    assert state.imu_frames != InputState.neutral().imu_frames
