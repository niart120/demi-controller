from dataclasses import dataclass, field

import pytest

from demi.domain.gamepad import GamepadButton
from demi.platform.windows_xinput import WindowsXInputBackend, XInputSnapshot


@dataclass
class FakeXInputReader:
    """Return configured XInput states by slot."""

    states: dict[int, XInputSnapshot] = field(default_factory=dict)

    def get_state(self, slot: int) -> XInputSnapshot | None:
        """Return the configured state for one slot."""
        return self.states.get(slot)


def test_xinput_backend_selects_first_connected_slot_and_normalizes_it() -> None:
    reader = FakeXInputReader(
        {
            1: XInputSnapshot(
                buttons=0x1000 | 0x0200 | 0x0001,
                left_trigger=255,
                right_trigger=127,
                left_x=32_767,
                left_y=32_767,
                right_x=0,
                right_y=0,
            )
        }
    )
    backend = WindowsXInputBackend(reader=reader)

    state = backend.poll()

    assert state.connected is True
    assert state.buttons == frozenset(
        {GamepadButton.SOUTH, GamepadButton.RIGHT_SHOULDER, GamepadButton.DPAD_UP}
    )
    assert state.left_stick.x == pytest.approx(2**-0.5)
    assert state.left_stick.y == pytest.approx(2**-0.5)
    assert state.left_trigger == 1.0
    assert state.right_trigger == 127 / 255


def test_xinput_backend_reselects_after_its_active_slot_disconnects() -> None:
    reader = FakeXInputReader({0: XInputSnapshot.neutral(), 2: XInputSnapshot.neutral()})
    backend = WindowsXInputBackend(reader=reader)

    assert backend.poll().connected is True
    del reader.states[0]

    assert backend.poll().connected is True
