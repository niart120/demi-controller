"""Pure mapping operations from physical state to domain controls."""

from math import hypot
from typing import Literal

from demi.domain.controller import GyroRate, LogicalButton, StickVector
from demi.domain.errors import DomainValueError
from demi.domain.mapping import InputProfile, is_button_target, logical_button_for_target
from demi.domain.physical_input import PhysicalInputState

IJKL_GYRO_RADIANS_PER_SECOND = 1.0
_IJKL_GYRO_SOURCES = frozenset(
    {
        "KEY:I",
        "KEY:K",
        "KEY:J",
        "KEY:L",
    }
)


def synthesize_ijkl_gyro(
    state: PhysicalInputState,
    *,
    capture_active: bool = True,
) -> GyroRate:
    """Convert held I/J/K/L keys into fixed diagnostic Y/Z gyro rates.

    Args:
        state: Current normalized held-input state.
        capture_active: Disable the diagnostic input when false.

    Returns:
        A fixed-rate Y/Z gyro value with opposing directions cancelled.
    """
    if not capture_active:
        return GyroRate(0.0, 0.0, 0.0)
    y_direction = float(state.is_source_active("KEY:K")) - float(state.is_source_active("KEY:I"))
    z_direction = float(state.is_source_active("KEY:J")) - float(state.is_source_active("KEY:L"))
    return GyroRate(
        x_radians_per_second=0.0,
        y_radians_per_second=y_direction * IJKL_GYRO_RADIANS_PER_SECOND,
        z_radians_per_second=z_direction * IJKL_GYRO_RADIANS_PER_SECOND,
    )


def aggregate_buttons(
    profile: InputProfile,
    state: PhysicalInputState,
    *,
    capture_active: bool,
) -> frozenset[LogicalButton]:
    """Aggregate active button bindings for one input evaluation.

    Args:
        profile: Profile whose bindings are evaluated.
        state: Current normalized held-input state.
        capture_active: Whether controller mappings are currently enabled.

    Returns:
        Logical buttons whose source binding is active. Capture outside always
        returns an empty set.
    """
    if not capture_active:
        return frozenset()
    buttons: set[LogicalButton] = set()
    for binding in profile.bindings:
        if binding.source in _IJKL_GYRO_SOURCES:
            continue
        if is_button_target(binding.target) and (
            state.is_source_active(binding.source) ^ binding.inverted
        ):
            buttons.add(logical_button_for_target(binding.target))
    return frozenset(buttons)


def synthesize_stick(
    profile: InputProfile,
    state: PhysicalInputState,
    stick: Literal["left", "right"],
    *,
    circular_limit: bool,
    capture_active: bool = True,
) -> StickVector:
    """Combine directional bindings into one normalized stick vector.

    Args:
        profile: Profile whose stick bindings are evaluated.
        state: Current normalized held-input state.
        stick: ``left`` or ``right`` stick selector.
        circular_limit: Normalize diagonal length to one when enabled.
        capture_active: Disable all mappings when false.

    Returns:
        The synthesized stick vector.
    """
    if stick not in {"left", "right"}:
        raise DomainValueError
    if not capture_active:
        return StickVector(x=0.0, y=0.0)

    prefix = f"{stick.upper()}_STICK:"
    x_negative = 0.0
    x_positive = 0.0
    y_negative = 0.0
    y_positive = 0.0
    for binding in profile.bindings:
        if binding.source in _IJKL_GYRO_SOURCES:
            continue
        target = binding.target.value
        if not target.startswith(prefix) or not state.is_source_active(binding.source):
            continue
        direction = target.removeprefix(prefix)
        if direction == "LEFT":
            x_negative = max(x_negative, binding.amount)
        elif direction == "RIGHT":
            x_positive = max(x_positive, binding.amount)
        elif direction == "DOWN":
            y_negative = max(y_negative, binding.amount)
        elif direction == "UP":
            y_positive = max(y_positive, binding.amount)

    x = x_positive - x_negative
    y = y_positive - y_negative
    length = hypot(x, y)
    if circular_limit and length > 1.0:
        x /= length
        y /= length
    return StickVector(x=x, y=y)
