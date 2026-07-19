"""Adapter and event-sink protocols owned by the runtime boundary."""

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from demi.controller.events import AdapterDescriptor, ControllerErrorCategory, RuntimeEvent
from demi.domain.controller import ControllerFrame
from demi.domain.settings import ControllerColorSettings


class ControllerAdapterError(Exception):
    """Safe failure raised by a concrete adapter at the runtime boundary."""

    def __init__(self, category: ControllerErrorCategory) -> None:
        """Create a failure without exposing a lower-layer exception type."""
        self.category = category
        super().__init__(category.value)


class ControllerAdapter(Protocol):
    """Async controller operations executed only on the worker thread."""

    async def discover_adapters(self) -> tuple[AdapterDescriptor, ...]:
        """Discover available adapters."""

    async def connect_saved(
        self,
        adapter_id: str,
        bond_path: Path,
        timeout_seconds: float,
        colors: ControllerColorSettings,
    ) -> None:
        """Connect to a saved bond without pairing."""

    async def start_pairing(
        self,
        adapter_id: str,
        bond_path: Path,
        timeout_seconds: float,
        colors: ControllerColorSettings,
    ) -> None:
        """Start an explicitly requested pairing operation."""

    async def disconnect(self) -> None:
        """Disconnect the active controller."""

    async def recreate_with_colors(self, colors: ControllerColorSettings) -> None:
        """Recreate the controller using new colors."""

    async def send_frame(self, frame: ControllerFrame) -> None:
        """Send one complete Project_Demi controller frame."""

    async def close(self) -> None:
        """Release all adapter resources."""


class RuntimeEventSink(Protocol):
    """Destination for worker-thread runtime events."""

    def emit(self, event: RuntimeEvent) -> None:
        """Receive one immutable runtime event."""


type ControllerAdapterFactory = Callable[[], ControllerAdapter]
