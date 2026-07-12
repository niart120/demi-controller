# プロジェクト初期化 仕様書

## 1. 概要

### 1.1 目的

Unit 001 の scaffold を、後続 unit が実装と検証へ進める最小の実行基盤として確定する。Python 3.12、uv、ruff、ty、pytest を使い、パッケージ版メタデータと CLI の起動面を機材なしで確認できる状態にする。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| roadmap | Unit 001 の成果、完了条件、`python -m demi --version` | `spec/initial/roadmap.md` |
| project guide | 現在の配布名 `demi-controller`、CLI `demi`、標準 gate | `AGENTS.md` |
| initial naming | 製品名、import ルート、当初の CLI 名 | `spec/initial/naming.md` |
| initial requirements | `project-demi` と `python -m demi` の起動契約 | `spec/initial/requirements.md` |
| existing scaffold | 現在の package metadata、CLI、package test | `pyproject.toml`, `src/demi`, `tests/unit` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| 開発者 / console script | `uv run demi --version` | 配布メタデータと一致する `0.1.0` を表示して終了する | Bluetooth 機材不要 |
| 開発者 / module entry point | `uv run python -m demi --version` | console script と同じ版を表示して終了する | GUI はこの unit の対象外 |
| 開発者 / compatibility script | `uv run project-demi --version` | `demi` と同じ CLI 結果を表示する | 配布名の変更は行わない |
| CI / repository | push または pull request | lock、静的検査、unit test、build を実行する | hardware、bumble、UI 実機試験は含めない |

## 2. 対象範囲

- `demi` の console script と `python -m demi` の共通 CLI 境界。
- `project-demi` を同じ CLI へ向ける互換 console script。
- `--version` の出力と package metadata の版の一致。
- Python 3.12 を使う最小 GitHub Actions gate。
- 後続 unit が利用する `spec/wip` の作業仕様配置。

## 3. 対象外

- Bluetooth アダプター、Switch 本体、Bumble を用いた検証。
- pyglet ウィンドウ、入力捕捉、設定、ドメイン型、接続 runtime。
- 配布名を `demi-controller` から `project-demi` へ変更すること。
- GUI の起動。これは Unit 004 で扱う。

## 4. 関連 docs

