from dataclasses import dataclass
from math import hypot

import pytest
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap

import demi.ui.controller_preview as preview_module
from demi.app import WindowSpec
from demi.domain.controller import AccelG, ControllerFrame, GyroRate, LogicalButton, StickVector
from demi.domain.settings import ControllerColorSettings
from demi.ui.controller_preview import (
    ControllerPreviewModel,
    ControllerPreviewWidget,
    PreviewRepaintLimiter,
    SystemPreviewClock,
    controller_preview_model,
)
from demi.ui.main_window import MainWindow
from demi.ui.preview_layout import CONTROL_IDS, PreviewRect, preview_layout
from demi.ui.preview_sensor import accel_display, gyro_display


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
    assert model.gyro_display == gyro_display(frame.gyro_rate)
    assert model.accel_display == accel_display(frame.accel_g)
    assert model.capture_active is True
    assert model.pointer_capture_active is True
    assert model.mouse_input_active is True

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


def test_preview_keeps_keyboard_operation_independent_from_pointer_capture() -> None:
    model = controller_preview_model(
        _frame(sequence=1, capture_active=True, pointer_capture_active=False),
        ControllerColorSettings(),
    )

    assert model.capture_active is True
    assert model.pointer_capture_active is False
    assert model.mouse_input_active is False


def test_mouse_input_status_is_below_controller_and_above_imu_indicators() -> None:
    layout = preview_layout(960, 600)

    assert layout.status_bounds.top >= layout.left_grip_bounds.bottom
    assert layout.status_bounds.top >= layout.right_grip_bounds.bottom
    assert layout.status_bounds.bottom <= layout.gyro_bounds.top
    assert layout.status_bounds.bottom <= layout.accel_bounds.top


@pytest.mark.parametrize(
    ("active", "expected"),
    [(False, "Mouse input: Off"), (True, "Mouse input: On")],
)
def test_mouse_input_status_text_omits_keyboard_shortcut(
    active: bool,
    expected: str,
) -> None:
    assert preview_module._mouse_input_status_text(active) == expected


def test_mouse_input_status_text_uses_translated_terms_without_keyboard_shortcut() -> None:
    translations = {
        "Mouse input": "マウス入力",
        "On": "有効",
        "Off": "無効",
    }

    def translate(_context: str, source: str) -> str:
        return translations[source]

    assert preview_module._mouse_input_status_text(False, translate) == "マウス入力: 無効"
    assert preview_module._mouse_input_status_text(True, translate) == "マウス入力: 有効"


def test_controller_layout_forms_lower_grips_and_a_joined_directional_pad() -> None:
    layout = preview_layout(960, 600)
    dpad_up = layout.controls["dpad_up"]
    dpad_left = layout.controls["dpad_left"]
    dpad_right = layout.controls["dpad_right"]
    dpad_down = layout.controls["dpad_down"]
    assert layout.left_grip_bounds.height > layout.left_grip_bounds.width
    assert layout.right_grip_bounds.height > layout.right_grip_bounds.width
    assert dpad_up.bottom > dpad_left.top
    assert dpad_up.bottom > dpad_right.top
    assert dpad_down.top < dpad_left.bottom
    assert dpad_down.top < dpad_right.bottom


def test_controller_layout_places_external_grips_below_the_faceplate() -> None:
    layout = preview_layout(960, 600)

    assert layout.left_grip_bounds.left < layout.body_bounds.left
    assert layout.right_grip_bounds.right > layout.body_bounds.right
    assert layout.left_grip_bounds.bottom <= layout.status_bounds.top
    assert layout.right_grip_bounds.bottom <= layout.status_bounds.top


