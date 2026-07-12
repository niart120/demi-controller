from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from demi.application.state import ConnectionState
from demi.controller.commands import ConnectSaved, DiscoverAdapters
from demi.controller.events import (
    AdapterDescriptor,
    AdaptersDiscovered,
    ControllerError,
    ControllerErrorCategory,
)
from demi.domain.settings import ControllerColorSettings

if TYPE_CHECKING:
    from demi.controller.commands import ControllerCommand
    from demi.controller.events import RuntimeEvent


def test_controller_commands_are_frozen_and_form_a_typed_union() -> None:
    command: ControllerCommand = DiscoverAdapters()
    saved = ConnectSaved(
        adapter_id="usb:0",
        bond_path=Path("bonds/default.json"),
        timeout_seconds=30.0,
        colors=ControllerColorSettings(),
    )

    assert isinstance(command, DiscoverAdapters)
    assert saved.adapter_id == "usb:0"
    with pytest.raises(FrozenInstanceError):
        saved.__setattr__("adapter_id", "usb:1")


def test_runtime_events_keep_adapter_and_error_information_as_values() -> None:
    descriptor = AdapterDescriptor(
        id="usb:0",
        display_name="Test Adapter",
        transport="usb",
        metadata=(("vendor", "fake"),),
    )
    discovered: RuntimeEvent = AdaptersDiscovered(adapters=(descriptor,))
    error = ControllerError(
        category=ControllerErrorCategory.CONNECTION_LOST,
        summary="接続が失われました",
        retryable=True,
        diagnostic_id="diag-001",
    )

    assert isinstance(discovered, AdaptersDiscovered)
    assert discovered.adapters[0].display_name == "Test Adapter"
    assert error.category is ControllerErrorCategory.CONNECTION_LOST
    assert error.retryable is True
    assert ConnectionState.CONNECTED.value == "connected"
