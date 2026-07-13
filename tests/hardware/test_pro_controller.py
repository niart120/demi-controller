"""Explicit preflight entry point for manual Pro Controller acceptance."""

import os

import pytest


@pytest.mark.bumble
@pytest.mark.hardware
def test_pro_controller_acceptance_preflight() -> None:
    """Require explicit hardware context before the manual checklist starts."""
    if os.environ.get("DEMI_HARDWARE") != "1":
        pytest.skip("set DEMI_HARDWARE=1 to select the manual hardware preflight")

    missing = [
        name
        for name in ("DEMI_HARDWARE_ADAPTER_ID", "DEMI_HARDWARE_TARGET")
        if not os.environ.get(name)
    ]
    if missing:
        pytest.fail(f"missing hardware context: {', '.join(missing)}")

    pytest.skip(
        "preflight only; execute the acceptance checklist manually and record it in "
        "spec/hardware-test-log.md"
    )
