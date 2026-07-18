import ast
import re
from pathlib import Path

_JAPANESE_TEXT = re.compile(r"[ぁ-んァ-ン一-龯]")


def test_user_interface_source_strings_are_english() -> None:
    repository_root = Path(__file__).parents[3]
    source_paths = [repository_root / "src/demi/app.py"]
    source_paths.extend((repository_root / "src/demi/ui").rglob("*.py"))
    violations: list[str] = []

    for path in source_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and _JAPANESE_TEXT.search(node.value)
            ):
                relative_path = path.relative_to(repository_root)
                violations.append(f"{relative_path}:{node.lineno}: {node.value!r}")

    assert violations == []
