from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from demi.app import WindowSpec
from demi.domain.controller import AccelG, ControllerFrame, GyroRate, LogicalButton, StickVector
from demi.domain.settings import ControllerColorSettings
from demi.ui.controller_preview import (
    ControllerPreviewWidget,
    controller_preview_model,
)
from demi.ui.main_window import MainWindow


def test_preview_model_and_widget_reflect_one_complete_frame_and_four_colors(
    qt_application: object,
) -> None:
    assert qt_application is not None
    frame = ControllerFrame(
        sequence=4,
        capture_epoch=2,
        monotonic_ns=1_008_000_000,
        buttons=frozenset({LogicalButton.A, LogicalButton.DPAD_LEFT}),
        left_stick=StickVector(x=-0.5, y=0.25),
        right_stick=StickVector(x=0.75, y=-0.5),
        gyro_rate=GyroRate(1.25, -2.5, 0.5),
        accel_g=AccelG(0.1, -0.2, 1.05),
        capture_active=True,
    )
    colors = ControllerColorSettings(
        body="#102030",
        buttons="#405060",
        left_grip="#708090",
        right_grip="#A0B0C0",
    )

    model = controller_preview_model(frame, colors)

    assert model.body_color == "#102030"
    assert model.buttons_color == "#405060"
    assert model.left_grip_color == "#708090"
    assert model.right_grip_color == "#A0B0C0"
    assert model.pressed_buttons == frozenset({LogicalButton.A, LogicalButton.DPAD_LEFT})
    assert model.left_stick == StickVector(x=-0.5, y=0.25)
    assert model.right_stick == StickVector(x=0.75, y=-0.5)
    assert model.gyro_rate == GyroRate(1.25, -2.5, 0.5)
    assert model.accel_g == AccelG(0.1, -0.2, 1.05)
    assert model.capture_active is True

    widget = ControllerPreviewWidget(colors=colors)
    widget.resize(640, 360)
    widget.set_frame(frame)
    canvas = QPixmap(widget.size())
    canvas.fill(Qt.GlobalColor.transparent)
    widget.render(canvas)

    assert widget.model == model
    assert canvas.isNull() is False

    window = MainWindow(WindowSpec(width=960, height=640, maximized=False))
    window.set_controller_colors(colors)
    window.set_frame(frame)

    assert window.controller_preview.model == model
