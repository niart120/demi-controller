from dataclasses import dataclass

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

import demi.ui.controller_preview as preview_module
from demi.app import WindowSpec
from demi.domain.controller import AccelG, ControllerFrame, GyroRate, LogicalButton, StickVector
from demi.domain.settings import ControllerColorSettings
from demi.ui.controller_preview import (
    ControllerPreviewWidget,
    PreviewRepaintLimiter,
    SystemPreviewClock,
    controller_preview_model,
)
from demi.ui.main_window import MainWindow


@dataclass
class FakeClock:
    """Control repaint-rate decisions without waiting for real time."""

    now_ns: int = 0

    def monotonic_ns(self) -> int:
        """Return the configured repaint timestamp."""
        return self.now_ns


def test_system_preview_clock_preserves_the_sixty_hz_repaint_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coarse_ticks = iter((0, 0, 15_625_000, 15_625_000))
    precise_ticks = iter((0, 8_000_000, 16_000_000, 17_000_000))
    monkeypatch.setattr(preview_module.time, "monotonic_ns", lambda: next(coarse_ticks))
    monkeypatch.setattr(preview_module.time, "perf_counter_ns", lambda: next(precise_ticks))
    limiter = PreviewRepaintLimiter(clock=SystemPreviewClock())

    assert [limiter.allows_repaint() for _ in range(4)] == [True, False, False, True]


def test_preview_model_and_widget_reflect_one_complete_frame_and_four_colors(
    qt_application: object,
) -> None:
    assert qt_application is not None
    frame = ControllerFrame(
        sequence=4,
        capture_epoch=2,
        monotonic_ns=1_008_000_000,
        buttons=frozenset({LogicalButton.A, LogicalButton.DPAD_LEFT, LogicalButton.LEFT_STICK}),
        left_stick=StickVector(x=-0.5, y=0.25),
        right_stick=StickVector(x=0.75, y=-0.5),
        gyro_rate=GyroRate(1.25, -2.5, 0.5),
        accel_g=AccelG(0.1, -0.2, 1.05),
        capture_active=True,
        pointer_capture_active=True,
    )
    colors = ControllerColorSettings(
        body="#102030",
        buttons="#405060",
        left_grip="#708090",
        right_grip="#A0B0C0",
    )

    model = controller_preview_model(frame, colors)

    assert model.control_ids == frozenset(
        {
            "a",
            "b",
            "x",
            "y",
            "dpad_up",
            "dpad_right",
            "dpad_down",
            "dpad_left",
            "l",
            "r",
            "zl",
            "zr",
            "plus",
            "minus",
            "home",
            "capture",
            "left_stick",
            "left_stick_click",
            "right_stick",
            "right_stick_click",
        }
    )
    assert model.body_color == "#102030"
    assert model.buttons_color == "#405060"
    assert model.left_grip_color == "#708090"
    assert model.right_grip_color == "#A0B0C0"
    assert model.pressed_buttons == frozenset(
        {LogicalButton.A, LogicalButton.DPAD_LEFT, LogicalButton.LEFT_STICK}
    )
    assert model.pressed_control_ids == frozenset({"a", "dpad_left", "left_stick_click"})
    assert model.left_stick == StickVector(x=-0.5, y=0.25)
    assert model.right_stick == StickVector(x=0.75, y=-0.5)
    assert model.left_stick_position == (-0.5, 0.25)
    assert model.right_stick_position == (0.75, -0.5)
    assert model.gyro_rate == GyroRate(1.25, -2.5, 0.5)
    assert model.accel_g == AccelG(0.1, -0.2, 1.05)
    assert model.capture_active is True
    assert model.pointer_capture_active is True

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


def test_preview_limits_repaint_requests_to_sixty_hz_but_keeps_the_latest_frame(
    qt_application: object,
) -> None:
    assert qt_application is not None
    clock = FakeClock()
    repaint_requests: list[None] = []
    widget = ControllerPreviewWidget(
        clock=clock,
        on_repaint_requested=lambda: repaint_requests.append(None),
    )

    first = _frame(sequence=1)
    widget.set_frame(first)
    clock.now_ns += 8_000_000
    widget.set_frame(_frame(sequence=2))
    clock.now_ns += 8_000_000
    widget.set_frame(_frame(sequence=3))
    clock.now_ns += 1_000_000
    latest = _frame(sequence=4)
    widget.set_frame(latest)

    assert len(repaint_requests) == 2
    assert widget.model == controller_preview_model(latest, ControllerColorSettings())


def _frame(*, sequence: int) -> ControllerFrame:
    return ControllerFrame(
        sequence=sequence,
        capture_epoch=1,
        monotonic_ns=1_000_000_000 + sequence,
        buttons=frozenset(),
        left_stick=StickVector(x=0.0, y=0.0),
        right_stick=StickVector(x=0.0, y=0.0),
        gyro_rate=GyroRate(0.0, 0.0, 0.0),
        accel_g=AccelG(0.0, 0.0, 1.0),
        capture_active=True,
    )
