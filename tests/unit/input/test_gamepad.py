from dataclasses import dataclass

import pytest

from demi.domain.controller import LogicalButton, StickVector
from demi.domain.gamepad import GamepadButton, GamepadState
from demi.input.gamepad import (
    PreferredGamepadBackend,
    apply_stick_dead_zone,
    combine_sticks,
    standard_gamepad_buttons,
)


@dataclass
class FakeGamepadBackend:
    """Return a mutable test gamepad state."""

    state: GamepadState
    closed: bool = False

    def poll(self) -> GamepadState:
        """Return the configured state."""
        return self.state

    def close(self) -> None:
        """Record shutdown."""
        self.closed = True


def test_stick_dead_zone_rescales_and_inverts_sdl_y_axis() -> None:
    assert apply_stick_dead_zone(0, 0) == StickVector(0.0, 0.0)
    assert apply_stick_dead_zone(3_000, -3_000) == StickVector(0.0, 0.0)

    assert apply_stick_dead_zone(32_767, 0) == StickVector(1.0, 0.0)
    assert apply_stick_dead_zone(0, 32_767) == StickVector(0.0, -1.0)


def test_standard_gamepad_buttons_map_to_same_physical_pro_positions() -> None:
    state = GamepadState(
        connected=True,
        buttons=frozenset(
            {
                GamepadButton.SOUTH,
                GamepadButton.EAST,
                GamepadButton.WEST,
                GamepadButton.NORTH,
                GamepadButton.DPAD_UP,
                GamepadButton.LEFT_SHOULDER,
                GamepadButton.LEFT_STICK,
                GamepadButton.BACK,
                GamepadButton.GUIDE,
            }
        ),
        left_stick=StickVector(0.0, 0.0),
        right_stick=StickVector(0.0, 0.0),
        left_trigger=0.5,
        right_trigger=0.49,
    )

    assert standard_gamepad_buttons(state) == frozenset(
        {
            LogicalButton.B,
            LogicalButton.A,
            LogicalButton.Y,
            LogicalButton.X,
            LogicalButton.DPAD_UP,
            LogicalButton.L,
            LogicalButton.LEFT_STICK,
            LogicalButton.MINUS,
            LogicalButton.HOME,
            LogicalButton.ZL,
        }
    )


def test_sticks_combine_directional_maxima_before_circular_limit() -> None:
    combined = combine_sticks(
        StickVector(0.25, -0.8), StickVector(-0.75, 0.5), circular_limit=False
    )
    assert combined.x == -0.5
    assert combined.y == pytest.approx(-0.3)

    limited = combine_sticks(StickVector(1.0, 0.0), StickVector(0.0, 1.0), circular_limit=True)

    assert limited.x == limited.y
    assert round(limited.x, 6) == round(2**-0.5, 6)


def test_preferred_backend_stays_selected_until_it_disconnects() -> None:
    preferred = FakeGamepadBackend(GamepadState.neutral())
    fallback = FakeGamepadBackend(
        GamepadState(
            connected=True,
            buttons=frozenset({GamepadButton.SOUTH}),
            left_stick=StickVector(0.0, 0.0),
            right_stick=StickVector(0.0, 0.0),
            left_trigger=0.0,
            right_trigger=0.0,
        )
    )
    backend = PreferredGamepadBackend(preferred=preferred, fallback=fallback)

    assert backend.poll() == fallback.state
    preferred.state = fallback.state
    assert backend.poll() == fallback.state
    fallback.state = GamepadState.neutral()

    assert backend.poll() == preferred.state
