import asyncio
from dataclasses import dataclass
from pathlib import Path

import pytest
from swbt import (
    AdapterDiscoveryError,
    AdapterInfo,
    ConnectionTimeoutError,
    InputState,
    InvalidInputError,
    InvalidKeyStoreError,
    InvalidProfileError,
    TransportOpenError,
)

from demi.controller.adapter import ControllerAdapterError
from demi.controller.events import ControllerErrorCategory
from demi.controller.swbt_adapter import SwbtControllerAdapter
from demi.domain.controller import AccelG, ControllerFrame, GyroRate, StickVector
from demi.domain.settings import ControllerColorSettings


@dataclass
class FailingGamepad:
    """Public-gamepad-shaped fake with one configurable failure."""

    open_error: Exception | None = None
    reconnect_error: Exception | None = None
    connect_error: Exception | None = None
    send_error: Exception | None = None

    async def open(self) -> None:
        """Open or raise the configured error."""
        if self.open_error is not None:
            raise self.open_error

    async def reconnect(self, timeout: float | None = None) -> None:  # noqa: ASYNC109
        """Reconnect or raise the configured error."""
        del timeout
        if self.reconnect_error is not None:
            raise self.reconnect_error

    async def connect(
        self,
        *,
        timeout: float | None = None,  # noqa: ASYNC109
        allow_pairing: bool = False,
    ) -> None:
        """Pair or raise the configured error."""
        del timeout, allow_pairing
        if self.connect_error is not None:
            raise self.connect_error

    async def send(self, state: InputState) -> None:
        """Send or raise the configured error."""
        del state
        if self.send_error is not None:
            raise self.send_error

    async def close(self, *, neutral: bool = True) -> None:
        """Close the fake gamepad."""
        del neutral


def frame() -> ControllerFrame:
    """Return one valid frame for error-path apply tests."""
    return ControllerFrame(
        sequence=1,
        capture_epoch=1,
        monotonic_ns=1,
        buttons=frozenset(),
        left_stick=StickVector(x=0.0, y=0.0),
        right_stick=StickVector(x=0.0, y=0.0),
        gyro_rate=GyroRate(0.0, 0.0, 0.0),
        accel_g=AccelG(0.0, 0.0, 1.0),
        capture_active=True,
    )


def test_discovery_error_is_classified_without_exposing_swbt_type() -> None:
    error = AdapterDiscoveryError("failed", platform="test")

    def list_error() -> tuple[AdapterInfo, ...]:
        raise error

    adapter = SwbtControllerAdapter(adapter_lister=list_error)

    with pytest.raises(ControllerAdapterError) as raised:
        asyncio.run(adapter.discover_adapters())

    assert raised.value.category is ControllerErrorCategory.ADAPTER_OPEN_FAILED


def test_saved_bond_error_is_classified_as_bond_not_found() -> None:
    gamepad = FailingGamepad(reconnect_error=InvalidKeyStoreError())
    adapter = SwbtControllerAdapter(gamepad_factory=lambda **_kwargs: gamepad)

    with pytest.raises(ControllerAdapterError) as raised:
        asyncio.run(
            adapter.connect_saved(
                "usb:0",
                Path("bond.json"),
                30.0,
                ControllerColorSettings(),
            )
        )

    assert raised.value.category is ControllerErrorCategory.BOND_NOT_FOUND


def test_invalid_swbt_profile_is_classified_as_saved_bond_error() -> None:
    gamepad = FailingGamepad(open_error=InvalidProfileError())
    adapter = SwbtControllerAdapter(gamepad_factory=lambda **_kwargs: gamepad)

    with pytest.raises(ControllerAdapterError) as raised:
        asyncio.run(
            adapter.connect_saved(
                "usb:0",
                Path("legacy-or-invalid.json"),
                30.0,
                ControllerColorSettings(),
            )
        )

    assert raised.value.category is ControllerErrorCategory.BOND_NOT_FOUND


def test_existing_profile_path_is_not_reported_as_pairing_timeout() -> None:
    async def reject_existing_profile(**_kwargs: object) -> FailingGamepad:
        raise FileExistsError

    adapter = SwbtControllerAdapter(profile_creator=reject_existing_profile)

    with pytest.raises(ControllerAdapterError) as raised:
        asyncio.run(
            adapter.start_pairing(
                "usb:0",
                Path("existing-profile.json"),
                30.0,
                ControllerColorSettings(),
            )
        )

    assert raised.value.category is ControllerErrorCategory.PAIRING_PROFILE_EXISTS


def test_pairing_timeout_and_transport_open_errors_are_classified() -> None:
    async def fail_profile_creation(**_kwargs: object) -> FailingGamepad:
        raise ConnectionTimeoutError

    pairing_adapter = SwbtControllerAdapter(profile_creator=fail_profile_creation)
    with pytest.raises(ControllerAdapterError) as pairing_raised:
        asyncio.run(
            pairing_adapter.start_pairing(
                "usb:0",
                Path("bond.json"),
                30.0,
                ControllerColorSettings(),
            )
        )

    open_gamepad = FailingGamepad(open_error=TransportOpenError())
    open_adapter = SwbtControllerAdapter(gamepad_factory=lambda **_kwargs: open_gamepad)
    with pytest.raises(ControllerAdapterError) as open_raised:
        asyncio.run(
            open_adapter.connect_saved(
                "usb:0",
                Path("bond.json"),
                30.0,
                ControllerColorSettings(),
            )
        )

    assert pairing_raised.value.category is ControllerErrorCategory.PAIRING_TIMEOUT
    assert open_raised.value.category is ControllerErrorCategory.ADAPTER_OPEN_FAILED


def test_invalid_input_from_send_is_classified_as_invalid_input() -> None:
    gamepad = FailingGamepad(send_error=InvalidInputError())
    adapter = SwbtControllerAdapter(gamepad_factory=lambda **_kwargs: gamepad)

    async def exercise() -> None:
        await adapter.connect_saved(
            "usb:0",
            Path("bond.json"),
            30.0,
            ControllerColorSettings(),
        )
        await adapter.send_frame(frame())

    with pytest.raises(ControllerAdapterError) as raised:
        asyncio.run(exercise())

    assert raised.value.category is ControllerErrorCategory.INVALID_INPUT
