"""Pure mapping operations from physical state to domain controls."""

from math import hypot, isfinite
from typing import Literal

from demi.domain.controller import GyroRate, LogicalButton, StickVector
from demi.domain.errors import DomainValueError
from demi.domain.mapping import (
    BindingTarget,
    InputProfile,
    is_button_target,
    is_diagnostic_target,
    logical_button_for_target,
)
from demi.domain.physical_input import PhysicalInputState

from .rotation_intent import RotationIntent

DIAGNOSTIC_GYRO_RADIANS_PER_SECOND = 1.0


def synthesize_diagnostic_rotation_intent(
    profile: InputProfile,
    state: PhysicalInputState,
    *,
    dt_seconds: float,
    capture_active: bool = True,
) -> RotationIntent:
    """Convert active Y/Z diagnostic bindings into angular displacement.

    Args:
        profile: Profile whose diagnostic bindings are evaluated.
        state: Current normalized held-input state.
        dt_seconds: Elapsed evaluation time used to integrate fixed rates.
        capture_active: Disable the diagnostic input when false.

    Returns:
        Yaw and pitch displacement for the current evaluation.

    Raises:
        DomainValueError: The elapsed time is not a finite number.
    """
    if (
        isinstance(dt_seconds, bool)
        or not isinstance(dt_seconds, (int, float))
        or not isfinite(dt_seconds)
    ):
        raise DomainValueError
    if not capture_active or dt_seconds <= 0.0:
        return RotationIntent(0.0, 0.0)

    active_targets = {
        binding.target for binding in profile.bindings if state.is_source_active(binding.source)
    }
    pitch_direction = float(BindingTarget.GYRO_Y_POSITIVE in active_targets) - float(
        BindingTarget.GYRO_Y_NEGATIVE in active_targets
    )
    yaw_direction = float(BindingTarget.GYRO_Z_POSITIVE in active_targets) - float(
        BindingTarget.GYRO_Z_NEGATIVE in active_targets
    )
    return RotationIntent(
        yaw_delta_radians=(yaw_direction * DIAGNOSTIC_GYRO_RADIANS_PER_SECOND * dt_seconds),
        pitch_delta_radians=(pitch_direction * DIAGNOSTIC_GYRO_RADIANS_PER_SECOND * dt_seconds),
    )


def synthesize_diagnostic_gyro_rate(
    profile: InputProfile,
    state: PhysicalInputState,
    *,
    capture_active: bool = True,
) -> GyroRate:
    """Return direct local-axis diagnostic gyro output.

    Args:
        profile: Profile whose diagnostic bindings are evaluated.
        state: Current normalized held-input state.
        capture_active: Disable the diagnostic input when false.

    Returns:
        Direct local-axis gyro rate for the current evaluation.
    """
    if not capture_active:
        return GyroRate(0.0, 0.0, 0.0)
    active_targets = {
        binding.target for binding in profile.bindings if state.is_source_active(binding.source)
    }
    x_direction = float(BindingTarget.GYRO_X_POSITIVE in active_targets) - float(
        BindingTarget.GYRO_X_NEGATIVE in active_targets
    )
    return GyroRate(
        x_direction * DIAGNOSTIC_GYRO_RADIANS_PER_SECOND,
        0.0,
        0.0,
    )


def is_imu_neutral_active(
    profile: InputProfile,
    state: PhysicalInputState,
    *,
    capture_active: bool = True,
) -> bool:
    """Return whether the current evaluation requests physical neutral IMU."""
    return capture_active and any(
        binding.target is BindingTarget.IMU_NEUTRAL and state.is_source_active(binding.source)
        for binding in profile.bindings
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
    diagnostic_sources = _diagnostic_sources(profile)
    buttons: set[LogicalButton] = set()
    for binding in profile.bindings:
        if binding.source in diagnostic_sources:
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
    diagnostic_sources = _diagnostic_sources(profile)
    for binding in profile.bindings:
        if binding.source in diagnostic_sources:
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


def _diagnostic_sources(profile: InputProfile) -> frozenset[str]:
    return frozenset(
        binding.source for binding in profile.bindings if is_diagnostic_target(binding.target)
    )
