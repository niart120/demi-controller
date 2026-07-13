from demi.domain.controller import AccelG, ControllerFrame, GyroRate, LogicalButton, StickVector
from demi.domain.settings import ControllerColorSettings
from demi.ui.controller_view import ControllerView


def make_frame() -> ControllerFrame:
    """Build a frame containing each dynamic display value."""
    return ControllerFrame(
        sequence=1,
        capture_epoch=2,
        monotonic_ns=3,
        buttons=frozenset({LogicalButton.A, LogicalButton.DPAD_LEFT}),
        left_stick=StickVector(x=-0.5, y=1.0),
        right_stick=StickVector(x=0.25, y=-1.0),
        gyro_rate=GyroRate(1.0, 2.0, 3.0),
        accel_g=AccelG(-0.5, 0.0, 0.8660254),
        capture_active=True,
    )


def test_controller_view_model_uses_only_the_latest_controller_frame() -> None:
    view = ControllerView()

    view.update(make_frame())

    model = view.model
    assert model.buttons == frozenset({LogicalButton.A, LogicalButton.DPAD_LEFT})
    assert model.left_stick == StickVector(x=-0.5, y=1.0)
    assert model.right_stick == StickVector(x=0.25, y=-1.0)
    assert model.gyro_rate == GyroRate(1.0, 2.0, 3.0)
    assert model.accel_g == AccelG(-0.5, 0.0, 0.8660254)
    assert model.capture_active is True


def test_controller_view_can_return_to_neutral_from_a_pressed_frame() -> None:
    view = ControllerView()
    view.update(make_frame())
    view.update(
        ControllerFrame(
            sequence=2,
            capture_epoch=3,
            monotonic_ns=4,
            buttons=frozenset(),
            left_stick=StickVector(x=0.0, y=0.0),
            right_stick=StickVector(x=0.0, y=0.0),
            gyro_rate=GyroRate(0.0, 0.0, 0.0),
            accel_g=AccelG(0.0, 0.0, 1.0),
            capture_active=False,
        )
    )

    assert view.model.buttons == frozenset()
    assert view.model.left_stick == StickVector(x=0.0, y=0.0)
    assert view.model.capture_active is False


def test_controller_view_replaces_colors_for_the_next_render() -> None:
    view = ControllerView()
    colors = ControllerColorSettings(body="#ABCDEF")

    view.set_colors(colors)

    assert view.colors == colors
