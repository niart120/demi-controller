from demi.domain.controller import AccelG, ControllerFrame, GyroRate, StickVector
from demi.ui.controller_preview import ControllerPreviewWidget


def test_preview_exposes_exact_sensor_axes_without_permanent_numeric_labels(
    qt_application: object,
) -> None:
    assert qt_application is not None
    widget = ControllerPreviewWidget()
    widget.set_frame(
        ControllerFrame(
            sequence=1,
            capture_epoch=1,
            monotonic_ns=1_000_000_000,
            buttons=frozenset(),
            left_stick=StickVector(0.0, 0.0),
            right_stick=StickVector(0.0, 0.0),
            gyro_rate=GyroRate(1.25, -2.5, 0.5),
            accel_g=AccelG(0.1, -0.2, 1.05),
            capture_active=True,
        )
    )

    expected_lines = (
        "Gyro X: 1.25 rad/s",
        "Gyro Y: -2.50 rad/s",
        "Gyro Z: 0.50 rad/s",
        "Acceleration X: 0.10 G",
        "Acceleration Y: -0.20 G",
        "Acceleration Z: 1.05 G",
    )
    tooltip = widget.toolTip()
    accessible_description = widget.accessibleDescription()

    assert all(line in tooltip for line in expected_lines)
    assert accessible_description == tooltip
