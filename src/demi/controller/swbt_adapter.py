"""swbt-python public API adapter for the controller runtime."""

from collections.abc import Callable
from pathlib import Path
from typing import NoReturn, Protocol

from swbt import (
    AdapterDiscoveryError,
    AdapterInfo,
    Button,
    ClosedError,
    ConnectionFailedError,
    ConnectionTimeoutError,
    ControllerColors,
    DirectProController,
    IMUFrame,
    InputState,
    InvalidInputError,
    InvalidKeyStoreError,
    Stick,
    SwbtError,
    TransportOpenError,
    list_adapters,
)

from demi.controller.adapter import ControllerAdapter, ControllerAdapterError
from demi.controller.events import AdapterDescriptor, ControllerErrorCategory
from demi.domain.controller import ControllerFrame, LogicalButton
from demi.domain.settings import ControllerColorSettings


class SwbtGamepad(Protocol):
    """Public swbt gamepad operations used by the adapter."""

    async def open(self) -> None:
        """Open the configured transport."""

    async def reconnect(self, timeout: float | None = None) -> None:  # noqa: ASYNC109
        """Reconnect through an existing bond."""

    async def connect(
        self,
        *,
        timeout: float | None = None,  # noqa: ASYNC109
        allow_pairing: bool = False,
    ) -> None:
        """Connect through reconnect and optional pairing."""

    async def send(self, state: InputState) -> None:
        """Send one complete input state and wait for completion."""

    async def close(self, *, neutral: bool = True) -> None:
        """Close the gamepad and optionally send neutral."""


type GamepadFactory = Callable[..., SwbtGamepad]
type AdapterLister = Callable[[], tuple[AdapterInfo, ...]]


_BUTTON_MAP: dict[LogicalButton, Button] = {
    LogicalButton.A: Button.A,
    LogicalButton.B: Button.B,
    LogicalButton.X: Button.X,
    LogicalButton.Y: Button.Y,
    LogicalButton.L: Button.L,
    LogicalButton.R: Button.R,
    LogicalButton.ZL: Button.ZL,
    LogicalButton.ZR: Button.ZR,
    LogicalButton.PLUS: Button.PLUS,
    LogicalButton.MINUS: Button.MINUS,
    LogicalButton.HOME: Button.HOME,
    LogicalButton.CAPTURE: Button.CAPTURE,
    LogicalButton.LEFT_STICK: Button.LEFT_STICK,
    LogicalButton.RIGHT_STICK: Button.RIGHT_STICK,
    LogicalButton.DPAD_UP: Button.DPAD_UP,
    LogicalButton.DPAD_DOWN: Button.DPAD_DOWN,
    LogicalButton.DPAD_LEFT: Button.DPAD_LEFT,
    LogicalButton.DPAD_RIGHT: Button.DPAD_RIGHT,
}


