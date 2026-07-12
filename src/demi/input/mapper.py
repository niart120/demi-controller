"""Pure mapping operations from physical state to domain controls."""

from demi.domain.controller import LogicalButton
from demi.domain.mapping import InputProfile, is_button_target, logical_button_for_target
from demi.domain.physical_input import PhysicalInputState


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
        if is_button_target(binding.target) and (
            state.is_source_active(binding.source) ^ binding.inverted
        ):
            buttons.add(logical_button_for_target(binding.target))
    return frozenset(buttons)
