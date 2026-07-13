# 旧 UI と pyglet の撤去 仕様書

## 1. 概要

### 1.1 目的

UI 再設計 milestone 1 として、pyglet を使う現行 GUI、入力境界、試験、配布設定を一括で撤去する。旧 UI と PySide6 UI の互換層や切替設定は作らず、後続 unit が旧設計へ依存できない状態にする。

撤去直後は引数なし GUI 起動と full gate が一時的に成立しなくてよい。ただし、package import、3つの version entry point、UI 以外の主要な機材不要試験、lockfile、wheel / sdist の生成は維持し、pyglet 欠落の traceback を利用者へ露出させない。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| UI redesign | 旧 UI の監査、維持する application / domain 境界、撤去完了条件 | `spec/ui-redesign/CURRENT_UI_REMOVAL.md` |
| milestone | milestone 1 の作業、許容する中間状態、完了条件 | `spec/ui-redesign/MILESTONES.md` |
| initial design | 現在は pyglet 前提であり、milestone 0 で PySide6 前提へ更新する必要がある | `spec/initial/` |
| completed history | 撤去対象を導入・配線・配布した履歴 | `spec/complete/unit_004/`, `spec/complete/unit_010/`, `spec/complete/unit_011/` |
| current source | pyglet UI、入力 adapter、composition root の具象 import | `src/demi/ui/`, `src/demi/input/pyglet_backend.py`, `src/demi/app.py` |
| current package | pyglet dependency、収集指定、license inventory、UI marker、release artifact workflow | `pyproject.toml`, `uv.lock`, `packaging/`, `.github/workflows/package.yml` |

milestone 0 は本 unit の前提条件であり、別の作業 unit は作成しない。完了済み作業仕様は当時の実装記録として保持し、現行仕様へ合わせて書き換えない。

仕様執筆時点の `spec/initial` には pyglet 前提が残っており、milestone 0 は未完了である。本 unit の実装着手前に milestone 0 を完了し、更新した初期仕様を実装判断の正本とする。

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| package user | pyglet を導入していない環境で `import demi` または version command を実行 | import と版表示が成功し、Qt display と GUI runnerを生成しない | CLI は traceback を表示しない |
| CLI user | 引数なし CLI を撤去直後に実行 | GUI 未実装を分類した非ゼロ status と安全な説明を返す | pyglet import error を原因表示にしない |
| maintainer | source、test、metadata、lock、builder を検索 | 現行 pyglet import、dependency、収集指定が0件になる | `spec/complete` の履歴は検索判定から除外する |
| release workflow | `v*` tag または手動 workflow | 旧 GUI を含む standalone artifact を発行しない | PySide6 standalone は milestone 7 まで再開しない |

## 2. 対象範囲

- `src/demi/ui` の現行 package と全ファイルを削除する。
- `src/demi/input/pyglet_backend.py` と pyglet 専用 export を削除する。
- `src/demi/app.py` から `PygletApplication`、`PygletInputBackend`、旧 view / toolbar / status / dialog、pyglet window factory の import、factory、具象 type hint を削除する。
- pyglet の window、drawing、key / mouse 定数、独自 hit test、main-thread queue drain を直接固定する test を削除する。
- application、CLI、lifecycle test から pyglet 固有 fake / assertion を除き、UI toolkit 非依存の既存契約だけを残す。
- `pyproject.toml` と `uv.lock` から pyglet を削除し、`ui` pytest marker の pyglet 固有文言を削除または marker 自体を後続 Qt test 用へ更新する。
- `packaging/build.py` の runtime package と `--collect-all pyglet`、`packaging/LICENSES.md` の pyglet inventory を削除する。
- `.github/workflows/package.yml` の tag 起動と artifact upload を停止または workflow 自体を削除し、旧 GUI artifact が release 経路へ到達しないことを repository test で固定する。
- `demi`、`project-demi`、`python -m demi` の `--version`、`import demi`、domain / config / input mapping / controller の対象試験を green に戻す。
- sdist と wheel に削除済み UI / pyglet backend が混入せず、package metadata が pyglet を要求しないことを確認する。

## 3. 対象外

- PySide6 dependency、`QApplication`、`QMainWindow` の追加。unit_014 が所有する。
- Qt key / mouse event、pointer capture、Raw Input、controller preview。unit_015 が所有する。
- Qt toolbar、status bar、settings dialog。unit_016 が所有する。
- Qt queued signal と production lifecycle の統合。unit_017 が所有する。
- README と `spec/initial` の PySide6 実装結果への最終同期、3 OS の実 display 受入。unit_018 が所有する。
- PyInstaller で PySide6 plugin を収集する standalone build、署名、artifact upload。milestone 7 の後続 unit が所有する。
- domain、controller runtime、設定 schema、入力 mapping、swbt adapter の意味変更。

