from pathlib import Path

_CONTROL_SOURCE_PATHS = (
    Path("src/demi/ui/toolbar.py"),
    Path("src/demi/ui/dialogs/mapping.py"),
    Path("src/demi/ui/dialogs/connection.py"),
    Path("src/demi/ui/dialogs/colors.py"),
)
_COORDINATE_HIT_TEST_MARKERS = (
    "event.position(",
    "event.globalPosition(",
    "contains(",
    "childAt(",
    "hit_test",
    "hitTest",
)


def test_standard_control_sources_do_not_implement_coordinate_hit_testing() -> None:
    repository_root = Path(__file__).parents[3]

    for relative_path in _CONTROL_SOURCE_PATHS:
        source = (repository_root / relative_path).read_text(encoding="utf-8")
        for marker in _COORDINATE_HIT_TEST_MARKERS:
            assert marker not in source, f"{relative_path}: {marker}"