@pytest.mark.parametrize("size", [(960, 600), (800, 475)])
def test_all_controls_stay_inside_a_two_to_one_silhouette_with_enclosed_shoulders(
    size: tuple[int, int],
) -> None:
    layout = preview_layout(*size)
    faceplate = preview_module._controller_faceplate_path(layout)
    silhouette = preview_module._controller_silhouette_path(layout)
    silhouette_bounds = silhouette.boundingRect()

    for control_id in CONTROL_IDS:
        assert faceplate.contains(preview_module._qrect(layout.controls[control_id])), control_id

    assert silhouette_bounds.top() <= layout.content_bounds.top + 1.0
    assert 1.9 <= silhouette_bounds.width() / silhouette_bounds.height() <= 2.1


def test_controller_silhouette_contains_both_complete_grip_regions() -> None:
    layout = preview_layout(960, 600)
    silhouette = preview_module._controller_silhouette_path(layout)
    left_grip = preview_module._grip_path(layout.left_grip_bounds, left=True)
    right_grip = preview_module._grip_path(layout.right_grip_bounds, left=False)

    assert left_grip.subtracted(silhouette).isEmpty()
    assert right_grip.subtracted(silhouette).isEmpty()


def test_controller_layout_places_the_left_stick_above_the_directional_pad() -> None:
    layout = preview_layout(960, 600)

    assert layout.controls["left_stick"].bottom <= layout.controls["dpad_up"].top


def test_directional_pad_uses_one_connected_cross_path() -> None:
    layout = preview_layout(960, 600)

    path = preview_module._directional_pad_path(layout)

    assert len(path.toFillPolygons()) == 1
    for control_id in ("dpad_up", "dpad_left", "dpad_right", "dpad_down"):
        bounds = preview_module._qrect(layout.controls[control_id])
        assert path.contains(bounds.center())


def test_face_controls_and_shoulders_keep_balanced_relative_proportions() -> None:
    layout = preview_layout(960, 600)
    controls = layout.controls
    stick_diameter = controls["left_stick"].width
    face_button_diameter = controls["a"].width
    dpad_bounds = preview_module._directional_pad_path(layout).boundingRect()

    assert dpad_bounds.width() <= stick_diameter * 1.2
    assert dpad_bounds.height() <= stick_diameter * 1.2
    for control_id in ("zl", "l", "r", "zr"):
        assert controls[control_id].width <= face_button_diameter * 2.25

    x_center = controls["x"].left + controls["x"].width / 2
    y_center = controls["y"].left + controls["y"].width / 2
    a_center = controls["a"].left + controls["a"].width / 2
    b_center = controls["b"].left + controls["b"].width / 2
    assert a_center - x_center == pytest.approx(x_center - y_center)
    assert b_center == pytest.approx(x_center)
    horizontal_spacing = a_center - x_center
    vertical_spacing = controls["y"].top - controls["x"].top
    assert horizontal_spacing == pytest.approx(vertical_spacing)


def test_pressed_button_fill_has_clear_contrast_from_neutral_fill(
    qt_application: object,
) -> None:
    assert qt_application is not None
    widget = ControllerPreviewWidget()
    widget.resize(960, 600)
    button_bounds = preview_layout(widget.width(), widget.height()).controls["a"]
    sample_x = round(button_bounds.left + button_bounds.width * 0.78)
    sample_y = round(button_bounds.top + button_bounds.height * 0.50)

    widget.set_frame(_frame(sequence=1))
    neutral = QPixmap(widget.size())
    widget.render(neutral)
    neutral_fill = neutral.toImage().pixelColor(sample_x, sample_y)

    widget.set_frame(_frame(sequence=2, buttons=frozenset({LogicalButton.A})))
    pressed = QPixmap(widget.size())
    widget.render(pressed)
    pressed_fill = pressed.toImage().pixelColor(sample_x, sample_y)

    assert _contrast_ratio(_rgb(neutral_fill), _rgb(pressed_fill)) >= 3.0


