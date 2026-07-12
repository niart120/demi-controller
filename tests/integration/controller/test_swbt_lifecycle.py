import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from swbt import InputState

from demi.controller.swbt_adapter import SwbtControllerAdapter
from demi.domain.settings import ControllerColorSettings


@dataclass
class RecordingGamepad:
    """Fake that records the public gamepad lifecycle calls."""

    calls: list[str] = field(default_factory=list)
    reconnect_timeouts: list[float | None] = field(default_factory=list)
    connect_options: list[tuple[float | None, bool]] = field(default_factory=list)
    applied_states: list[InputState] = field(default_factory=list)
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

    async def apply(self, state: InputState) -> None:
        """Record complete state application."""
        self.calls.append("apply")
        self.applied_states.append(state)

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
