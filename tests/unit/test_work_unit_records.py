"""Regression checks for the completed Qt UI work-unit records."""

from pathlib import Path

COMPLETED_UI_UNITS = (
    "unit_013/LEGACY_UI_AND_PYGLET_REMOVAL.md",
    "unit_014/PYSIDE6_APPLICATION_SHELL.md",
    "unit_015/QT_INPUT_AND_CONTROLLER_PREVIEW.md",
    "unit_016/QT_STANDARD_CONTROLS_AND_DIALOGS.md",
    "unit_017/QT_RUNTIME_AND_LIFECYCLE_INTEGRATION.md",
)


def test_completed_ui_units_have_closed_tdd_lists_and_checklists() -> None:
    """Keep predecessor records complete while preserving their historical evidence."""
    root = Path(__file__).parents[2]

    for relative_path in COMPLETED_UI_UNITS:
        record = (root / "spec" / "complete" / relative_path).read_text(encoding="utf-8")
        tdd_list = _section(record, "## 6. TDD Test List", "## 7.")
        checklist = _section(record, "## 11. チェックリスト", None)

        assert "| todo |" not in tdd_list
        assert "| deferred |" not in tdd_list
        assert "- [ ]" not in checklist


def test_unit_018_keeps_only_windows_manual_and_standalone_work_open() -> None:
    """Avoid stale acceptance status after the source-level work is complete."""
    root = Path(__file__).parents[2]
    record = (root / "spec" / "wip" / "unit_018" / "QT_QUALITY_AND_OS_ACCEPTANCE.md").read_text(
        encoding="utf-8"
    )
    tdd_list = _section(record, "## 6. TDD Test List", "## 7.")

    assert tdd_list.count("| todo |") == 1
    assert "| todo | Windows実display" in tdd_list
    assert tdd_list.count("| deferred |") == 1
    assert "| deferred | standalone artifact" in tdd_list
    assert "| 3 OS source CI | not run |" not in record
    assert "| macOS / Linux実display acceptance |" not in record


def _section(record: str, start: str, end: str | None) -> str:
    """Return one Markdown section without its next heading."""
    start_index = record.index(start)
    section = record[start_index:]
    if end is None:
        return section
    return section[: section.index(end)]
