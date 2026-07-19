import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from swbt import InputState

from demi.controller.swbt_adapter import SwbtControllerAdapter
from demi.domain.controller import AccelG, ControllerFrame, GyroRate, LogicalButton, StickVector
from demi.domain.settings import ControllerColorSettings


@dataclass
class RecordingGamepad:
    """Fake that records the public gamepad lifecycle calls."""

    calls: list[str] = field(default_factory=list)
    reconnect_timeouts: list[float | None] = field(default_factory=list)
    connect_options: list[tuple[float | None, bool]] = field(default_factory=list)
    sent_states: list[InputState] = field(default_factory=list)
    close_neutral_values: list[bool] = field(default_factory=list)

    async def open(self) -> None:
        """Record opening the transport."""
        self.calls.append("open")

    async def reconnect(self, timeout: float | None = None) -> None:  # noqa: ASYNC109
        """Record saved-bond reconnect."""
        self.calls.append("reconnect")
        self.reconnect_timeouts.append(timeout)

    async def connect(
        self,
        *,
        timeout: float | None = None,  # noqa: ASYNC109
        allow_pairing: bool = False,
    ) -> None:
        """Record explicit pairing options."""
        self.calls.append("connect")
        self.connect_options.append((timeout, allow_pairing))

    async def send(self, state: InputState) -> None:
        """Record one complete sent state."""
        self.calls.append("send")
        self.sent_states.append(state)

    async def close(self, *, neutral: bool = True) -> None:
        """Record closing and its neutral policy."""
        self.calls.append("close")
        self.close_neutral_values.append(neutral)


def test_saved_reconnect_and_pairing_use_distinct_public_lifecycle_routes() -> None:
    gamepads: list[RecordingGamepad] = []
    factory_kwargs: list[dict[str, object]] = []

    def gamepad_factory(**kwargs: object) -> RecordingGamepad:
        factory_kwargs.append(kwargs)
        gamepad = RecordingGamepad()
        gamepads.append(gamepad)
        return gamepad

    adapter = SwbtControllerAdapter(
        gamepad_factory=gamepad_factory,
        adapter_lister=lambda: (),
    )
    colors = ControllerColorSettings()

    async def exercise() -> None:
        await adapter.connect_saved("usb:0", Path("saved.json"), 12.5, colors)
        await adapter.disconnect()
        await adapter.start_pairing("usb:0", Path("new.json"), 20.0, colors)
        await adapter.close()

    asyncio.run(exercise())

    assert [gamepad.calls for gamepad in gamepads] == [
        ["open", "reconnect", "close"],
        ["open", "connect", "close"],
    ]
    assert gamepads[0].reconnect_timeouts == [12.5]
    assert gamepads[1].connect_options == [(20.0, True)]
    assert [kwargs["key_store_path"] for kwargs in factory_kwargs] == [
        "saved.json",
        "new.json",
    ]


def test_frame_apply_and_color_recreate_preserve_saved_connection_context() -> None:
    gamepads: list[RecordingGamepad] = []
    factory_kwargs: list[dict[str, object]] = []

    def gamepad_factory(**kwargs: object) -> RecordingGamepad:
        factory_kwargs.append(kwargs)
        gamepad = RecordingGamepad()
        gamepads.append(gamepad)
        return gamepad

    adapter = SwbtControllerAdapter(
        gamepad_factory=gamepad_factory,
        adapter_lister=lambda: (),
    )
    initial_colors = ControllerColorSettings()
    updated_colors = ControllerColorSettings(body="#ABCDEF")
    frame = ControllerFrame(
        sequence=1,
        capture_epoch=1,
        monotonic_ns=1,
        buttons=frozenset({LogicalButton.A}),
        left_stick=StickVector(x=0.5, y=0.0),
        right_stick=StickVector(x=0.0, y=-0.5),
        gyro_rate=GyroRate(0.0, 0.0, 0.0),
        accel_g=AccelG(0.0, 0.0, 1.0),
        capture_active=True,
    )

    async def exercise() -> None:
        await adapter.connect_saved("usb:0", Path("saved.json"), 12.5, initial_colors)
        await adapter.send_frame(frame)
        await adapter.recreate_with_colors(updated_colors)
        await adapter.close()

    asyncio.run(exercise())

    assert gamepads[0].calls == ["open", "reconnect", "send", "close"]
    assert gamepads[1].calls == ["open", "reconnect", "close"]
    assert gamepads[0].reconnect_timeouts == [12.5]
    assert gamepads[1].reconnect_timeouts == [12.5]
    assert factory_kwargs[0]["key_store_path"] == "saved.json"
    assert factory_kwargs[1]["key_store_path"] == "saved.json"
