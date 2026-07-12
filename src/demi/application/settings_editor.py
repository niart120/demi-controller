"""Immutable draft editing for Project_Demi settings modals."""

from dataclasses import replace
from typing import Literal

from demi.domain.errors import DomainValueError
from demi.domain.mapping import Binding, BindingTarget, InputProfile, default_profile
from demi.domain.settings import (
    AppSettings,
    ConnectionSettings,
    ControllerColorSettings,
    DiagnosticLevel,
)

type ColorField = Literal["body", "buttons", "left_grip", "right_grip"]


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
            DomainValueError: The index, binding values, or reserved F12 source is invalid.
        """
        profile = self._active_profile()
        try:
            current = profile.bindings[index]
        except IndexError:
            raise DomainValueError from None
        next_source = current.source if source is None else source
        if next_source == "KEY:F12":
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

    def reset_profile(self) -> None:
        """Restore the built-in profile while retaining connection and colors."""
        self._draft = replace(
            self._draft,
            active_profile="default",
            profiles=(default_profile(),),
        )

    def validate(self) -> None:
        """Validate reserved modal rules before a repository save."""
        if any(
            binding.source == "KEY:F12"
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