def test_stick_click_is_not_drawn_as_a_separate_control_over_the_stick(
    qt_application: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert qt_application is not None
    drawn_control_ids: list[str] = []
    draw_control = ControllerPreviewWidget._draw_control

    def record_control(
        self: ControllerPreviewWidget,
        painter: QPainter,
        control_id: str,
        bounds: PreviewRect,
        model: ControllerPreviewModel,
    ) -> None:
        drawn_control_ids.append(control_id)
        draw_control(self, painter, control_id, bounds, model)

    monkeypatch.setattr(ControllerPreviewWidget, "_draw_control", record_control)
    widget = ControllerPreviewWidget()
    widget.resize(960, 600)
    widget.set_frame(_frame(sequence=1, buttons=frozenset({LogicalButton.LEFT_STICK})))
    canvas = QPixmap(widget.size())
    widget.render(canvas)

    assert "left_stick" in drawn_control_ids
    assert "right_stick" in drawn_control_ids
    assert "left_stick_click" not in drawn_control_ids
    assert "right_stick_click" not in drawn_control_ids


@pytest.mark.parametrize(
    "position",
    [
        (-1.0, -1.0),
        (-1.0, 1.0),
        (1.0, -1.0),
        (1.0, 1.0),
        (-1.0, 0.0),
        (1.0, 0.0),
        (0.0, -1.0),
        (0.0, 1.0),
    ],
)
def test_stick_knob_remains_completely_inside_its_outer_ring(
    position: tuple[float, float],
) -> None:
    outer_ring = QRectF(0.0, 0.0, 108.0, 108.0)
    knob = preview_module._stick_knob_geometry(outer_ring, position)
    center_distance = hypot(
        knob.center().x() - outer_ring.center().x(),
        knob.center().y() - outer_ring.center().y(),
    )

    assert center_distance + knob.width() / 2 <= outer_ring.width() / 2


def test_control_label_size_scales_with_the_control() -> None:
    bounds = preview_layout(960, 600).controls["a"]

    pixel_size = preview_module._control_label_pixel_size(bounds)

    assert pixel_size >= round(bounds.height * 0.40)


def test_grip_colors_fill_grip_regions_and_not_the_stick_surfaces(
    qt_application: object,
) -> None:
    assert qt_application is not None
    colors = ControllerColorSettings(
        body="#102030",
        buttons="#405060",
        left_grip="#A02020",
        right_grip="#20A020",
    )
    widget = ControllerPreviewWidget(colors=colors)
    widget.resize(960, 600)
    widget.set_frame(_frame(sequence=1))
    canvas = QPixmap(widget.size())
    widget.render(canvas)
    image = canvas.toImage()
    layout = preview_layout(widget.width(), widget.height())

    assert _sample_rect(image, layout.left_grip_bounds, 0.20, 0.80) == (160, 32, 32)
    assert _sample_rect(image, layout.right_grip_bounds, 0.70, 0.75) == (32, 160, 32)
    assert _sample_rect(image, layout.controls["left_stick"], 0.50, 0.15) == (64, 80, 96)
    assert _sample_rect(image, layout.controls["right_stick"], 0.50, 0.15) == (64, 80, 96)


def test_gyro_indicator_uses_signed_linear_tracks_instead_of_button_like_rings() -> None:
    bounds = QRectF(0.0, 0.0, 384.0, 84.0)
    display = gyro_display(GyroRate(2.0, -2.0, 0.0))

    positive_track, positive_fill = preview_module._gyro_bar_geometry(bounds, 0, display.x)
    negative_track, negative_fill = preview_module._gyro_bar_geometry(bounds, 1, display.y)
    _, zero_fill = preview_module._gyro_bar_geometry(bounds, 2, display.z)

    assert positive_track.width() >= positive_track.height() * 4
    assert negative_track.width() >= negative_track.height() * 4
    assert positive_fill.left() == pytest.approx(positive_track.center().x())
    assert positive_fill.right() > positive_track.center().x()
    assert negative_fill.right() == pytest.approx(negative_track.center().x())
    assert negative_fill.left() < negative_track.center().x()
    assert zero_fill.width() == 0.0


def test_minimum_imu_layout_keeps_plots_below_a_readable_heading_band() -> None:
    layout = preview_layout(800, 475)
    gyro_bounds = preview_module._qrect(layout.gyro_bounds)
    accel_bounds = preview_module._qrect(layout.accel_bounds)
    display = accel_display(AccelG(0.0, 0.0, 1.0))

    first_track, _ = preview_module._gyro_bar_geometry(
        gyro_bounds,
        0,
        gyro_display(GyroRate(0.0, 0.0, 0.0)).x,
    )
    _, _, guides = preview_module._accel_vector_geometry(accel_bounds, display)

    assert first_track.top() >= gyro_bounds.top() + 16.0
    assert min(point.y() for guide in guides for point in guide) >= accel_bounds.top() + 16.0
    assert preview_module._accel_axis_label_pixel_size(accel_bounds) >= 10


def test_acceleration_indicator_composes_three_axes_into_one_vector() -> None:
    bounds = QRectF(0.0, 0.0, 384.0, 84.0)
    x_only = accel_display(AccelG(0.25, 0.0, 0.0))
    y_only = accel_display(AccelG(0.0, 0.25, 0.0))
    z_only = accel_display(AccelG(0.0, 0.0, 0.25))
    combined = accel_display(AccelG(0.25, 0.25, 0.25))

    center, x_end, guides = preview_module._accel_vector_geometry(bounds, x_only)
    _, y_end, _ = preview_module._accel_vector_geometry(bounds, y_only)
    _, z_end, _ = preview_module._accel_vector_geometry(bounds, z_only)
    _, combined_end, _ = preview_module._accel_vector_geometry(bounds, combined)

    assert len(guides) == 3
    assert combined_end.x() - center.x() == pytest.approx(
        (x_end.x() - center.x()) + (y_end.x() - center.x()) + (z_end.x() - center.x())
    )
    assert combined_end.y() - center.y() == pytest.approx(
        (x_end.y() - center.y()) + (y_end.y() - center.y()) + (z_end.y() - center.y())
    )
    assert x_end.x() > center.x()  # +X: upper-right
    assert x_end.y() < center.y()
    assert y_end.x() > center.x()  # +Y: lower-right
    assert y_end.y() > center.y()
    assert z_end.x() == pytest.approx(center.x())  # +Z: screen-down
    assert z_end.y() > center.y()


def _frame(
    *,
    sequence: int,
    capture_active: bool = True,
    pointer_capture_active: bool = False,
    buttons: frozenset[LogicalButton] = frozenset(),
) -> ControllerFrame:
    return ControllerFrame(
        sequence=sequence,
        capture_epoch=1,
        monotonic_ns=1_000_000_000 + sequence,
        buttons=buttons,
        left_stick=StickVector(x=0.0, y=0.0),
        right_stick=StickVector(x=0.0, y=0.0),
        gyro_rate=GyroRate(0.0, 0.0, 0.0),
        accel_g=AccelG(0.0, 0.0, 1.0),
        capture_active=capture_active,
        pointer_capture_active=pointer_capture_active,
    )


def _contrast_ratio(first: tuple[int, int, int], second: tuple[int, int, int]) -> float:
    def luminance(color: tuple[int, int, int]) -> float:
        channels = tuple(channel / 255 for channel in color)
        linear = tuple(
            channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
            for channel in channels
        )
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    lighter = max(luminance(first), luminance(second))
    darker = min(luminance(first), luminance(second))
    return (lighter + 0.05) / (darker + 0.05)


def _sample_rect(
    image: QImage,
    bounds: PreviewRect,
    x_ratio: float,
    y_ratio: float,
) -> tuple[int, int, int]:
    color = image.pixelColor(
        round(bounds.left + bounds.width * x_ratio),
        round(bounds.top + bounds.height * y_ratio),
    )
    return _rgb(color)


def _rgb(color: QColor) -> tuple[int, int, int]:
    return color.red(), color.green(), color.blue()
