"""ControllerFrame display model and pyglet drawing boundary."""

from dataclasses import dataclass
from typing import Protocol, cast

from pyglet import shapes
from pyglet.graphics import Batch
from pyglet.text import Label

from demi.domain.controller import AccelG, ControllerFrame, GyroRate, LogicalButton, StickVector
from demi.domain.settings import ControllerColorSettings


@dataclass(frozen=True, slots=True)
class ControllerViewModel:
    """Immutable values rendered by the controller view."""

    buttons: frozenset[LogicalButton]
    left_stick: StickVector
    right_stick: StickVector
    gyro_rate: GyroRate
    accel_g: AccelG
    capture_active: bool

    @classmethod
    def from_frame(cls, frame: ControllerFrame) -> "ControllerViewModel":
        """Create display values from one complete controller frame."""
        return cls(
            buttons=frame.buttons,
            left_stick=frame.left_stick,
            right_stick=frame.right_stick,
            gyro_rate=frame.gyro_rate,
            accel_g=frame.accel_g,
            capture_active=frame.capture_active,
        )

    @classmethod
    def neutral(cls) -> "ControllerViewModel":
        """Return the display model for a capture-inactive neutral frame."""
        return cls(
            buttons=frozenset(),
            left_stick=StickVector(x=0.0, y=0.0),
            right_stick=StickVector(x=0.0, y=0.0),
            gyro_rate=GyroRate(0.0, 0.0, 0.0),
            accel_g=AccelG(0.0, 0.0, 1.0),
            capture_active=False,
        )


class ColorShape(Protocol):
    """Subset of a pyglet shape used for pressed-state updates."""

    @property
    def color(self) -> tuple[int, ...]:
        """Return the shape color."""

    @color.setter
    def color(self, value: tuple[int, ...]) -> None:
        """Set the shape color."""

    def delete(self) -> None:
        """Delete the underlying pyglet shape."""


def _rgb(value: str) -> tuple[int, int, int]:
    return (
        int(value[1:3], 16),
        int(value[3:5], 16),
        int(value[5:7], 16),
    )


