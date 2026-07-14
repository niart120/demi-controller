from pathlib import Path


def test_application_and_session_sources_do_not_import_pyside6() -> None:
    repository_root = Path(__file__).parents[3]
    source_paths = [
        repository_root / "src" / "demi" / "app.py",
        *(repository_root / "src" / "demi" / "application").glob("*.py"),
    ]

    assert source_paths
    assert all("PySide6" not in path.read_text(encoding="utf-8") for path in source_paths)


def test_application_and_domain_keep_framework_and_any_out_of_the_core() -> None:
    repository_root = Path(__file__).parents[3]
    source_paths = [
        *(repository_root / "src" / "demi" / "application").glob("*.py"),
        *(repository_root / "src" / "demi" / "domain").glob("*.py"),
    ]

    assert source_paths
    for source_path in source_paths:
        source = source_path.read_text(encoding="utf-8")

        assert "PySide6" not in source
        assert "Any" not in source
        assert "# type: ignore" not in source
