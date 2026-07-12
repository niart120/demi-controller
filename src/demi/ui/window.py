"""Window specifications and the pyglet window factory."""

from dataclasses import dataclass

from pyglet.window import Window

from demi.domain.errors import DomainValueError


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
