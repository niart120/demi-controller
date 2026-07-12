# Quality Gates

## Local Gate

通常の変更:

```powershell
uv sync --dev
uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
uv run pytest tests/unit
git diff --check
```

package / release / public metadata を触る変更:

```powershell
uv build
uv run twine check --strict dist/*
```

## 判定

- command と結果を PR 本文または work unit に記録する。
- 未実行の gate は `not run` とし、理由を書く。
- 対象外の gate は `not applicable` とし、なぜ対象外かを書く。
- warning を確認済みとして握りつぶさない。
- README、docs、spec、skill、PR 本文を変更した場合は `$docs-quality-review` で文言、置き場所、根拠を確認する。
- 公開 API の型注釈、`py.typed`、`type ignore`、`cast()` を変更した場合は `$type-boundary-review` で型境界を確認する。
- 公開 API の docstring、README/docs の API 説明、D 系 lint を変更した場合は `$docstring-style` で契約と文言を確認する。
