# Publishing Runbook

## Scope

`demi-controller` を PyPI / TestPyPI に公開するための runbook。

## Preconditions

- GitHub repository と Trusted Publishing が設定済み。
- `pyproject.toml`、`uv.lock`、release workflow が候補 version と一致している。
- default branch が clean。
- release PR が merge 済み。

## Local Preflight

```powershell
uv sync --dev
uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
uv run pytest tests/unit
uv build
uv run python packaging/build.py
uv run python packaging/smoke.py
uv run twine check --strict dist/*
git diff --check
```

## Stop Conditions

- production publish は、この turn の明示承認なしに実行しない。
- PyPI に同一 version が存在する場合は停止する。
- Trusted Publishing または workflow が未設定の場合は停止する。
- TestPyPI smoke が失敗した状態で production へ進まない。

## Post-publish Smoke

```powershell
uvx --from demi-controller==<version> python -c "import importlib.metadata; print(importlib.metadata.version('demi-controller'))"
```
