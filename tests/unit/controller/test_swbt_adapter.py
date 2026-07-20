import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from swbt import AdapterInfo, Button, ControllerColors, IMUFrame, InputState, Stick

from demi.controller.events import AdapterDescriptor
from demi.controller.swbt_adapter import SwbtControllerAdapter
from demi.domain.controller import AccelG, ControllerFrame, GyroRate, LogicalButton, StickVector
from demi.domain.settings import ControllerColorSettings


@dataclass
class RecordingGamepad:
    """Public-gamepad-shaped fake used to observe translated input states."""

    sent_states: list[InputState] = field(default_factory=list)

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

    async def send(self, state: InputState) -> None:
        """Record one complete public input state."""
        self.sent_states.append(state)

    async def close(self, *, neutral: bool = True) -> None:
        """Close the fake gamepad."""
        del neutral


def test_controller_frame_is_converted_to_one_public_input_state(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="demi.controller.swbt_adapter")
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
        await adapter.send_frame(frame)

    asyncio.run(exercise())

    assert len(gamepad.sent_states) == 1
    state = gamepad.sent_states[0]
    assert state.buttons == frozenset({Button.A, Button.ZR})
    assert state.left_stick == Stick.normalized(x=-1.0, y=0.25)
    assert state.right_stick == Stick.normalized(x=0.5, y=-1.0)
    expected_imu = IMUFrame.gyro_rate(
        x_rad_s=1.0,
        y_rad_s=-2.0,
        z_rad_s=3.0,
    ).with_accel_g(x_g=0.25, y_g=-0.5, z_g=0.75)
    assert state.imu_frames == (expected_imu, expected_imu, expected_imu)
    assert (
        "direct-input sent sequence=1 capture_epoch=1 "
        "capture_active=True pointer_capture_active=False buttons=A,ZR" in caplog.messages
    )


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
        await adapter.send_frame(neutral_frame)

    asyncio.run(exercise())

    state = gamepad.sent_states[0]
    expected_imu = IMUFrame.gyro_rate().with_accel_g(x_g=0.0, y_g=0.0, z_g=1.0)
    assert state.buttons == frozenset()
    assert state.left_stick == Stick.center()
    assert state.right_stick == Stick.center()
    assert state.imu_frames == (expected_imu, expected_imu, expected_imu)
    assert state.imu_frames != InputState.neutral().imu_frames


def test_adapter_info_and_project_colors_cross_the_public_boundary() -> None:
    gamepad = RecordingGamepad()
    constructor_kwargs: dict[str, object] = {}

    def gamepad_factory(**kwargs: object) -> RecordingGamepad:
        constructor_kwargs.update(kwargs)
        return gamepad

    info = AdapterInfo(
        name="usb:0",
        manufacturer="Acme",
        product="Blue Dongle",
        vendor_id=0x1234,
        product_id=0x5678,
        serial_number="private-serial",
    )
    adapter = SwbtControllerAdapter(
        gamepad_factory=gamepad_factory,
        adapter_lister=lambda: (info,),
    )
    colors = ControllerColorSettings(
        body="#ABCDEF",
        buttons="#102030",
        left_grip="#405060",
        right_grip="#708090",
    )

    async def exercise() -> tuple[AdapterDescriptor, ...]:
        descriptors = await adapter.discover_adapters()
        await adapter.connect_saved("usb:0", Path("bond.json"), 30.0, colors)
        return descriptors

    descriptors = asyncio.run(exercise())

    assert descriptors == (
        AdapterDescriptor(
            id="usb:0",
            display_name="Blue Dongle",
            transport="usb",
            metadata=(
                ("manufacturer", "Acme"),
                ("product", "Blue Dongle"),
                ("vendor_id", "1234"),
                ("product_id", "5678"),
            ),
        ),
    )
    assert constructor_kwargs["adapter"] == "usb:0"
    assert constructor_kwargs["key_store_path"] == "bond.json"
    swbt_colors = constructor_kwargs["controller_colors"]
    assert isinstance(swbt_colors, ControllerColors)
    assert swbt_colors.body == 0xABCDEF
    assert swbt_colors.buttons == 0x102030
    assert swbt_colors.left_grip == 0x405060
    assert swbt_colors.right_grip == 0x708090


def test_direct_gamepad_constructor_omits_report_period() -> None:
    gamepad = RecordingGamepad()
    constructor_kwargs: dict[str, object] = {}

    def gamepad_factory(**kwargs: object) -> RecordingGamepad:
        constructor_kwargs.update(kwargs)
        return gamepad

    adapter = SwbtControllerAdapter(
        gamepad_factory=gamepad_factory,
        adapter_lister=lambda: (),
    )

    asyncio.run(
        adapter.connect_saved(
            "usb:0",
            Path("bond.json"),
            30.0,
            ControllerColorSettings(),
        )
    )

    assert "report_period_us" not in constructor_kwargs
