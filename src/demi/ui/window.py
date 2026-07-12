"""Window specifications and the pyglet window factory."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from pyglet import app as pyglet_app
from pyglet import clock as pyglet_clock
from pyglet.graphics import Batch
from pyglet.text import Label
from pyglet.window import Window

from demi.application.coordinator import CaptureCoordinator
from demi.application.state import ConnectionState
from demi.domain.errors import DomainValueError
from demi.input.publisher import InputPublisher
from demi.input.pyglet_backend import PygletInputBackend

from .controller_view import ControllerView
from .status_bar import StatusBar
from .toolbar import Toolbar


@dataclass(frozen=True, slots=True)
class WindowSpec:
    """Validated dimensions and creation options for the main window.

    Raises:
        DomainValueError: A dimension or option violates the window contract.
    """

    width: int = 960
    height: int = 640
    min_width: int = 800
    min_height: int = 520
    caption: str = "Project Demi"
    resizable: bool = True
    visible: bool = False
    vsync: bool = True

    def __post_init__(self) -> None:
        """Validate window dimensions and creation flags."""
        values = (self.width, self.height, self.min_width, self.min_height)
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise DomainValueError
        if self.width < self.min_width or self.height < self.min_height:
            raise DomainValueError
        if self.min_width < 1 or self.min_height < 1:
            raise DomainValueError
        if not isinstance(self.caption, str) or not self.caption.strip():
            raise DomainValueError
        if not isinstance(self.resizable, bool) or not isinstance(self.visible, bool):
            raise DomainValueError
        if not isinstance(self.vsync, bool):
            raise DomainValueError


class PygletWindowPort(Protocol):
    """Window operations consumed by the application event bridge."""

    width: int
    height: int

    def push_handlers(self, *objects: object) -> None:
        """Register event handler objects."""

    def clear(self) -> None:
        """Clear the current drawing surface."""

    def set_visible(self, visible: bool = True) -> None:
        """Show or hide the configured window."""


class ClockScheduler(Protocol):
    """Subset of pyglet clock scheduling used by the application."""

    def schedule_interval(self, callback: Callable[[float], None], interval: float) -> None:
        """Schedule a callback at a fixed interval."""

    def unschedule(self, callback: Callable[[float], None]) -> None:
        """Remove a previously scheduled callback."""


def create_window(spec: WindowSpec | None = None) -> Window:
    """Create a pyglet window from a validated window specification.

    Args:
        spec: Dimensions and creation options for the main window.

    Returns:
        A configured pyglet window with the minimum size applied.

    Raises:
        DomainValueError: The window specification is invalid.
        Exception: Pyglet raises an environment-specific error when a display
            or OpenGL context cannot be created.
    """
    if spec is None:
        spec = WindowSpec()

    window = Window(
        width=spec.width,
        height=spec.height,
        caption=spec.caption,
        resizable=spec.resizable,
        visible=spec.visible,
        vsync=spec.vsync,
    )
    window.set_minimum_size(spec.min_width, spec.min_height)
    return window


class PygletApplication:
    """Connect the window, input backend, publisher, and view on one thread."""

    def __init__(
        self,
        *,
        window: PygletWindowPort,
        coordinator: CaptureCoordinator,
        backend: PygletInputBackend,
        view: ControllerView,
        toolbar: Toolbar,
        status_bar: StatusBar,
        clock: ClockScheduler | None = None,
        connection_state: ConnectionState = ConnectionState.READY,
        adapter_label: str = "なし",
    ) -> None:
        """Initialize the main-thread application event bridge."""
        self._window = window
        self._coordinator = coordinator
        self._backend = backend
        self._view = view
        self._toolbar = toolbar
        self._status_bar = status_bar
        self._clock = clock if clock is not None else pyglet_clock
        self._connection_state = connection_state
        self._adapter_label = adapter_label
        self._started = False
        self._chrome_batch: Batch | None = None
        self._toolbar_label: Label | None = None
        self._status_label: Label | None = None

    @property
    def started(self) -> bool:
        """Return whether the application callback is scheduled."""
        return self._started

    def start(self) -> None:
        """Install event handlers and schedule 8ms input evaluation."""
        if self._started:
            return
        self._backend.install(self._window)
        self._window.push_handlers(self)
        self._clock.schedule_interval(
            self._evaluate,
            InputPublisher.evaluation_interval_ms / 1000.0,
        )
        self._window.set_visible(True)
        self._started = True

    def stop(self) -> None:
        """Unschedule evaluation and leave capture in a neutral state."""
        if not self._started:
            return
        self._clock.unschedule(self._evaluate)
        self._coordinator.stop_capture()
        self._started = False

    def run(self) -> None:
        """Start the application and enter pyglet's default event loop."""
        self.start()
        pyglet_app.run()

    def toggle_capture(self) -> bool:
        """Start or stop capture through the coordinator-owned transition."""
        return self._coordinator.toggle_capture()

    def on_draw(self) -> None:
        """Render the latest frame and the toolbar/status text."""
        frame = self._coordinator.last_frame
        if frame is not None:
            self._view.update(frame)
        self._sync_chrome()
        self._window.clear()
        self._view.draw(float(self._window.width), float(self._window.height))
        self._draw_chrome()

    def on_close(self) -> None:
        """Stop scheduled evaluation when the window is closing."""
        self.stop()

    def _evaluate(self, dt_seconds: float) -> None:
        del dt_seconds
        self._coordinator.evaluate()

    def _sync_chrome(self) -> None:
        self._toolbar.update(
            app_state=self._coordinator.app_state,
            connection_state=self._connection_state,
            focused=self._coordinator.focused,
            dialog_open=False,
        )
        self._status_bar.update(
            adapter_label=self._adapter_label,
            connection_state=self._connection_state,
            app_state=self._coordinator.app_state,
            preview_only=self._coordinator.is_captured
            and self._connection_state is not ConnectionState.CONNECTED,
        )

    def _draw_chrome(self) -> None:
        if self._chrome_batch is None:
            self._chrome_batch = Batch()
            self._toolbar_label = Label(
                "",
                x=16,
                y=self._window.height - 32,
                batch=self._chrome_batch,
            )
            self._status_label = Label("", x=16, y=12, batch=self._chrome_batch)
        if self._toolbar_label is not None:
            self._toolbar_label.text = (
                f"{self._toolbar.model.connection_label}  "
                f"[{self._toolbar.model.connection_action_label}]  "
                f"[{self._toolbar.model.capture_label}]"
            )
            self._toolbar_label.y = self._window.height - 32
        if self._status_label is not None:
            self._status_label.text = self._status_bar.model.text
        if self._chrome_batch is not None:
            self._chrome_batch.draw()
