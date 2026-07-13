"""Regression tests for removal of legacy pyglet UI boundaries."""

import ast
from pathlib import Path

LEGACY_MODULE_PREFIXES = (
    "pyglet",
    "demi.input.pyglet_backend",
)
LEGACY_TYPE_NAMES = frozenset(
    {
        "PygletApplication",
        "PygletInputBackend",
        "PygletWindowPort",
    }
)


def test_current_source_and_tests_have_no_pyglet_legacy_boundary() -> None:
    root = Path(__file__).parents[2]

    assert not (root / "src" / "demi" / "input" / "pyglet_backend.py").exists()

    references: dict[Path, set[str]] = {}
    for directory in (root / "src", root / "tests"):
        for path in directory.rglob("*.py"):
            found = _legacy_references(path)
            if found:
                references[path.relative_to(root)] = found

    assert references == {}


def _legacy_references(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names if _is_legacy_module(alias.name))
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            if _is_legacy_module(node.module):
                found.add(node.module)
        elif isinstance(node, ast.Name) and node.id in LEGACY_TYPE_NAMES:
            found.add(node.id)
    return found


def _is_legacy_module(module: str) -> bool:
    return any(
        module == prefix or module.startswith(f"{prefix}.") for prefix in LEGACY_MODULE_PREFIXES
    )
