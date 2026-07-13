"""Shared cleanup for controller integration tests."""

from collections.abc import Iterator

import pytest

from demi.controller.runtime import ControllerRuntime


@pytest.fixture(autouse=True)
def close_started_controller_runtimes(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """Close every runtime even when a test assertion stops before cleanup."""
    started_runtimes: list[ControllerRuntime] = []
    original_start = ControllerRuntime.start

    def tracking_start(runtime: ControllerRuntime) -> None:
        started_runtimes.append(runtime)
        original_start(runtime)

    monkeypatch.setattr(ControllerRuntime, "start", tracking_start)
    try:
        yield
    finally:
        for runtime in reversed(started_runtimes):
            runtime.close()