## 4. 関連 docs

- `spec/ui-redesign/README.md`
- `spec/ui-redesign/CURRENT_UI_REMOVAL.md`
- `spec/ui-redesign/MILESTONES.md`
- `spec/initial/architecture.md`
- `spec/initial/input.md`
- `spec/initial/lifecycle.md`
- `spec/initial/testing.md`
- `spec/complete/unit_004/UI_AND_PYGLET.md`
- `spec/complete/unit_007/SETTINGS_MODAL.md`
- `spec/complete/unit_010/PACKAGING.md`
- `spec/complete/unit_011/APPLICATION_ASSEMBLY_AND_GUI_WIRING.md`
- `AGENTS.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| package を import する | pyglet 非導入、display なし | `import demi` が成功する | PySide6 もまだ要求しない |
| version を表示する | 3つの正規 entry point と `--version` | distribution metadata と同じ版、status 0 | GUI module を import しない |
| GUI 不在を通知する | 引数なし CLI、legacy UI 撤去済み | 分類済みの説明を stderr へ出し、非ゼロ status | traceback、秘密値、pyglet 欠落文を出さない |
| current source を検索する | `src` と現行 test | pyglet import、旧 UI class、pyglet key / mouse 定数が0件 | 完了履歴は判定外 |
| metadata を解決する | `uv lock --check` | pyglet distribution が dependency graph に存在しない | lockfile を手編集しない |
| package を作る | `uv build` | sdist / wheel が生成され、削除済み module を含まず pyglet を要求しない | standalone build ではない |
| release artifact を止める | tag / workflow 定義 | 旧 standalone の build と upload が起動しない | local builder の残存だけで release 可としない |
| UI 以外を維持する | domain、config、mapping、controller の対象試験 | pyglet 撤去を理由に失敗しない | full UI / lifecycle gate は中間状態では not run を許容 |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-skipped | pyglet 非導入環境で package import と `demi`、`project-demi`、`python -m demi` の version 表示が成功する | regression | package | `pyglet` importを失敗させるtestで既存のlazy import境界を固定。GUI runnerとdisplayを生成しない |
| refactor-skipped | 引数なし CLI は旧 UI 撤去中を安全に説明して非ゼロ status を返し、pyglet 欠落 traceback を表示しない | edge | unit | `demi`、module entry point、packaging launcherで同じstderrとstatus 1を確認。unit_014でGUI起動へ置換する |
| refactor-skipped | production source と現行 test の pyglet import、旧 UI class、pyglet固有 type / factory が0件になる | new | package | 旧package / backendを削除し、ASTでimportと具象型参照を検査。post-greenの追加構造整理は不要 |
| refactor-skipped | `pyproject.toml` と `uv.lock` の dependency graph に pyglet が存在しない | regression | package | runtime dependencyとpyglet固有pytest markerを削除し、`uv lock`で更新 |
| refactor-skipped | package builder と license inventory に pyglet の収集・列挙指定が存在しない | regression | package | `RUNTIME_PACKAGES`、PyInstaller collect指定、license inventoryから削除。PySide6 license追加はunit_014/018で扱う |
| refactor-skipped | tag または手動 package workflow が旧 standalone artifact を build / upload しない | regression | package | 旧`package.yml`を削除し、milestone 7までQt standalone workflowを作らない |
| todo | wheel と sdist が削除済み `demi.ui` と `demi.input.pyglet_backend` を含まず、pyglet を依存に持たない | regression | package | `uv build` 後の metadata / contents smoke |
| todo | domain、config、input mapping、controller runtime の機材不要対象試験が pyglet なしで成功する | characterization | unit | GUI / lifecycle test の未復旧を分離する |

## 7. 設計メモ

### 7.1 確認済みの事実

- 現行 `pyproject.toml` は `pyglet>=2.1,<2.2` を runtime dependency に持ち、`uv.lock` は pyglet 2.1.15 を解決している。
- 現行 `src/demi/ui` は window、controller view、dialog、event bridge、toolbar、status bar を所有し、`src/demi/input/pyglet_backend.py` は pyglet key / mouse event を正規化している。
- 現行 `src/demi/app.py` は上記具象型を import し、production composition root で組み立てている。
- 現行 package workflow は3 OSで PyInstaller artifact を build、smoke、upload し、`v*` tag から起動する。

### 7.2 採用する境界

- 旧 `src/demi/ui` から表示 model だけを抜き取って残す方法は採用しない。後続 Qt UI は新しい module と責務で作る。
- `ApplicationSession`、`CaptureCoordinator`、`InputPublisher`、`ApplicationShutdownCoordinator` の toolkit 非依存の振る舞いは維持する。具象 UI 型を参照している箇所だけを切り離す。
- package workflow は誤 release を防ぐため fail-open にしない。旧 artifact を発行しないことを自動試験で観測する。
- GUI 不在は短期の作業 branch 状態であり、default branch へ release 可能な状態として取り込まない。

### 7.3 unit 間の引き渡し

- 着手条件: milestone 0 により `spec/initial` の採用 UI、input、lifecycle、testing、risk、diagnostics を PySide6 前提へ更新する。仕様執筆時点では未完了である。
- unit_014 へ渡す条件: pyglet の production / package 境界が消え、package import、version entry point、lock、source package build が成立し、GUI 不在が安全に分類されている。
- unit_014 は引数なし CLI の一時エラーを PySide6 application shell の起動へ置換する。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/ui/` | delete | 旧 pyglet UI package 全体 |
| `src/demi/input/pyglet_backend.py` | delete | pyglet key / mouse adapter |
| `src/demi/input/__init__.py` | modify | pyglet backend export の削除 |
| `src/demi/app.py` | modify | 旧 UI import、factory、具象 type / composition の撤去 |
| `src/demi/cli.py` | modify | GUI 不在の安全な中間 status が必要な場合の境界 |
| `tests/unit/ui/` | delete | 旧 pyglet UI 契約 test |
| `tests/unit/input/test_pyglet_backend.py` | delete | pyglet adapter test |
| `tests/unit/test_pyglet_import_boundary.py` | delete | pyglet 遅延 import 契約 test |
| `tests/unit/application/`, `tests/integration/lifecycle/` | modify | pyglet 具象 fake / assertion の撤去、toolkit 非依存契約の維持 |
| `pyproject.toml` | modify | pyglet dependency と pytest marker 文言の削除 |
| `uv.lock` | modify | pyglet distribution の削除 |
| `packaging/build.py` | modify | pyglet runtime inventory と収集指定の削除 |
| `packaging/LICENSES.md` | modify | pyglet license inventory の削除 |
| `.github/workflows/package.yml` | modify / delete | 旧 standalone artifact の tag build / upload 停止 |
| `tests/unit/test_packaging.py` | modify | release artifact 停止と pyglet 収集0件の契約 |
| `spec/wip/unit_013/LEGACY_UI_AND_PYGLET_REMOVAL.md` | modify | TDD 状態、検証、引き渡し記録 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `rg -n "T[O]DO|T[B]D|x[x]x|前[回]|今[回]|一[旦]|上[述]|適[宜]|必要に応じ[て]" spec/wip/unit_013` | passed | 該当なし |
| `git diff --no-index --check -- NUL spec/wip/unit_013/LEGACY_UI_AND_PYGLET_REMOVAL.md` | passed | whitespace errorなし。LF / CRLF変換予告のみ |
| `uv run pytest tests/unit/test_cli.py -q` | expected failed | red: 引数なしの`main([])`が旧GUI実行器を呼び、置換したtestの`AssertionError`で失敗した |
| `uv run pytest tests/unit/test_cli.py -q` | passed (6 passed) | green: 引数なしの`demi`、module entry point、packaging launcherがGUI更新中の説明をstderrへ出してstatus 1で終了する |
| `uv run pytest tests/unit/test_cli.py -q` | passed (7 passed) | characterization: `pyglet` importを禁止してもpackage importとversion出力が成功した |
| `uv run ruff format --check src/demi/cli.py tests/unit/test_cli.py` | passed | 2 files already formatted |
| `uv run ruff check src/demi/cli.py tests/unit/test_cli.py` | passed | CLI境界と対象testにlint指摘なし |
| `uv run ty check --no-progress` | passed | import hookを標準ライブラリの`__import__`シグネチャで型付けし、ignore / castなし |
| `uv run pytest tests/unit/test_legacy_ui_removal.py -q` | expected failed | red: `src/demi/ui`が存在したため旧UI撤去契約に失敗した |
| `uv run pytest tests/unit/test_legacy_ui_removal.py -q` | passed (1 passed) | green: 旧UI packageとpyglet backendがなく、source / testの旧importと具象型参照がない |
| `uv run pytest tests/unit -q` | passed (154 passed) | 旧UI専用testを削除し、domain / config / mapping / controller / applicationの機材不要試験がgreen |
| `uv run pytest tests/integration -q` | passed (12 passed) | 旧GUI assemblyを除き、controller runtimeのintegration契約がgreen |
| `uv run ruff format --check .` | passed (75 files) | formatter差分なし |
| `uv run ruff check .` | passed | lint指摘なし |
| `uv run ty check --no-progress` | passed | discard event sinkが`RuntimeEventSink.emit(event=...)`契約を満たす |
| `rg -n -i '(^|\s)(from|import)\s+pyglet|from\s+demi\.ui|from\s+demi\.input\.pyglet_backend|\b(PygletApplication|PygletInputBackend|PygletWindowPort)\b' src tests --glob '!test_legacy_ui_removal.py'` | passed | legacy import / concrete boundary参照なし |
| `git diff --check` | passed | whitespace errorなし |
| `uv run pytest tests/unit/test_packaging.py -q` | expected failed | red: `pyproject.toml`にpyglet runtime dependencyが残っていた |
| `uv lock` | passed | 73 packagesを解決し、pyglet 2.1.15を削除した |
| `uv run pytest tests/unit/test_packaging.py -q` | passed (3 passed) | green: project metadataとlockfileにpygletがない |
| `uv lock --check` | passed | lockfileがmetadataと整合する |
| `uv run ruff format --check tests/unit/test_packaging.py` | passed | formatter差分なし |
| `uv run ruff check tests/unit/test_packaging.py` | passed | lint指摘なし |
| `uv run pytest tests/unit/test_packaging.py -q` | expected failed | red: builderのruntime packageとlicense inventoryにpygletが残っていた |
| `uv run pytest tests/unit/test_packaging.py -q` | passed (4 passed) | green: builderとlicense inventoryにpyglet参照がない |
| `uv run ruff format --check packaging/build.py tests/unit/test_packaging.py` | passed | formatter差分なし |
| `uv run ruff check packaging/build.py tests/unit/test_packaging.py` | passed | lint指摘なし |
| `uv run pytest tests/unit/test_packaging.py -q` | expected failed | red: 旧`package.yml`がtag / manual artifact経路として残っていた |
| `uv run pytest tests/unit/test_packaging.py -q` | passed (4 passed) | green: 旧package workflowは存在せず、artifact build / uploadの入口がない |
| `uv run ruff format --check tests/unit/test_packaging.py` | passed | formatter差分なし |
| `uv run ruff check tests/unit/test_packaging.py` | passed | lint指摘なし |
| `uv lock --check` | not run | 仕様執筆だけで dependency を変更していない。実装時に pyglet 削除後の lock を検証する |
| `uv run pytest tests/unit` | not run | 仕様執筆だけで production / test を変更していない |
| `uv run pytest tests/integration` | not run | 仕様執筆だけで production / test を変更していない |
| `uv build` | not run | 仕様執筆だけで package metadata を変更していない。実装時は必須 |

