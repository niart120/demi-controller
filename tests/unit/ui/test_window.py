from demi.ui.window import WindowSpec


def test_default_window_spec_preserves_minimum_layout_contract() -> None:
    spec = WindowSpec()

    assert (spec.width, spec.height) == (960, 640)
    assert (spec.min_width, spec.min_height) == (800, 520)
    assert spec.resizable is True
    assert spec.caption == "Project Demi"
