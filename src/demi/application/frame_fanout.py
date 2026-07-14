"""Deliver one evaluated controller frame to runtime and preview boundaries."""

from typing import Protocol, runtime_checkable

from demi.domain.controller import ControllerFrame
from demi.domain.settings import ControllerColorSettings


class RuntimeFrameSink(Protocol):
    """Accept the latest controller frame for controller I/O."""

    def offer_frame(self, frame: ControllerFrame) -> bool | None:
        """Offer one immutable frame to the runtime boundary."""


@runtime_checkable
class FramePreviewPort(Protocol):
    """Accept one complete frame for display without reevaluating input."""

    def set_frame(self, frame: ControllerFrame) -> None:
        """Store one evaluated frame for later UI rendering."""


@runtime_checkable
class ControllerColorPreviewPort(Protocol):
    """Accept the four validated colors used by a controller preview."""

    def set_controller_colors(self, colors: ControllerColorSettings) -> None:
        """Apply saved colors without changing the current input frame."""


class ControllerFrameFanout:
    """Offer the same immutable frame to the runtime and optional preview."""

    def __init__(
        self,
        *,
        runtime: RuntimeFrameSink,
        preview: FramePreviewPort | None = None,
    ) -> None:
        """Create one fan-out boundary around existing output ports.

        Args:
            runtime: Controller I/O destination for every evaluated frame.
            preview: Optional UI destination that observes the same frame object.
        """
        self._runtime = runtime
        self._preview = preview

    def offer_frame(self, frame: ControllerFrame) -> bool | None:
        """Offer one frame to both destinations without constructing another frame.

        Args:
            frame: Immutable controller state from one input evaluation.

        Returns:
            The runtime destination's acceptance result.
        """
        result = self._runtime.offer_frame(frame)
        preview = self._preview
        if preview is not None:
            preview.set_frame(frame)
        return result