class SwbtControllerAdapter(ControllerAdapter):
    """Adapt Project_Demi values to swbt-python public values."""

    def __init__(
        self,
        *,
        gamepad_factory: GamepadFactory = DirectProController,
        adapter_lister: AdapterLister = list_adapters,
    ) -> None:
        """Initialize an adapter with injectable public-API boundaries.

        Args:
            gamepad_factory: Public swbt gamepad constructor.
            adapter_lister: Public swbt adapter discovery function.
        """
        self._gamepad_factory = gamepad_factory
        self._adapter_lister = adapter_lister
        self._gamepad: SwbtGamepad | None = None
        self._adapter_id: str | None = None
        self._bond_path: Path | None = None
        self._colors: ControllerColorSettings | None = None
        self._timeout_seconds: float | None = None

    async def discover_adapters(self) -> tuple[AdapterDescriptor, ...]:
        """List USB Bluetooth candidates without opening a controller."""
        try:
            return tuple(self._descriptor(info) for info in self._adapter_lister())
        except Exception as error:  # noqa: BLE001
            _raise_adapter_failure(error, ControllerErrorCategory.ADAPTER_OPEN_FAILED)

    async def connect_saved(
        self,
        adapter_id: str,
        bond_path: Path,
        timeout_seconds: float,
        colors: ControllerColorSettings,
    ) -> None:
        """Open a controller and reconnect without pairing."""
        try:
            await self._connect_controller(adapter_id, bond_path, colors)
            self._timeout_seconds = timeout_seconds
            gamepad = self._require_gamepad()
            await gamepad.reconnect(timeout=timeout_seconds)
        except Exception as error:  # noqa: BLE001
            await self._discard_failed_gamepad()
            _raise_adapter_failure(error, ControllerErrorCategory.RECONNECT_FAILED)

    async def start_pairing(
        self,
        adapter_id: str,
        bond_path: Path,
        timeout_seconds: float,
        colors: ControllerColorSettings,
    ) -> None:
        """Open a controller and allow explicit pairing."""
        try:
            await self._connect_controller(adapter_id, bond_path, colors)
            self._timeout_seconds = timeout_seconds
            gamepad = self._require_gamepad()
            await gamepad.connect(timeout=timeout_seconds, allow_pairing=True)
        except Exception as error:  # noqa: BLE001
            await self._discard_failed_gamepad()
            _raise_adapter_failure(error, ControllerErrorCategory.PAIRING_TIMEOUT)

    async def disconnect(self) -> None:
        """Close the current gamepad with a final neutral attempt."""
        gamepad = self._gamepad
        if gamepad is None:
            return
        try:
            await gamepad.close(neutral=True)
        except Exception as error:  # noqa: BLE001
            _raise_adapter_failure(error, ControllerErrorCategory.CONNECTION_LOST)
        finally:
            self._clear_gamepad()

    async def recreate_with_colors(self, colors: ControllerColorSettings) -> None:
        """Recreate and reconnect the current saved controller with new colors."""
        adapter_id = self._adapter_id
        bond_path = self._bond_path
        timeout_seconds = self._timeout_seconds
        if adapter_id is None or bond_path is None:
            return
        await self.disconnect()
        await self.connect_saved(adapter_id, bond_path, timeout_seconds or 30.0, colors)

    async def send_frame(self, frame: ControllerFrame) -> None:
        """Convert and send one complete Project_Demi frame."""
        try:
            await self._require_gamepad().send(frame_to_input_state(frame))
        except Exception as error:  # noqa: BLE001
            _raise_adapter_failure(error, ControllerErrorCategory.CONNECTION_LOST)

    async def close(self) -> None:
        """Release the current gamepad idempotently."""
        await self.disconnect()

    async def _connect_controller(
        self,
        adapter_id: str,
        bond_path: Path,
        colors: ControllerColorSettings,
    ) -> None:
        if self._gamepad is not None:
            await self.disconnect()
        self._gamepad = self._gamepad_factory(
            adapter=adapter_id,
            key_store_path=str(bond_path),
            controller_colors=to_swbt_colors(colors),
        )
        self._adapter_id = adapter_id
        self._bond_path = bond_path
        self._colors = colors
        try:
            await self._gamepad.open()
        except Exception:
            await self._discard_failed_gamepad()
            raise

    async def _discard_failed_gamepad(self) -> None:
        gamepad = self._gamepad
        try:
            if gamepad is not None:
                await gamepad.close(neutral=True)
        except Exception:  # noqa: BLE001
            return
        finally:
            self._clear_gamepad()

    def _require_gamepad(self) -> SwbtGamepad:
        if self._gamepad is None:
            raise RuntimeError
        return self._gamepad

    def _clear_gamepad(self) -> None:
        self._gamepad = None
        self._adapter_id = None
        self._bond_path = None
        self._colors = None
        self._timeout_seconds = None

    @staticmethod
    def _descriptor(info: AdapterInfo) -> AdapterDescriptor:
        display_name = info.product or info.manufacturer or info.name
        metadata: list[tuple[str, str]] = []
        if info.manufacturer is not None:
            metadata.append(("manufacturer", info.manufacturer))
        if info.product is not None:
            metadata.append(("product", info.product))
        if info.vendor_id is not None:
            metadata.append(("vendor_id", f"{info.vendor_id:04x}"))
        if info.product_id is not None:
            metadata.append(("product_id", f"{info.product_id:04x}"))
        return AdapterDescriptor(
            id=info.name,
            display_name=display_name,
            transport="usb",
            metadata=tuple(metadata),
        )


def frame_to_input_state(frame: ControllerFrame) -> InputState:
    """Convert a domain frame through swbt public physical-unit constructors."""
    buttons = frozenset(_BUTTON_MAP[button] for button in frame.buttons)
    imu = IMUFrame.gyro_rate(
        x_rad_s=frame.gyro_rate.x_radians_per_second,
        y_rad_s=frame.gyro_rate.y_radians_per_second,
        z_rad_s=frame.gyro_rate.z_radians_per_second,
    ).with_accel_g(
        x_g=frame.accel_g.x_g,
        y_g=frame.accel_g.y_g,
        z_g=frame.accel_g.z_g,
    )
    return InputState(
        buttons=buttons,
        left_stick=Stick.normalized(x=frame.left_stick.x, y=frame.left_stick.y),
        right_stick=Stick.normalized(x=frame.right_stick.x, y=frame.right_stick.y),
        imu_frames=(imu, imu, imu),
    )


def to_swbt_colors(colors: ControllerColorSettings) -> ControllerColors:
    """Convert validated Project_Demi colors to swbt RGB integers."""
    return ControllerColors(
        body=_hex_color(colors.body),
        buttons=_hex_color(colors.buttons),
        left_grip=_hex_color(colors.left_grip),
        right_grip=_hex_color(colors.right_grip),
    )


def _hex_color(value: str) -> int:
    return int(value.removeprefix("#"), 16)


def _raise_adapter_failure(
    error: Exception,
    fallback: ControllerErrorCategory,
) -> NoReturn:
    """Raise a safe adapter failure classified from a swbt exception."""
    if isinstance(error, (AdapterDiscoveryError, TransportOpenError)):
        category = ControllerErrorCategory.ADAPTER_OPEN_FAILED
    elif isinstance(error, InvalidKeyStoreError):
        category = ControllerErrorCategory.BOND_NOT_FOUND
    elif isinstance(error, InvalidInputError):
        category = ControllerErrorCategory.INVALID_INPUT
    elif isinstance(error, (ClosedError, ConnectionFailedError, ConnectionTimeoutError, SwbtError)):
        category = fallback
    else:
        category = fallback
    raise ControllerAdapterError(category) from error