class ControllerView:
    """Render a controller state from the latest ``ControllerFrame`` only."""

    def __init__(
        self,
        *,
        colors: ControllerColorSettings | None = None,
        batch: Batch | None = None,
    ) -> None:
        """Initialize a display model and an optional pyglet batch."""
        self._colors = colors if colors is not None else ControllerColorSettings()
        self._model = ControllerViewModel.neutral()
        self._batch = batch
        self._layout: tuple[float, float] | None = None
        self._static_shapes: list[shapes.ShapeBase] = []
        self._button_shapes: dict[LogicalButton, ColorShape] = {}
        self._left_knob: shapes.Circle | None = None
        self._right_knob: shapes.Circle | None = None
        self._left_center = (0.0, 0.0)
        self._right_center = (0.0, 0.0)
        self._stick_radius = 1.0
        self._gyro_label: Label | None = None
        self._accel_label: Label | None = None
        self._capture_label: Label | None = None

    @property
    def model(self) -> ControllerViewModel:
        """Return the latest frame-derived display model."""
        return self._model

    def update(self, frame: ControllerFrame) -> None:
        """Replace the display model with values from one controller frame."""
        self._model = ControllerViewModel.from_frame(frame)

    def draw(self, width: float, height: float) -> None:
        """Draw the current model using reusable pyglet shapes and labels.

        Args:
            width: Current drawable width in pixels.
            height: Current drawable height in pixels.
        """
        if width <= 0 or height <= 0:
            return
        if self._batch is None:
            self._batch = Batch()
        if self._layout != (width, height):
            self._clear_renderables()
            self._build_renderables(width, height)
            self._layout = (width, height)
        self._update_renderables()
        self._batch.draw()

    def _clear_renderables(self) -> None:
        for drawable in self._static_shapes:
            drawable.delete()
        for drawable in self._button_shapes.values():
            drawable.delete()
        for drawable in (self._left_knob, self._right_knob):
            if drawable is not None:
                drawable.delete()
        for label in (self._gyro_label, self._accel_label, self._capture_label):
            if label is not None:
                label.delete()
        self._static_shapes.clear()
        self._button_shapes.clear()
        self._left_knob = None
        self._right_knob = None
        self._gyro_label = None
        self._accel_label = None
        self._capture_label = None

    def _build_renderables(self, width: float, height: float) -> None:
        batch = self._batch
        if batch is None:
            return
        body_width = min(width * 0.72, 560.0)
        body_height = min(height * 0.46, 300.0)
        body_x = (width - body_width) / 2.0
        body_y = height * 0.28
        body_color = _rgb(self._colors.body)
        left_grip_color = _rgb(self._colors.left_grip)
        right_grip_color = _rgb(self._colors.right_grip)
        button_color = _rgb(self._colors.buttons)

        self._static_shapes.extend(
            (
                shapes.Rectangle(
                    body_x,
                    body_y,
                    body_width,
                    body_height,
                    color=body_color,
                    batch=batch,
                ),
                shapes.Rectangle(
                    body_x - body_width * 0.08,
                    body_y - body_height * 0.16,
                    body_width * 0.2,
                    body_height * 0.55,
                    color=left_grip_color,
                    batch=batch,
                ),
                shapes.Rectangle(
                    body_x + body_width * 0.88,
                    body_y - body_height * 0.16,
                    body_width * 0.2,
                    body_height * 0.55,
                    color=right_grip_color,
                    batch=batch,
                ),
            )
        )
        self._left_center = (body_x + body_width * 0.25, body_y + body_height * 0.48)
        self._right_center = (body_x + body_width * 0.75, body_y + body_height * 0.48)
        self._stick_radius = min(body_width, body_height) * 0.1
        for center_x, center_y in (self._left_center, self._right_center):
            self._static_shapes.append(
                shapes.Circle(
                    center_x,
                    center_y,
                    self._stick_radius * 1.5,
                    color=button_color,
                    batch=batch,
                )
            )
        self._left_knob = shapes.Circle(
            self._left_center[0],
            self._left_center[1],
            self._stick_radius * 0.65,
            color=button_color,
            batch=batch,
        )
        self._right_knob = shapes.Circle(
            self._right_center[0],
            self._right_center[1],
            self._stick_radius * 0.65,
            color=button_color,
            batch=batch,
        )

        button_positions = {
            LogicalButton.A: (body_x + body_width * 0.83, body_y + body_height * 0.62),
            LogicalButton.B: (body_x + body_width * 0.75, body_y + body_height * 0.50),
            LogicalButton.X: (body_x + body_width * 0.75, body_y + body_height * 0.74),
            LogicalButton.Y: (body_x + body_width * 0.67, body_y + body_height * 0.62),
            LogicalButton.L: (body_x + body_width * 0.18, body_y + body_height * 0.90),
            LogicalButton.R: (body_x + body_width * 0.82, body_y + body_height * 0.90),
            LogicalButton.ZL: (body_x + body_width * 0.27, body_y + body_height * 0.90),
            LogicalButton.ZR: (body_x + body_width * 0.73, body_y + body_height * 0.90),
            LogicalButton.PLUS: (body_x + body_width * 0.63, body_y + body_height * 0.86),
            LogicalButton.MINUS: (body_x + body_width * 0.37, body_y + body_height * 0.86),
            LogicalButton.HOME: (body_x + body_width * 0.63, body_y + body_height * 0.30),
            LogicalButton.CAPTURE: (body_x + body_width * 0.37, body_y + body_height * 0.30),
            LogicalButton.LEFT_STICK: self._left_center,
            LogicalButton.RIGHT_STICK: self._right_center,
            LogicalButton.DPAD_UP: (body_x + body_width * 0.16, body_y + body_height * 0.67),
            LogicalButton.DPAD_DOWN: (body_x + body_width * 0.16, body_y + body_height * 0.43),
            LogicalButton.DPAD_LEFT: (body_x + body_width * 0.12, body_y + body_height * 0.55),
            LogicalButton.DPAD_RIGHT: (body_x + body_width * 0.20, body_y + body_height * 0.55),
        }
        for button, (x, y) in button_positions.items():
            self._button_shapes[button] = cast(
                "ColorShape",
                shapes.Circle(
                    x,
                    y,
                    self._stick_radius * 0.4,
                    color=button_color,
                    batch=batch,
                ),
            )

        label_color = (*button_color, 255)
        self._capture_label = Label(
            "IDLE",
            x=body_x,
            y=body_y + body_height + 24,
            color=label_color,
            batch=batch,
        )
        self._gyro_label = Label(
            "Gyro 0.00, 0.00, 0.00 rad/s",
            x=body_x,
            y=body_y - 28,
            color=label_color,
            batch=batch,
        )
        self._accel_label = Label(
            "Accel 0.00, 0.00, 1.00 G",
            x=body_x,
            y=body_y - 48,
            color=label_color,
            batch=batch,
        )

    def _update_renderables(self) -> None:
        if self._left_knob is None or self._right_knob is None:
            return
        self._left_knob.x = self._left_center[0] + self._model.left_stick.x * self._stick_radius
        self._left_knob.y = self._left_center[1] + self._model.left_stick.y * self._stick_radius
        self._right_knob.x = self._right_center[0] + self._model.right_stick.x * self._stick_radius
        self._right_knob.y = self._right_center[1] + self._model.right_stick.y * self._stick_radius
        button_color = (*_rgb(self._colors.buttons), 255)
        pressed_color = (*tuple(255 - value for value in button_color[:3]), 255)
        for button, shape in self._button_shapes.items():
            shape.color = pressed_color if button in self._model.buttons else button_color
        if self._capture_label is not None:
            self._capture_label.text = "CAPTURED" if self._model.capture_active else "IDLE"
        if self._gyro_label is not None:
            gyro = self._model.gyro_rate
            self._gyro_label.text = (
                f"Gyro {gyro.x_radians_per_second:.2f}, "
                f"{gyro.y_radians_per_second:.2f}, {gyro.z_radians_per_second:.2f} rad/s"
            )
        if self._accel_label is not None:
            accel = self._model.accel_g
            self._accel_label.text = f"Accel {accel.x_g:.2f}, {accel.y_g:.2f}, {accel.z_g:.2f} G"
