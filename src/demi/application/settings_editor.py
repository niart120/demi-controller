"""Immutable draft editing for Project_Demi settings modals."""

from dataclasses import dataclass, replace
from typing import Literal

from demi.domain.errors import DomainValueError
from demi.domain.mapping import Binding, BindingTarget, InputProfile, default_profile
from demi.domain.settings import (
    AppSettings,
    ConnectionSettings,
    ControllerColorSettings,
    DiagnosticLevel,
    InputSettings,
    MouseSettings,
)

type ColorField = Literal["body", "buttons", "left_grip", "right_grip"]

RESERVED_BINDING_SOURCES = frozenset({"KEY:F4"})


@dataclass(frozen=True, slots=True)
class BindingConflict:
    """One duplicate binding source or local-action collision."""

    source: str
    binding_indices: tuple[int, ...]
    local_action: str | None = None


class SettingsEditor:
    """Edit an immutable ``AppSettings`` snapshot without mutating its source."""

    def __init__(self, settings: AppSettings) -> None:
        """Create a draft initialized from a validated settings snapshot."""
        self._draft = settings

    @property
    def draft(self) -> AppSettings:
        """Return the current immutable settings draft."""
        return self._draft

    def update_binding(
        self,
        index: int,
        *,
        source: str | None = None,
        target: BindingTarget | None = None,
        amount: float | None = None,
        inverted: bool | None = None,
    ) -> None:
        """Replace one active-profile binding in the draft.

        Raises:
            DomainValueError: The index, binding values, or reserved F4 source is invalid.
        """
        profile = self._active_profile()
        try:
            current = profile.bindings[index]
        except IndexError:
            raise DomainValueError from None
        next_source = current.source if source is None else source
        if next_source in RESERVED_BINDING_SOURCES:
            raise DomainValueError
        updated = Binding(
            source=next_source,
            target=current.target if target is None else target,
            amount=current.amount if amount is None else amount,
            inverted=current.inverted if inverted is None else inverted,
        )
        bindings = (*profile.bindings[:index], updated, *profile.bindings[index + 1 :])
        self._replace_profile(replace(profile, bindings=bindings))

    def update_connection(
        self,
        *,
        adapter_id: str | None = None,
        bond_slot: str | None = None,
        timeout_seconds: float | None = None,
        reconnect_on_start: bool | None = None,
        diagnostic_level: DiagnosticLevel | None = None,
    ) -> None:
        """Replace editable connection fields after domain validation."""
        current = self._draft.connection
        connection = ConnectionSettings(
            adapter_id=current.adapter_id if adapter_id is None else adapter_id,
            controller=current.controller,
            bond_slot=current.bond_slot if bond_slot is None else bond_slot,
            timeout_seconds=(
                current.timeout_seconds if timeout_seconds is None else timeout_seconds
            ),
            reconnect_on_start=(
                current.reconnect_on_start if reconnect_on_start is None else reconnect_on_start
            ),
            diagnostic_level=(
                current.diagnostic_level if diagnostic_level is None else diagnostic_level
            ),
        )
        self._draft = replace(self._draft, connection=connection)

    def update_color(self, field: ColorField, value: str) -> None:
        """Replace one color field and normalize it through the domain value."""
        current = self._draft.controller_colors
        if field == "body":
            colors = ControllerColorSettings(
                body=value,
                buttons=current.buttons,
                left_grip=current.left_grip,
                right_grip=current.right_grip,
            )
        elif field == "buttons":
            colors = ControllerColorSettings(
                body=current.body,
                buttons=value,
                left_grip=current.left_grip,
                right_grip=current.right_grip,
            )
        elif field == "left_grip":
            colors = ControllerColorSettings(
                body=current.body,
                buttons=current.buttons,
                left_grip=value,
                right_grip=current.right_grip,
            )
        else:
            colors = ControllerColorSettings(
                body=current.body,
                buttons=current.buttons,
                left_grip=current.left_grip,
                right_grip=value,
            )
        self._draft = replace(self._draft, controller_colors=colors)

    def update_mouse(
        self,
        *,
        gyro_enabled: bool | None = None,
        horizontal_sensitivity: float | None = None,
        vertical_sensitivity: float | None = None,
        invert_x: bool | None = None,
        invert_y: bool | None = None,
        pitch_limit_degrees: float | None = None,
    ) -> None:
        """Replace editable mouse-to-IMU settings after domain validation.

        Args:
            gyro_enabled: Whether mouse motion contributes controller IMU values.
            horizontal_sensitivity: Independent yaw sensitivity multiplier.
            vertical_sensitivity: Independent pitch sensitivity multiplier.
            invert_x: Whether horizontal mouse motion reverses yaw direction.
            invert_y: Whether vertical mouse motion reverses pitch direction.
            pitch_limit_degrees: Maximum absolute virtual pitch in degrees.
        """
        current_input = self._draft.input
        current_mouse = current_input.mouse
        mouse = MouseSettings(
            gyro_enabled=current_mouse.gyro_enabled if gyro_enabled is None else gyro_enabled,
            horizontal_sensitivity=(
                current_mouse.horizontal_sensitivity
                if horizontal_sensitivity is None
                else horizontal_sensitivity
            ),
            vertical_sensitivity=(
                current_mouse.vertical_sensitivity
                if vertical_sensitivity is None
                else vertical_sensitivity
            ),
            invert_x=current_mouse.invert_x if invert_x is None else invert_x,
            invert_y=current_mouse.invert_y if invert_y is None else invert_y,
            pitch_limit_degrees=(
                current_mouse.pitch_limit_degrees
                if pitch_limit_degrees is None
                else pitch_limit_degrees
            ),
        )
        self._draft = replace(
            self._draft,
            input=InputSettings(
                evaluation_interval_ms=current_input.evaluation_interval_ms,
                circular_stick_limit=current_input.circular_stick_limit,
                mouse=mouse,
            ),
        )

    def update_input(
        self,
        *,
        evaluation_interval_ms: int | None = None,
        circular_stick_limit: bool | None = None,
    ) -> None:
        """Replace editable input loop fields while retaining mouse settings.

        Args:
            evaluation_interval_ms: Input evaluation interval in milliseconds.
            circular_stick_limit: Whether stick coordinates use a circular limit.
        """
        current = self._draft.input
        self._draft = replace(
            self._draft,
            input=InputSettings(
                evaluation_interval_ms=(
                    current.evaluation_interval_ms
                    if evaluation_interval_ms is None
                    else evaluation_interval_ms
                ),
                circular_stick_limit=(
                    current.circular_stick_limit
                    if circular_stick_limit is None
                    else circular_stick_limit
                ),
                mouse=current.mouse,
            ),
        )

    def reset_profile(self) -> None:
        """Restore the built-in profile while retaining connection and colors."""
        self._draft = replace(
            self._draft,
            active_profile="default",
            profiles=(default_profile(),),
        )

    def conflicts(self) -> tuple[BindingConflict, ...]:
        """Return deterministic duplicate-source and local-action warnings."""
        profile = self._active_profile()
        indices_by_source: dict[str, list[int]] = {}
        for index, binding in enumerate(profile.bindings):
            indices_by_source.setdefault(binding.source, []).append(index)

        conflicts: list[BindingConflict] = []
        for source, indices in indices_by_source.items():
            if len(indices) >= 2:
                conflicts.append(BindingConflict(source=source, binding_indices=tuple(indices)))

        local_actions = (
            *self._draft.local_actions.toggle_capture,
            *self._draft.local_actions.quit,
            *self._draft.local_actions.connection,
            *self._draft.local_actions.release_capture,
        )
        local_action_set = set(local_actions)
        for index, binding in enumerate(profile.bindings):
            if not binding.source.startswith("KEY:"):
                continue
            action = binding.source.removeprefix("KEY:")
            if action in local_action_set:
                conflicts.append(
                    BindingConflict(
                        source=binding.source,
                        binding_indices=(index,),
                        local_action=action,
                    )
                )
        return tuple(
            sorted(
                conflicts,
                key=lambda conflict: (
                    conflict.binding_indices[0],
                    conflict.source,
                    conflict.local_action or "",
                ),
            )
        )

    def validate(self) -> None:
        """Validate reserved modal rules before a repository save."""
        if any(
            binding.source == "KEY:F4"
            for profile in self._draft.profiles
            for binding in profile.bindings
        ):
            raise DomainValueError

    def _active_profile(self) -> InputProfile:
        for profile in self._draft.profiles:
            if profile.id == self._draft.active_profile:
                return profile
        raise DomainValueError

    def _replace_profile(self, profile: InputProfile) -> None:
        self._draft = replace(
            self._draft,
            profiles=tuple(
                profile if candidate.id == profile.id else candidate
                for candidate in self._draft.profiles
            ),
        )