full unit / integration gate は旧 GUI の置換前に green でない可能性がある。unit_013 の完了判定では、失敗を一括で許容せず、削除した GUI 契約に限定した失敗であることと、上表の package / non-UI 対象 gate が green であることを記録する。

## 10. 先送り事項

| 観測 | 先送り理由 | 後続の置き場 |
|---|---|---|
| 引数なし GUI 起動は撤去直後に利用不能 | application shell は pyglet 撤去と別のTDD境界 | `spec/wip/unit_014/PYSIDE6_APPLICATION_SHELL.md` |
| PySide6 / Qt の license inventory は未確定 | dependency版と配布範囲が未決定 | unit_014 で dependencyを固定し、unit_018 で source / wheel noticeを受入 |
| PySide6 standalone artifact は未検証 | Qt plugin、署名、clean environmentを別に検証する必要がある | milestone 7 の後続 unit |

## 11. チェックリスト

- [ ] milestone 0 の初期仕様更新が完了している
- [ ] `src/demi/ui` と `pyglet_backend.py` を一括削除した
- [ ] app、test、type、factory から pyglet 具象依存を削除した
- [ ] metadata、lock、builder、license、pytest marker から pyglet を削除した
- [ ] 旧 standalone release artifact を停止した
- [ ] package import、3 version entry point、non-UI対象試験を確認した
- [ ] TDD Test List を更新した
- [ ] 検証結果と未実行理由を記録した
- [ ] unit_014 への引き渡し条件を満たした
