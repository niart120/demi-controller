from pathlib import Path


def test_readme_and_initial_spec_describe_the_current_qt_execution_surface() -> None:
    root = Path(__file__).parents[2]
    readme = (root / "README.md").read_text(encoding="utf-8")
    initial_readme = (root / "spec" / "initial" / "README.md").read_text(encoding="utf-8")
    requirements = (root / "spec" / "initial" / "requirements.md").read_text(encoding="utf-8")

    for entry_point in ("uv run demi", "uv run project-demi", "uv run python -m demi"):
        assert entry_point in readme
    assert "PySide6 / Qt Widgets" in readme
    assert (
        "コントローラー入力のプレビュー、キーボード / マウス操作、設定画面、"
        "接続 / ペアリング操作は未実装"
    ) not in readme
    assert "単体配布物は提供していない" in readme
    assert "ソース一式とビルドした wheel" in initial_readme
    assert "単体配布物" in initial_readme
    assert "`demi`、`project-demi`、`python -m demi`" in requirements
