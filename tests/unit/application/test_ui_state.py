from pathlib import Path


def test_application_and_session_sources_do_not_import_pyside6() -> None:
    repository_root = Path(__file__).parents[3]
    source_paths = [
        repository_root / "src" / "demi" / "app.py",
        *(repository_root / "src" / "demi" / "application").glob("*.py"),
    ]

    assert source_paths
    assert all("PySide6" not in path.read_text(encoding="utf-8") for path in source_paths)
