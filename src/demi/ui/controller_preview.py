"""QPainter controller preview backed by a complete immutable controller frame."""

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from demi.domain.controller import AccelG, ControllerFrame, GyroRate, LogicalButton, StickVector
from demi.domain.settings import ControllerColorSettings


@dataclass(frozen=True, slots=True)
class ControllerPreviewModel:
    """Display-only values derived from one frame and four controller colors."""

    body_color: str
    buttons_color: str
    left_grip_color: str
    right_grip_color: str
    pressed_buttons: frozenset[LogicalButton]
    left_stick: StickVector
    right_stick: StickVector
    gyro_rate: GyroRate
    accel_g: AccelG
    capture_active: bool


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
        left_stick=frame.left_stick,
        right_stick=frame.right_stick,
        gyro_rate=frame.gyro_rate,
        accel_g=frame.accel_g,
        capture_active=frame.capture_active,
    )


class ControllerPreviewWidget(QWidget):
    """Render a controller-state model without changing input or runtime state."""

    def __init__(
        self,
        *,
        colors: ControllerColorSettings | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Create a preview with validated colors and no initial controller frame.

        Args:
            colors: Initial controller colors, defaulting to application defaults.
            parent: Optional Qt owner for widget lifetime.
        """
        super().__init__(parent)
        self._colors = colors if colors is not None else ControllerColorSettings()
        self._frame: ControllerFrame | None = None
        self._model: ControllerPreviewModel | None = None
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
        self.update()

    def set_colors(self, colors: ControllerColorSettings) -> None:
        """Apply four validated colors without changing the current input frame.

        Args:
            colors: Replacement display colors selected by the UI.
        """
        self._colors = colors
        frame = self._frame
        if frame is not None:
            self._model = controller_preview_model(frame, colors)
        self.update()

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
        bounds = QRectF(self.rect()).adjusted(20.0, 20.0, -20.0, -20.0)
        body = QRectF(
            bounds.left() + bounds.width() * 0.15,
            bounds.top() + bounds.height() * 0.22,
            bounds.width() * 0.70,
            bounds.height() * 0.46,
        )
        painter.setPen(QPen(QColor("#E0E0E0"), 2.0))
        painter.setBrush(QColor(model.body_color))
        painter.drawRoundedRect(body, 44.0, 44.0)

        left_grip_center = QPointF(body.left() + body.width() * 0.18, body.center().y())
        right_grip_center = QPointF(body.right() - body.width() * 0.18, body.center().y())
        self._draw_grip(painter, left_grip_center, QColor(model.left_grip_color))
        self._draw_grip(painter, right_grip_center, QColor(model.right_grip_color))
        self._draw_stick(painter, left_grip_center, model.left_stick)
        self._draw_stick(painter, right_grip_center, model.right_stick)
        self._draw_buttons(painter, body, model)
        self._draw_diagnostics(painter, bounds, model)
        self._draw_capture_overlay(painter, body, model.capture_active)

    @staticmethod
    def _draw_grip(painter: QPainter, center: QPointF, color: QColor) -> None:
        painter.setPen(QPen(QColor("#E0E0E0"), 1.5))
        painter.setBrush(color)
        painter.drawEllipse(_circle(center, 54.0))

    @staticmethod
    def _draw_stick(painter: QPainter, center: QPointF, stick: StickVector) -> None:
        painter.setPen(QPen(QColor("#F5F5F5"), 2.0))
        painter.setBrush(QColor("#242424"))
        painter.drawEllipse(_circle(center, 31.0))
        thumb_center = QPointF(center.x() + stick.x * 21.0, center.y() - stick.y * 21.0)
        painter.setBrush(QColor("#D8D8D8"))
        painter.drawEllipse(_circle(thumb_center, 11.0))

    @staticmethod
    def _draw_buttons(
        painter: QPainter,
        body: QRectF,
        model: ControllerPreviewModel,
    ) -> None:
        positions = {
            LogicalButton.X: QPointF(body.right() - 78.0, body.top() + 62.0),
            LogicalButton.Y: QPointF(body.right() - 102.0, body.top() + 86.0),
            LogicalButton.A: QPointF(body.right() - 54.0, body.top() + 86.0),
            LogicalButton.B: QPointF(body.right() - 78.0, body.top() + 110.0),
            LogicalButton.DPAD_UP: QPointF(body.left() + 78.0, body.top() + 62.0),
            LogicalButton.DPAD_LEFT: QPointF(body.left() + 54.0, body.top() + 86.0),
            LogicalButton.DPAD_RIGHT: QPointF(body.left() + 102.0, body.top() + 86.0),
            LogicalButton.DPAD_DOWN: QPointF(body.left() + 78.0, body.top() + 110.0),
        }
        base_color = QColor(model.buttons_color)
        for button, center in positions.items():
            painter.setPen(QPen(QColor("#F0F0F0"), 1.5))
            button_color = (
                base_color.lighter(150) if button in model.pressed_buttons else base_color
            )
            painter.setBrush(button_color)
            painter.drawEllipse(_circle(center, 13.0))
            painter.drawText(_circle(center, 13.0), Qt.AlignmentFlag.AlignCenter, button.value[:1])

    @staticmethod
    def _draw_diagnostics(
        painter: QPainter,
        bounds: QRectF,
        model: ControllerPreviewModel,
    ) -> None:
        painter.setPen(QPen(QColor("#F0F0F0"), 1.0))
        pressed = ", ".join(sorted(button.value for button in model.pressed_buttons)) or "なし"
        text = (
            f"ボタン: {pressed}\n"
            f"ジャイロ: {model.gyro_rate.x_radians_per_second:.2f}, "
            f"{model.gyro_rate.y_radians_per_second:.2f}, "
            f"{model.gyro_rate.z_radians_per_second:.2f}\n"
            f"加速度: {model.accel_g.x_g:.2f}, {model.accel_g.y_g:.2f}, {model.accel_g.z_g:.2f}"
        )
        diagnostics = QRectF(bounds.left(), bounds.bottom() - 58.0, bounds.width(), 58.0)
        painter.drawText(diagnostics, Qt.AlignmentFlag.AlignLeft, text)

    @staticmethod
    def _draw_capture_overlay(painter: QPainter, body: QRectF, capture_active: bool) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#167A4C") if capture_active else QColor("#4A4A4A"))
        overlay = QRectF(body.center().x() - 64.0, body.bottom() - 36.0, 128.0, 24.0)
        painter.drawRoundedRect(overlay, 8.0, 8.0)
        painter.setPen(QPen(QColor("#FFFFFF"), 1.0))
        label = "入力捕捉中" if capture_active else "入力待機中"
        painter.drawText(overlay, Qt.AlignmentFlag.AlignCenter, label)


def _circle(center: QPointF, radius: float) -> QRectF:
    return QRectF(center.x() - radius, center.y() - radius, radius * 2.0, radius * 2.0)
