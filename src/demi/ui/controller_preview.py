"""QPainter controller preview backed by a complete immutable controller frame."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from math import hypot
from typing import Protocol

from PySide6.QtCore import QCoreApplication, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from demi.domain.controller import AccelG, ControllerFrame, GyroRate, LogicalButton, StickVector
from demi.domain.settings import ControllerColorSettings
from demi.ui.preview_layout import (
    CONTROL_IDS,
    PreviewLayout,
    PreviewRect,
    normalized_stick_position,
    preview_layout,
)
from demi.ui.preview_sensor import (
    SensorDisplay,
    SignedAxisDisplay,
    accel_display,
    gyro_display,
)

type RepaintRequest = Callable[[], object]

_PRESSED_FILL_COLOR = "#F4C95D"
_PRESSED_OUTLINE_COLOR = "#FFF1A8"
_PRESSED_TEXT_COLOR = "#181818"
_STICK_CLICK_IDS = frozenset({"left_stick_click", "right_stick_click"})


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
    mouse_input_active: bool
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
        mouse_input_active=frame.pointer_capture_active,
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
        silhouette = _controller_silhouette_path(layout)
        painter.setPen(Qt.PenStyle.NoPen)
        self._draw_grip(painter, layout.left_grip_bounds, model.left_grip_color, left=True)
        self._draw_grip(painter, layout.right_grip_bounds, model.right_grip_color, left=False)
        painter.setBrush(QColor(model.body_color))
        painter.drawPath(_controller_faceplate_path(layout))
        painter.setPen(QPen(QColor("#E0E0E0"), 2.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(silhouette)
        painter.drawPath(_controller_faceplate_path(layout))
        for control_id, bounds in layout.controls.items():
            if control_id in _STICK_CLICK_IDS or control_id.startswith("dpad_"):
                continue
            self._draw_control(painter, control_id, bounds, model)
        self._draw_directional_pad(painter, layout, model)
        self._draw_status(painter, model, layout.status_bounds)
        self._draw_sensors(painter, model, layout.gyro_bounds, layout.accel_bounds)

    def _request_widget_repaint(self) -> None:
        self.update()

    def _draw_control(
        self,
        painter: QPainter,
        control_id: str,
        bounds: PreviewRect,
        model: ControllerPreviewModel,
    ) -> None:
        rect = _qrect(bounds)
        pressed = control_id in model.pressed_control_ids
        base_color = QColor(model.buttons_color)
        if control_id in {"left_stick", "right_stick"}:
            stick_click_id = (
                "left_stick_click" if control_id == "left_stick" else "right_stick_click"
            )
            stick_pressed = stick_click_id in model.pressed_control_ids
            painter.setPen(
                QPen(
                    QColor(_PRESSED_OUTLINE_COLOR if stick_pressed else "#F5F5F5"),
                    4.0 if stick_pressed else 1.5,
                )
            )
            painter.setBrush(base_color)
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
        painter.setPen(
            QPen(
                QColor(_PRESSED_OUTLINE_COLOR if pressed else "#F5F5F5"),
                3.0 if pressed else 1.5,
            )
        )
        painter.setBrush(QColor(_PRESSED_FILL_COLOR) if pressed else base_color)
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
        font = painter.font()
        label_font = painter.font()
        label_font.setPixelSize(_control_label_pixel_size(bounds))
        painter.setFont(label_font)
        painter.setPen(QPen(QColor(_PRESSED_TEXT_COLOR if pressed else "#F5F5F5"), 1.0))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)
        painter.setFont(font)

    @staticmethod
    def _draw_grip(painter: QPainter, bounds: PreviewRect, color: str, *, left: bool) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawPath(_grip_path(bounds, left=left))

    def _draw_directional_pad(
        self,
        painter: QPainter,
        layout: PreviewLayout,
        model: ControllerPreviewModel,
    ) -> None:
        control_ids = ("dpad_up", "dpad_left", "dpad_right", "dpad_down")
        path = _directional_pad_path(layout)
        pressed_ids = model.pressed_control_ids.intersection(control_ids)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(model.buttons_color))
        painter.drawPath(path)

        painter.save()
        painter.setClipPath(path)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(_PRESSED_FILL_COLOR))
        for control_id in pressed_ids:
            painter.drawRect(_qrect(layout.controls[control_id]))
        painter.restore()

        painter.setPen(
            QPen(
                QColor(_PRESSED_OUTLINE_COLOR if pressed_ids else "#F5F5F5"),
                3.0 if pressed_ids else 1.5,
            )
        )
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        labels = {
            "dpad_up": "▲",
            "dpad_left": "◀",
            "dpad_right": "▶",
            "dpad_down": "▼",
        }
        original_font = painter.font()
        for control_id in control_ids:
            bounds = layout.controls[control_id]
            label_font = painter.font()
            label_font.setPixelSize(_control_label_pixel_size(bounds))
            painter.setFont(label_font)
            painter.setPen(
                QPen(
                    QColor(_PRESSED_TEXT_COLOR if control_id in pressed_ids else "#F5F5F5"),
                    1.0,
                )
            )
            painter.drawText(
                _qrect(bounds),
                Qt.AlignmentFlag.AlignCenter,
                labels[control_id],
            )
        painter.setFont(original_font)

    def _draw_status(
        self,
        painter: QPainter,
        model: ControllerPreviewModel,
        bounds: PreviewRect,
    ) -> None:
        translate = QCoreApplication.translate
        on = translate("ControllerPreviewWidget", "On")
        off = translate("ControllerPreviewWidget", "Off")
        mouse_input = translate("ControllerPreviewWidget", "Mouse input")
        mouse_color = "#176B3A" if model.mouse_input_active else "#7A1F1F"
        painter.setPen(QPen(QColor("#FFFFFF"), 1.0))
        painter.setBrush(QColor(mouse_color))
        painter.drawRoundedRect(_qrect(bounds), 5.0, 5.0)
        painter.drawText(
            _qrect(bounds),
            Qt.AlignmentFlag.AlignCenter,
            f"{mouse_input}: {on if model.mouse_input_active else off} (F5)",
        )

    def _draw_sensors(
        self,
        painter: QPainter,
        model: ControllerPreviewModel,
        gyro_region: PreviewRect,
        accel_region: PreviewRect,
    ) -> None:
        translate = QCoreApplication.translate
        gyro_bounds = _qrect(gyro_region)
        accel_bounds = _qrect(accel_region)
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
            track, fill = _gyro_bar_geometry(bounds, index, axis)
            radius = track.height() / 2.0
            painter.setPen(QPen(QColor("#707070"), 1.0))
            painter.setBrush(QColor("#303030"))
            painter.drawRoundedRect(track, radius, radius)
            if fill.width() > 0.0:
                painter.setPen(QPen(color, 1.0))
                painter.setBrush(color)
                painter.drawRoundedRect(fill, radius, radius)
            painter.setPen(QPen(QColor("#B8B8B8"), 1.0))
            painter.drawLine(
                QPointF(track.center().x(), track.top() - 2.0),
                QPointF(track.center().x(), track.bottom() + 2.0),
            )
            label_bounds = QRectF(
                bounds.left(),
                track.center().y() - bounds.height() * 0.11,
                bounds.width() * 0.17,
                bounds.height() * 0.22,
            )
            painter.setPen(QPen(color, 1.0))
            painter.drawText(label_bounds, Qt.AlignmentFlag.AlignCenter, "XYZ"[index])

    @staticmethod
    def _draw_accel(painter: QPainter, bounds: QRectF, display: SensorDisplay) -> None:
        center, end, guides = _accel_vector_geometry(bounds, display)
        colors = (QColor("#E25D5D"), QColor("#63B66F"), QColor("#5B8DEF"))
        for index, ((guide_start, guide_end), color) in enumerate(zip(guides, colors, strict=True)):
            painter.setPen(QPen(QColor("#626262"), 1.0))
            painter.drawLine(guide_start, guide_end)
            label_bounds = QRectF(guide_end.x() - 11.0, guide_end.y() - 7.0, 22.0, 14.0)
            original_font = painter.font()
            label_font = painter.font()
            label_font.setPixelSize(max(8, round(bounds.height() * 0.13)))
            painter.setFont(label_font)
            painter.setPen(QPen(color, 1.0))
            painter.drawText(label_bounds, Qt.AlignmentFlag.AlignCenter, f"+{'XYZ'[index]}")
            painter.setFont(original_font)

        painter.setPen(QPen(QColor("#E8EEF4"), 4.0))
        painter.drawLine(center, end)
        vector_x = end.x() - center.x()
        vector_y = end.y() - center.y()
        vector_length = hypot(vector_x, vector_y)
        if vector_length > 0.0:
            unit_x = vector_x / vector_length
            unit_y = vector_y / vector_length
            head_length = min(9.0, bounds.height() * 0.12)
            base = QPointF(
                end.x() - unit_x * head_length,
                end.y() - unit_y * head_length,
            )
            side = head_length * 0.45
            painter.drawLine(
                end,
                QPointF(base.x() - unit_y * side, base.y() + unit_x * side),
            )
            painter.drawLine(
                end,
                QPointF(base.x() + unit_y * side, base.y() - unit_x * side),
            )
        painter.setPen(QPen(QColor("#F0F0F0"), 1.0))
        painter.setBrush(QColor("#F0F0F0"))
        painter.drawEllipse(_circle(center, 3.0))


def _circle(center: QPointF, radius: float) -> QRectF:
    return QRectF(center.x() - radius, center.y() - radius, radius * 2.0, radius * 2.0)


def _qrect(bounds: PreviewRect) -> QRectF:
    return QRectF(bounds.left, bounds.top, bounds.width, bounds.height)


def _controller_silhouette_path(layout: PreviewLayout) -> QPainterPath:
    return (
        _controller_faceplate_path(layout)
        .united(_grip_path(layout.left_grip_bounds, left=True))
        .united(_grip_path(layout.right_grip_bounds, left=False))
    )


def _directional_pad_path(layout: PreviewLayout) -> QPainterPath:
    up = _qrect(layout.controls["dpad_up"])
    left = _qrect(layout.controls["dpad_left"])
    right = _qrect(layout.controls["dpad_right"])
    down = _qrect(layout.controls["dpad_down"])
    path = QPainterPath()
    path.moveTo(up.left(), up.top())
    path.lineTo(up.right(), up.top())
    path.lineTo(up.right(), left.top())
    path.lineTo(right.right(), left.top())
    path.lineTo(right.right(), right.bottom())
    path.lineTo(down.right(), right.bottom())
    path.lineTo(down.right(), down.bottom())
    path.lineTo(down.left(), down.bottom())
    path.lineTo(down.left(), left.bottom())
    path.lineTo(left.left(), left.bottom())
    path.lineTo(left.left(), left.top())
    path.lineTo(up.left(), left.top())
    path.closeSubpath()
    return path


def _controller_faceplate_path(layout: PreviewLayout) -> QPainterPath:
    bounds = _qrect(layout.body_bounds)
    path = QPainterPath()
    path.moveTo(bounds.left() + bounds.width() * 0.14, bounds.top())
    path.lineTo(bounds.right() - bounds.width() * 0.14, bounds.top())
    path.cubicTo(
        bounds.right() - bounds.width() * 0.04,
        bounds.top(),
        bounds.right(),
        bounds.top() + bounds.height() * 0.10,
        bounds.right(),
        bounds.top() + bounds.height() * 0.25,
    )
    path.lineTo(bounds.right(), bounds.top() + bounds.height() * 0.60)
    path.cubicTo(
        bounds.right(),
        bounds.top() + bounds.height() * 0.84,
        bounds.right() - bounds.width() * 0.09,
        bounds.bottom(),
        bounds.center().x() + bounds.width() * 0.06,
        bounds.bottom(),
    )
    path.lineTo(bounds.center().x() - bounds.width() * 0.06, bounds.bottom())
    path.cubicTo(
        bounds.left() + bounds.width() * 0.09,
        bounds.bottom(),
        bounds.left(),
        bounds.top() + bounds.height() * 0.84,
        bounds.left(),
        bounds.top() + bounds.height() * 0.60,
    )
    path.lineTo(bounds.left(), bounds.top() + bounds.height() * 0.25)
    path.cubicTo(
        bounds.left(),
        bounds.top() + bounds.height() * 0.10,
        bounds.left() + bounds.width() * 0.04,
        bounds.top(),
        bounds.left() + bounds.width() * 0.14,
        bounds.top(),
    )
    path.closeSubpath()
    return path


def _grip_path(bounds: PreviewRect, *, left: bool) -> QPainterPath:
    rect = _qrect(bounds)
    path = QPainterPath()
    if left:
        path.moveTo(rect.left() + rect.width() * 0.43, rect.top())
        path.lineTo(rect.right(), rect.top() + rect.height() * 0.58)
        path.cubicTo(
            rect.left() + rect.width() * 0.92,
            rect.top() + rect.height() * 0.58,
            rect.left() + rect.width() * 0.82,
            rect.top() + rect.height() * 0.78,
            rect.left() + rect.width() * 0.70,
            rect.top() + rect.height() * 0.90,
        )
        path.cubicTo(
            rect.left() + rect.width() * 0.57,
            rect.bottom(),
            rect.left() + rect.width() * 0.30,
            rect.bottom(),
            rect.left() + rect.width() * 0.18,
            rect.top() + rect.height() * 0.91,
        )
        path.cubicTo(
            rect.left() + rect.width() * 0.02,
            rect.top() + rect.height() * 0.78,
            rect.left(),
            rect.top() + rect.height() * 0.48,
            rect.left() + rect.width() * 0.12,
            rect.top() + rect.height() * 0.24,
        )
        path.cubicTo(
            rect.left() + rect.width() * 0.20,
            rect.top() + rect.height() * 0.08,
            rect.left() + rect.width() * 0.30,
            rect.top(),
            rect.left() + rect.width() * 0.43,
            rect.top(),
        )
    else:
        path.moveTo(rect.right() - rect.width() * 0.43, rect.top())
        path.lineTo(rect.left(), rect.top() + rect.height() * 0.58)
        path.cubicTo(
            rect.right() - rect.width() * 0.92,
            rect.top() + rect.height() * 0.58,
            rect.right() - rect.width() * 0.82,
            rect.top() + rect.height() * 0.78,
            rect.right() - rect.width() * 0.70,
            rect.top() + rect.height() * 0.90,
        )
        path.cubicTo(
            rect.right() - rect.width() * 0.57,
            rect.bottom(),
            rect.right() - rect.width() * 0.30,
            rect.bottom(),
            rect.right() - rect.width() * 0.18,
            rect.top() + rect.height() * 0.91,
        )
        path.cubicTo(
            rect.right() - rect.width() * 0.02,
            rect.top() + rect.height() * 0.78,
            rect.right(),
            rect.top() + rect.height() * 0.48,
            rect.right() - rect.width() * 0.12,
            rect.top() + rect.height() * 0.24,
        )
        path.cubicTo(
            rect.right() - rect.width() * 0.20,
            rect.top() + rect.height() * 0.08,
            rect.right() - rect.width() * 0.30,
            rect.top(),
            rect.right() - rect.width() * 0.43,
            rect.top(),
        )
    path.closeSubpath()
    return path


def _control_label_pixel_size(bounds: PreviewRect) -> int:
    return max(11, round(min(bounds.width, bounds.height) * 0.42))


def _gyro_bar_geometry(
    bounds: QRectF,
    index: int,
    axis: SignedAxisDisplay,
) -> tuple[QRectF, QRectF]:
    track = QRectF(
        bounds.left() + bounds.width() * 0.20,
        bounds.top() + bounds.height() * (0.40 + index * 0.20),
        bounds.width() * 0.76,
        max(3.0, bounds.height() * 0.10),
    )
    center_x = track.center().x()
    signed_width = track.width() * 0.5 * axis.magnitude * axis.direction
    fill = QRectF(
        min(center_x, center_x + signed_width),
        track.top(),
        abs(signed_width),
        track.height(),
    )
    return track, fill


def _accel_vector_geometry(
    bounds: QRectF,
    display: SensorDisplay,
) -> tuple[QPointF, QPointF, tuple[tuple[QPointF, QPointF], ...]]:
    center = QPointF(bounds.center().x(), bounds.top() + bounds.height() * 0.58)
    axis_length = min(bounds.width() * 0.25, bounds.height() * 0.38)
    basis = ((0.0, -1.0), (-0.78, 0.62), (0.78, 0.62))
    guides = tuple(
        (
            QPointF(center.x() - x * axis_length, center.y() - y * axis_length),
            QPointF(center.x() + x * axis_length, center.y() + y * axis_length),
        )
        for x, y in basis
    )
    components = tuple(
        axis.direction * axis.magnitude for axis in (display.x, display.y, display.z)
    )
    projected_x = sum(
        value * direction[0] for value, direction in zip(components, basis, strict=True)
    )
    projected_y = sum(
        value * direction[1] for value, direction in zip(components, basis, strict=True)
    )
    projected_length = hypot(projected_x, projected_y)
    if projected_length > 1.0:
        projected_x /= projected_length
        projected_y /= projected_length
    end = QPointF(
        center.x() + projected_x * axis_length,
        center.y() + projected_y * axis_length,
    )
    return center, end, guides


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
