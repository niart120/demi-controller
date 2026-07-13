"""Normalized keyboard and mouse state independent from a GUI library."""

import re
from dataclasses import dataclass, field
from math import isfinite

from .errors import DomainValueError

_KEY_SYMBOL_PATTERN = re.compile(r"[A-Z0-9_]+")
_MOUSE_BUTTON_PATTERN = re.compile(r"(?:LEFT|MIDDLE|RIGHT|BUTTON_[0-9]+)")


@dataclass(frozen=True, slots=True)
class KeySource:
    """Canonical keyboard source with optional normalized modifiers."""

    symbol: str
    modifiers: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        """Normalize and validate the key symbol and modifiers."""
        if (
            not isinstance(self.symbol, str)
            or _KEY_SYMBOL_PATTERN.fullmatch(self.symbol.upper()) is None
        ):
            raise DomainValueError
        if not isinstance(self.modifiers, frozenset) or not all(
            isinstance(modifier, str)
            and _KEY_SYMBOL_PATTERN.fullmatch(modifier.upper()) is not None
            for modifier in self.modifiers
        ):
            raise DomainValueError
        object.__setattr__(self, "symbol", self.symbol.upper())
        object.__setattr__(
            self,
            "modifiers",
            frozenset(modifier.upper() for modifier in self.modifiers),
        )

    @property
    def canonical(self) -> str:
        """Return the persisted ``KEY:...`` source name."""
        modifiers = sorted(self.modifiers)
        if modifiers:
            return f"KEY:{'+'.join((*modifiers, self.symbol))}"
        return f"KEY:{self.symbol}"


@dataclass(frozen=True, slots=True)
class MouseButtonSource:
    """Canonical mouse button source."""

    button: str

    def __post_init__(self) -> None:
        """Normalize and validate the mouse button name."""
        if (
            not isinstance(self.button, str)
            or _MOUSE_BUTTON_PATTERN.fullmatch(self.button.upper()) is None
        ):
            raise DomainValueError
        object.__setattr__(self, "button", self.button.upper())

    @property
    def canonical(self) -> str:
        """Return the persisted ``MOUSE:...`` source name."""
        return f"MOUSE:{self.button}"


type PhysicalSource = KeySource | MouseButtonSource


def _require_motion_value(value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise DomainValueError


@dataclass(slots=True)
class PhysicalInputState:
    """Mutable held-input and relative-motion state for one capture session."""

    held_keys: set[KeySource] = field(default_factory=set)
    held_mouse_buttons: set[MouseButtonSource] = field(default_factory=set)
    accumulated_dx: float = 0.0
    accumulated_dy: float = 0.0
    revision: int = 0

    def press_key(self, symbol: str, modifiers: frozenset[str] = frozenset()) -> None:
        """Add a normalized key source, ignoring duplicate press notifications."""
        source = KeySource(symbol, modifiers)
        if source not in self.held_keys:
            self.held_keys.add(source)
            self.revision += 1

    def release_key(self, symbol: str, modifiers: frozenset[str] = frozenset()) -> None:
        """Remove a key source; releasing an absent source is harmless."""
        source = KeySource(symbol, modifiers)
        if source in self.held_keys:
            self.held_keys.remove(source)
            self.revision += 1

    def press_mouse_button(self, button: str) -> None:
        """Add a normalized mouse button, ignoring duplicate press notifications."""
        source = MouseButtonSource(button)
        if source not in self.held_mouse_buttons:
            self.held_mouse_buttons.add(source)
            self.revision += 1

    def release_mouse_button(self, button: str) -> None:
        """Remove a mouse button; releasing an absent source is harmless."""
        source = MouseButtonSource(button)
        if source in self.held_mouse_buttons:
            self.held_mouse_buttons.remove(source)
            self.revision += 1

    def add_mouse_motion(self, dx: float, dy: float) -> None:
        """Accumulate finite relative mouse movement for the next evaluation."""
        _require_motion_value(dx)
        _require_motion_value(dy)
        if dx or dy:
            self.accumulated_dx += dx
            self.accumulated_dy += dy
            self.revision += 1

    def consume_mouse_motion(self) -> tuple[float, float]:
        """Return and clear the accumulated relative mouse movement once."""
        motion = (self.accumulated_dx, self.accumulated_dy)
        if motion != (0.0, 0.0):
            self.accumulated_dx = 0.0
            self.accumulated_dy = 0.0
            self.revision += 1
        return motion

    def is_source_active(self, canonical_source: str) -> bool:
        """Return whether a canonical binding source is currently held."""
        return any(source.canonical == canonical_source for source in self.held_keys) or any(
            source.canonical == canonical_source for source in self.held_mouse_buttons
        )

    def clear(self) -> None:
        """Clear held sources and pending relative movement."""
        changed = bool(
            self.held_keys or self.held_mouse_buttons or self.accumulated_dx or self.accumulated_dy
        )
        self.held_keys.clear()
        self.held_mouse_buttons.clear()
        self.accumulated_dx = 0.0
        self.accumulated_dy = 0.0
        if changed:
            self.revision += 1
