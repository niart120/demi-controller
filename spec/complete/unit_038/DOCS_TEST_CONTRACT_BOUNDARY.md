# 文書テストの契約境界 仕様書

## 1. 概要

### 1.1 目的

自然言語の表現や作業記録の状態語を固定する pytest を通常の品質ゲートから除去し、自動検査と人間による文書レビューの責務を分ける。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| GitHub Issue #41 | 固定文言・禁止語・Markdown checkbox に依存する docs test を除去し、agent 向けの検証方針を見直す。 | `https://github.com/niart120/demi-controller/issues/41` |
| user request | まず不要なテストを掃除する。 | conversation |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| 文書の執筆者 | README、initial spec、完了仕様を意味を保って変更する | 旧説明や状態語を含むかだけでは pytest が失敗しない | リンク、構文、実在する製品契約は別途検査できる |
| CI | unit test を実行する | package、source、workflow など機械的に観測できる契約だけを失敗理由にする | 文書の意味・読みやすさは pytest の対象外 |

## 2. 対象範囲

- `test_documentation.py` と `test_work_unit_records.py` を削除する。
- `test_packaging.py` から README と initial spec の禁止語だけを検査する assertion を削除する。
- `AGENTS.md` と docs / TDD 関連 skill に自動検査と prose review の境界を記載する。
- docs test の pass を意味上の整合性と記録した既存 work unit record を訂正する。

## 3. 対象外

- CLI、package metadata、依存 lock、workflow、production source の機械的契約を検査する test の削除。
- Markdown link、frontmatter、YAML、TOML の機械的検査の廃止。
- spec / work unit 運用そのものの廃止。

## 4. 関連 docs

- `AGENTS.md`
- `spec/initial/testing.md`
- `.agents/skills/docs-quality-review/SKILL.md`
- `.agents/skills/tdd-test-list/SKILL.md`
- `.agents/skills/tdd-workflow/SKILL.md`
- `.agents/skills/test-desiderata-review/SKILL.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| 文書の言い換え | 説明文、見出し、説明順、作業状態の表記を変更する | その文字列だけを原因に unit test が失敗しない | 意味上の正しさは review で確認する |
| 旧 UI 依存の禁止 | metadata、lock、package builder、license inventory、production source を検査する | `pyglet` の runtime dependency、収集指定、legacy import があれば失敗する | 現行文書の単語検索は含めない |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-done | README、initial spec、完了仕様の固定文言と状態語だけを検査する test が通常 unit gate に存在しない | regression | unit | `test_documentation.py` と `test_work_unit_records.py` を削除し、`test_packaging.py` の文書禁止語 assertion を削除する |
| refactor-done | `AGENTS.md` と文書品質 review skill が、prose の誤りと test 設計の誤りを同列に調査する境界を示す | new | docs | 固定文言 test への一方向の追従を指示しない |
| refactor-done | TDD 関連 skill が、構文・参照・schema・実行可能な契約と prose review の責務を分ける | new | docs | docs-only 変更では確認した対象と方法を記録する |
| refactor-done | 既存完了仕様の docs test 結果が保証した範囲を、変更対象との関係に合わせて訂正する | regression | docs | PR #23 と #40 由来の記録を訂正した |

## 7. 設計メモ

### 確認済みの事実

- `tests/unit/test_documentation.py` は README と initial spec の固定表現を検査している。
- `tests/unit/test_work_unit_records.py` は complete record 内の状態語、checkbox、特定 deferred 行を検査している。
- `tests/unit/test_packaging.py` の一件は README と initial spec に `pyglet` がないことだけを検査している。
- metadata、lock、builder、license inventory と legacy import 境界は機械的に観測できる。

### 判断

上記三つの文書依存 test は、変更対象の意味を確認せず、正しい言い換えを回帰として扱うため削除する。機械的契約を検査する test は維持する。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `tests/unit/test_documentation.py` | delete | README と initial spec の固定文言 test を除去する。 |
| `tests/unit/test_work_unit_records.py` | delete | 作業記録の状態語・checkbox・特定文言を検査する test を除去する。 |
| `tests/unit/test_packaging.py` | modify | 現行文書の `pyglet` 禁止語 test を除去する。 |
| `AGENTS.md`、`.agents/skills/` | modify | 自動検査と prose review の境界を記載する。 |
| `spec/complete/unit_038/DOCS_TEST_CONTRACT_BOUNDARY.md` | new | scope、TDD 状態、検証、後続項目を記録する。 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv sync --dev` / `uv lock --check` | passed | 77 packages を解決し、74 packages を確認。 |
| `uv run pytest tests/unit --basetemp tmp\pytest\unit038` | passed | 274 passed。既定 temporary directory は access denied となったため、作業領域内の一時ディレクトリを指定した。 |
| `uv run ruff format --check .` | passed | 146 files already formatted。 |
| `uv run ruff check .` | passed | All checks passed。 |
| `uv run ty check --no-progress` | passed | All checks passed。 |
| `uv build` | passed | PyPI 接続を許可して sdist と wheel を作成。 |
| `git diff --check` | passed | whitespace error なし。 |
| `quick_validate.py` | passed | `docs-quality-review`、`tdd-test-list`、`tdd-workflow`、`test-desiderata-review` はすべて valid。 |
| docs-quality review | passed | `AGENTS.md`、4 skill、unit_018、unit_037、unit_038 を読み、fixed assertion の残存と仮テキストがないことを確認。 |
| agentic self-review | passed | Issue #41 の完了条件、対象外、diff、gate、未検証事項を照合。 |

## 10. 先送り事項

- none

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を更新した
- [x] 検証結果または未実行理由を記録した
- [x] package / release / public API に触れないことを確認した