- `spec/initial/roadmap.md`
- `spec/initial/requirements.md`
- `spec/initial/architecture.md`
- `spec/initial/AGENTIC_SDD.md`
- `AGENTS.md`
- `SKILLS.md`
- `spec/publishing.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| CLI が版を表示する | `--version` | `demi-controller` の metadata 版を標準出力へ 1 行表示し、終了コード 0 を返す | `__version__` と metadata の二重管理を検査する |
| module entry point が CLI を委譲する | `python -m demi --version` | console script と同じ出力・終了コードになる | `demi.__main__` を追加する |
| 互換 CLI が同じ処理を使う | `project-demi --version` | `demi --version` と同じ出力になる | 正規 CLI は `demi` のまま維持する |
| package が typed import を公開する | wheel / source distribution の build 後 | `demi` を import でき、版と `py.typed` が存在する | build の検証はネットワーク依存のため実行結果を記録する |
| CI が標準 gate を実行する | push / pull request | lock、format、lint、ty、unit test、build が順に実行される | 実機系 marker は CI へ含めない |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-skipped | `demi --version` と `python -m demi --version` が同じ版を表示する | new | package | `main` と module entry point を追加。behavior を保つ追加整理は不要 |
| refactor-skipped | `project-demi --version` が canonical CLI と同じ結果になる | new | package | entry point を metadata に追加。追加 refactor は不要 |
| refactor-skipped | build した配布物が metadata、import ルート、`py.typed` を保持する | characterization | package | wheel/source distribution と package smoke を確認。追加 refactor は不要 |
| refactor-skipped | push / pull request の CI が標準 gate を実行する | characterization | package | 初期 commit の workflow が gate を満たすことをテストで確認。workflow 自体の変更は不要 |

## 7. 設計メモ

現在の `AGENTS.md` と `pyproject.toml` は配布名を `demi-controller`、正規 CLI を `demi` と定義している。一方、roadmap、naming、development journal は `project-demi` を初期設計上の配布名または CLI として記録している。本 unit では直接の repo guide と既存 package test の契約を維持し、`project-demi` は同じ CLI への互換 entry point として提供する。配布名そのものの変更は、別の Intent Delta がない限り対象外とする。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/cli.py` | modify | CLI 引数と版表示 |
| `src/demi/__main__.py` | new | module entry point |
| `pyproject.toml` | modify | `project-demi` compatibility script |
| `tests/unit/test_cli.py` | new | CLI の同一出力契約 |
| `tests/unit/test_package.py` | modify | package smoke の不足分がある場合だけ更新 |
| `.github/workflows/ci.yml` | verify | 初期 commit の CI gate |
| `.github/PULL_REQUEST_TEMPLATE.md` | verify | 初期 commit の merge evidence 欄 |
| `spec/complete/unit_001/PROJECT_BOOTSTRAP.md` | new / modify | TDD 状態、検証、完了記録 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv sync --dev` | passed | 2026-07-13、依存解決完了 |
| `uv lock --check` | passed | 変更前 scaffold |
| `uv run ruff format --check .` | passed | 3 files already formatted |
| `uv run ruff check .` | passed | 変更前 scaffold |
| `uv run ty check --no-progress` | passed | 変更前 scaffold |
| `uv run pytest tests/unit` | passed | 1 passed、変更前 scaffold |
| `uv build` | failed | 変更前 scaffold では sandbox のネットワーク制限で `uv-build` を取得できなかった。実装後に承認付きで再実行して passed |
| `uv run demi --version` | failed | 変更前 CLI は引数を処理せず `Project_Demi` を表示したため、TDD で版表示へ置き換えた |
| `uv run python -m demi --version` | failed | `demi.__main__` が存在しない |
| `uv run pytest tests/unit` | passed | 3 passed。CLI と既存 package test |
| `uv run ruff format --check src/demi/cli.py src/demi/__main__.py tests/unit/test_cli.py` | passed | 3 files already formatted |
| `uv run ruff check src/demi/cli.py src/demi/__main__.py tests/unit/test_cli.py` | passed | All checks passed |
| `uv run ty check --no-progress` | passed | All checks passed |
| `uv run python -m demi --version` | passed | `0.1.0` |
| `uv run demi --version` | passed | `0.1.0` |
| `uv lock` | passed | package metadata 変更後も 40 packages を解決 |
| `uv sync --dev` | passed | 承認付き実行で editable package を再構築 |
| `uv run pytest tests/unit/test_cli.py::test_project_demi_compatibility_script_points_to_the_canonical_cli` | passed | 1 passed |
| `uv run project-demi --version` | passed | `0.1.0`。`demi` と同じ出力 |
| `uv lock --check` | passed | package metadata 変更後 |
| `uv build` | passed | `dist/demi_controller-0.1.0.tar.gz` と `dist/demi_controller-0.1.0-py3-none-any.whl` を生成 |
| wheel contents inspection | passed | metadata、`demi/__init__.py`、`demi/py.typed` を確認 |
| source distribution contents inspection | passed | `PKG-INFO` と `src/demi/py.typed` を確認 |
| package smoke via `uv run python -c` | passed | metadata 版、import、`py.typed` を確認。`0.1.0` |
| `uv run pytest tests/unit/test_ci.py` | passed | workflow の標準 gate と Python 3.12、pull request trigger を確認 |
| CI YAML parse via `uv run python -c` | passed | PyYAML で workflow を読み込み、Python 3.12 / 3.13 matrix を確認 |
| `uv run pytest tests/unit` | passed | 5 passed |
| `uv run ruff format --check .` | passed | 4 files already formatted |
| `uv run ruff check .` | passed | All checks passed |
| `uv run ty check --no-progress` | passed | All checks passed |
| `git diff --check` | passed | whitespace error なし |

## 10. 先送り事項

- GUI 起動と設定ファイルの初回生成は Unit 004 以降で扱う。
- 配布名の canonical 化方針は、現在の `AGENTS.md` と初期設計の差分として記録し、別途 Intent Delta がある場合に再判断する。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を作成した
- [x] 検証結果または未実行理由を実装後に更新した
- [x] package / release / public API に触れる gate を完了した
- [x] 完了時に `spec/complete/unit_001` へ移動した
