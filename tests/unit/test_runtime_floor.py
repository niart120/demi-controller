import tomllib
from pathlib import Path

import yaml

REPOSITORY_ROOT = Path(__file__).parents[2]


def test_package_and_ci_require_python_313_and_test_supported_versions() -> None:
    pyproject = tomllib.loads((REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    workflow = yaml.safe_load(
        (REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    )

    project = pyproject["project"]
    classifiers = project["classifiers"]
    matrix = workflow["jobs"]["test"]["strategy"]["matrix"]

    assert project["requires-python"] == ">=3.13"
    assert "Programming Language :: Python :: 3.12" not in classifiers
    assert "Programming Language :: Python :: 3.13" in classifiers
    assert "Programming Language :: Python :: 3.14" in classifiers
    assert pyproject["tool"]["ruff"]["target-version"] == "py313"
    assert pyproject["tool"]["ty"]["environment"]["python-version"] == "3.13"
    assert matrix["python-version"] == ["3.13", "3.14"]
    assert (REPOSITORY_ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.13"


def test_package_declares_swbt_v06_compatibility_range() -> None:
    pyproject = tomllib.loads((REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert "swbt-python>=0.6.0,<0.7.0" in pyproject["project"]["dependencies"]
