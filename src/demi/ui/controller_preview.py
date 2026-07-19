"""QPainter controller preview backed by a complete immutable controller frame."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from PySide6.QtCore import QCoreApplication, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from demi.domain.controller import AccelG, ControllerFrame, GyroRate, LogicalButton, StickVector
from demi.domain.settings import ControllerColorSettings
from demi.ui.preview_layout import (
    CONTROL_IDS,
    PreviewRect,
    normalized_stick_position,
    preview_layout,
)
from demi.ui.preview_sensor import SensorDisplay, accel_display, gyro_display

type RepaintRequest = Callable[[], object]


class PreviewClock(Protocol):
    """Provide the monotonic time used to limit preview repaint requests."""

    def monotonic_ns(self) -> int:
        """Return the current monotonic time in nanoseconds."""


class SystemPreviewClock:
    """Read repaint timestamps from the process monotonic clock."""

    def monotonic_ns(self) -> int:
        """Return the current process monotonic timestamp."""
        return time.perf_counter_ns()


class PreviewRepaintLimiter:
    """Allow asynchronous preview repaint requests no more than a fixed rate."""

    def __init__(self, *, clock: PreviewClock, maximum_hz: int = 60) -> None:
        """Create a repaint limiter with a monotonic clock.

        Args:
            clock: Monotonic timestamp source, injectable for deterministic tests.
            maximum_hz: Maximum allowed asynchronous repaint request rate.

        Raises:
            ValueError: If the requested rate is not a positive integer.
        """
        if isinstance(maximum_hz, bool) or not isinstance(maximum_hz, int) or maximum_hz <= 0:
            raise ValueError
        self._clock = clock
        self._minimum_interval_ns = (1_000_000_000 + maximum_hz - 1) // maximum_hz
        self._last_request_ns: int | None = None

    def allows_repaint(self) -> bool:
        """Return whether the current time may issue an asynchronous repaint request."""
        now_ns = self._clock.monotonic_ns()
        last_request_ns = self._last_request_ns
        if last_request_ns is not None and now_ns - last_request_ns < self._minimum_interval_ns:
            return False
        self._last_request_ns = now_ns
        return True


@dataclass(frozen=True, slots=True)
class ControllerPreviewModel:
    """Display-only values derived from one frame and four controller colors."""

    body_color: str
    buttons_color: str
    left_grip_color: str
    right_grip_color: str
    pressed_buttons: frozenset[LogicalButton]
    pressed_control_ids: frozenset[str]
    left_stick: StickVector
    right_stick: StickVector
    left_stick_position: tuple[float, float]
    right_stick_position: tuple[float, float]
    gyro_rate: GyroRate
    accel_g: AccelG
    gyro_display: SensorDisplay
    accel_display: SensorDisplay
    capture_active: bool
    pointer_capture_active: bool
    control_ids: frozenset[str]


def controller_preview_model(
    frame: ControllerFrame,
    colors: ControllerColorSettings,
) -> ControllerPreviewModel:
    """Build a Qt-free model from one evaluated frame and validated colors.

    Args:
        frame: Complete immutable state from input evaluation.
        colors: Four validated controller colors selected by the user.

    Returns:
        The values that a controller preview needs to render one frame.
    """
    return ControllerPreviewModel(
        body_color=colors.body,
        buttons_color=colors.buttons,
        left_grip_color=colors.left_grip,
        right_grip_color=colors.right_grip,
        pressed_buttons=frame.buttons,
        pressed_control_ids=frozenset(_control_id(button) for button in frame.buttons),
        left_stick=frame.left_stick,
        right_stick=frame.right_stick,
        left_stick_position=normalized_stick_position(frame.left_stick.x, frame.left_stick.y),
        right_stick_position=normalized_stick_position(frame.right_stick.x, frame.right_stick.y),
        gyro_rate=frame.gyro_rate,
        accel_g=frame.accel_g,
        gyro_display=gyro_display(frame.gyro_rate),
        accel_display=accel_display(frame.accel_g),
        capture_active=frame.capture_active,
        pointer_capture_active=frame.pointer_capture_active,
        control_ids=CONTROL_IDS,
    )


def _control_id(button: LogicalButton) -> str:
    if button is LogicalButton.LEFT_STICK:
        return "left_stick_click"
    if button is LogicalButton.RIGHT_STICK:
        return "right_stick_click"
    return button.value.lower()


class ControllerPreviewWidget(QWidget):
    """Render a controller-state model without changing input or runtime state."""

    def __init__(
        self,
        *,
        colors: ControllerColorSettings | None = None,
        parent: QWidget | None = None,
        clock: PreviewClock | None = None,
        on_repaint_requested: RepaintRequest | None = None,
    ) -> None:
        """Create a preview with validated colors and no initial controller frame.

        Args:
            colors: Initial controller colors, defaulting to application defaults.
            parent: Optional Qt owner for widget lifetime.
            clock: Monotonic source used to limit frame-driven repaint requests.
            on_repaint_requested: Optional asynchronous repaint request boundary.
        """
        super().__init__(parent)
        self._colors = colors if colors is not None else ControllerColorSettings()
        self._frame: ControllerFrame | None = None
        self._model: ControllerPreviewModel | None = None
        self._repaint_limiter = PreviewRepaintLimiter(
            clock=clock if clock is not None else SystemPreviewClock()
        )
        self._on_repaint_requested = (
            on_repaint_requested
            if on_repaint_requested is not None
            else self._request_widget_repaint
        )
        self.setMinimumSize(480, 300)
        self.setMouseTracking(True)

    @property
    def model(self) -> ControllerPreviewModel | None:
        """Return the latest display-only model without recomputing input."""
        return self._model

    def set_frame(self, frame: ControllerFrame) -> None:
        """Store one complete evaluated frame and request an asynchronous repaint.

        Args:
            frame: Immutable controller state shared with the runtime boundary.
        """
        self._frame = frame
        self._model = controller_preview_model(frame, self._colors)
        sensor_description = _sensor_description(frame)
        self.setToolTip(sensor_description)
        self.setAccessibleDescription(sensor_description)
        if self._repaint_limiter.allows_repaint():
            self._on_repaint_requested()

    def set_colors(self, colors: ControllerColorSettings) -> None:
        """Apply four validated colors without changing the current input frame.

        Args:
            colors: Replacement display colors selected by the UI.
        """
        self._colors = colors
        frame = self._frame
        if frame is not None:
            self._model = controller_preview_model(frame, colors)
        self._on_repaint_requested()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 - Qt override name.
        """Render the saved model without updating domain, runtime, or settings state."""
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#181818"))
        model = self._model
        if model is not None:
            self._draw_model(painter, model)
        painter.end()

    def _draw_model(self, painter: QPainter, model: ControllerPreviewModel) -> None:
        canvas_width = self.width()
        canvas_height = self.height()
        layout = preview_layout(canvas_width, canvas_height)
        body = QRectF(
            canvas_width * 0.04,
            canvas_height * 0.16,
            canvas_width * 0.92,
            canvas_height * 0.62,
        )
        painter.setPen(QPen(QColor("#E0E0E0"), 2.0))
        painter.setBrush(QColor(model.body_color))
        painter.drawRoundedRect(body, 36.0, 36.0)
        for control_id, bounds in layout.controls.items():
            self._draw_control(painter, control_id, bounds, model)
        self._draw_status(painter, model)
        self._draw_sensors(painter, model)

    def _request_widget_repaint(self) -> None:
        self.update()

    def _draw_control(
        self,
        painter: QPainter,
        control_id: str,
        bounds: PreviewRect,
        model: ControllerPreviewModel,
    ) -> None:
        rect = QRectF(bounds.left, bounds.top, bounds.width, bounds.height)
        pressed = control_id in model.pressed_control_ids
        base_color = QColor(model.buttons_color)
        painter.setPen(QPen(QColor("#F5F5F5"), 1.5))
        painter.setBrush(base_color.lighter(165) if pressed else base_color)
        if control_id in {"left_stick", "right_stick"}:
            grip_color = QColor(
                model.left_grip_color if control_id == "left_stick" else model.right_grip_color
            )
            painter.setBrush(grip_color)
            painter.drawEllipse(rect)
            position = (
                model.left_stick_position
                if control_id == "left_stick"
                else model.right_stick_position
            )
            radius = min(rect.width(), rect.height()) * 0.17
            travel = min(rect.width(), rect.height()) * 0.25
            center = rect.center()
            knob = QPointF(center.x() + position[0] * travel, center.y() - position[1] * travel)
            painter.setBrush(QColor("#D8D8D8"))
            painter.drawEllipse(_circle(knob, radius))
            return
        if control_id.endswith("_stick_click"):
            painter.setBrush(QColor("#F4C95D") if pressed else QColor("#303030"))
            painter.drawEllipse(rect)
            return
        label = {
            "dpad_up": "↑",
            "dpad_right": "→",
            "dpad_down": "↓",
            "dpad_left": "←",
            "minus": "-",
            "plus": "+",
            "home": "H",
            "capture": "C",
        }.get(control_id, control_id.upper())
        if control_id in {"zl", "l", "r", "zr", "minus", "plus", "home", "capture"}:
            painter.drawRoundedRect(rect, 7.0, 7.0)
        else:
            painter.drawEllipse(rect)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)

    def _draw_status(self, painter: QPainter, model: ControllerPreviewModel) -> None:
        translate = QCoreApplication.translate
        keyboard = translate("ControllerPreviewWidget", "Keyboard input")
        mouse = translate("ControllerPreviewWidget", "Mouse capture")
        on = translate("ControllerPreviewWidget", "On")
        off = translate("ControllerPreviewWidget", "Off")
        painter.setPen(QPen(QColor("#FFFFFF"), 1.0))
        status = QRectF(
            self.width() * 0.05,
            self.height() * 0.515,
            self.width() * 0.90,
            self.height() * 0.055,
        )
        painter.drawText(
            status,
            Qt.AlignmentFlag.AlignCenter,
            f"{keyboard}: {on if model.capture_active else off}  ·  "
            f"{mouse}: {on if model.pointer_capture_active else off}",
        )

    def _draw_sensors(self, painter: QPainter, model: ControllerPreviewModel) -> None:
        translate = QCoreApplication.translate
        top = self.height() * 0.82
        height = self.height() * 0.14
        gyro_bounds = QRectF(self.width() * 0.06, top, self.width() * 0.40, height)
        accel_bounds = QRectF(self.width() * 0.54, top, self.width() * 0.40, height)
        self._draw_gyro(painter, gyro_bounds, model.gyro_display)
        self._draw_accel(painter, accel_bounds, model.accel_display)
        painter.setPen(QPen(QColor("#EAEAEA"), 1.0))
        painter.drawText(
            gyro_bounds,
            Qt.AlignmentFlag.AlignTop,
            translate("ControllerPreviewWidget", "Gyro"),
        )
        painter.drawText(
            accel_bounds,
            Qt.AlignmentFlag.AlignTop,
            translate("ControllerPreviewWidget", "Acceleration"),
        )

    @staticmethod
    def _draw_gyro(painter: QPainter, bounds: QRectF, display: SensorDisplay) -> None:
        colors = (QColor("#E25D5D"), QColor("#63B66F"), QColor("#5B8DEF"))
        axes = zip((display.x, display.y, display.z), colors, strict=True)
        for index, (axis, color) in enumerate(axes):
            center = QPointF(
                bounds.left() + bounds.width() * (0.32 + index * 0.24),
                bounds.center().y() + 5.0,
            )
            radius = min(bounds.height() * 0.30, bounds.width() * 0.08)
            painter.setPen(QPen(QColor("#555555"), 2.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(_circle(center, radius))
            painter.setPen(QPen(color, 4.0))
            span = int(axis.direction * axis.magnitude * 300.0 * 16.0)
            painter.drawArc(_circle(center, radius), 90 * 16, span)
            painter.setPen(QPen(QColor("#F0F0F0"), 1.0))
            painter.drawText(_circle(center, radius), Qt.AlignmentFlag.AlignCenter, "XYZ"[index])

    @staticmethod
    def _draw_accel(painter: QPainter, bounds: QRectF, display: SensorDisplay) -> None:
        center = QPointF(bounds.center().x(), bounds.center().y() + 5.0)
        length = min(bounds.width() * 0.32, bounds.height() * 0.42)
        axes = (
            (display.x, QPointF(1.0, 0.0), QColor("#E25D5D"), "X"),
            (display.y, QPointF(0.0, -1.0), QColor("#63B66F"), "Y"),
            (display.z, QPointF(0.72, -0.72), QColor("#5B8DEF"), "Z"),
        )
        for axis, direction, color, label in axes:
            signed_length = length * axis.magnitude * axis.direction
            end = QPointF(
                center.x() + direction.x() * signed_length,
                center.y() + direction.y() * signed_length,
            )
            painter.setPen(QPen(color, 4.0))
            painter.drawLine(center, end)
            label_bounds = QRectF(end.x() - 9.0, end.y() - 9.0, 18.0, 18.0)
            painter.drawText(label_bounds, Qt.AlignmentFlag.AlignCenter, label)
        painter.setPen(QPen(QColor("#F0F0F0"), 1.0))
        painter.setBrush(QColor("#F0F0F0"))
        painter.drawEllipse(_circle(center, 3.0))


def _circle(center: QPointF, radius: float) -> QRectF:
    return QRectF(center.x() - radius, center.y() - radius, radius * 2.0, radius * 2.0)


def _sensor_description(frame: ControllerFrame) -> str:
    translate = QCoreApplication.translate
    gyro = translate("ControllerPreviewWidget", "Gyro")
    acceleration = translate("ControllerPreviewWidget", "Acceleration")
    return "\n".join(
        (
            f"{gyro} X: {frame.gyro_rate.x_radians_per_second:.2f} rad/s",
            f"{gyro} Y: {frame.gyro_rate.y_radians_per_second:.2f} rad/s",
            f"{gyro} Z: {frame.gyro_rate.z_radians_per_second:.2f} rad/s",
            f"{acceleration} X: {frame.accel_g.x_g:.2f} G",
            f"{acceleration} Y: {frame.accel_g.y_g:.2f} G",
            f"{acceleration} Z: {frame.accel_g.z_g:.2f} G",
        )
    )
