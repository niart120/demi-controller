# PySide6 Deploy 診断設定 仕様書

## 1. 概要

### 1.1 目的

Windows standalone build で `pyside6-deploy` が出す project file と `dumpbin` の
warning を、設定と依存解析の根拠を明示して解消する。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| GitHub issue #58 | PySide6 Deploy の project file と dumpbin warning の解消 | `https://github.com/niart120/demi-controller/issues/58` |
| 既存 package record | standalone build は成功するが両 warning が残る | `spec/complete/unit_053/NUITKA_PYSIDE6_DEPLOY.md` |
| 既存 package record | USB runtime 修正後も warning が残る | `spec/complete/unit_056/USB_DLL_LOAD_DIAGNOSTICS.md` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| release maintainer | Windows で `packaging/build.py` を実行する | Deploy が有効な project file と依存解析手段を使い、対象 warning を出さない | Qt module/plugin の明示的な収集範囲は変えない |

## 2. 対象範囲

- `pyside6-deploy` 用 project file を version control し、mutable config が正しく参照する。
- Windows の Qt DLL 依存解析を実行できる手段を build 前に解決する。
- build と standalone smoke で warning と artifact を確認する。

## 3. 対象外

- Nuitka / PySide6 Deploy 移行本体。
- SDL2、libusb、Qt plugin の収集設定と USB adapter 接続動作。
- Visual Studio Build Tools の自動インストール。

## 4. 関連 docs

- `spec/complete/unit_053/NUITKA_PYSIDE6_DEPLOY.md`
- `spec/complete/unit_056/USB_DLL_LOAD_DIAGNOSTICS.md`
- `pysidedeploy.spec`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| project file | mutable Deploy config | `packaging` 配下の有効な PySide project file を参照する | launcher を project source として宣言する |
| Qt dependency scan | Windows build environment | `dumpbin /dependents` と同等の Qt DLL 依存情報を取得する | 存在しない実行ファイルを warning として無視しない |
| standalone build | `packaging/build.py` | 対象 warning なしで `demi.exe` を生成する | Qt modules と plugins の明示設定を維持する |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| green | Deploy config が有効な project file を参照し、launcher を project source として宣言する | regression | package | `tests/unit/test_packaging.py` で固定 |
| green | Windows build environment が PySide6 Deploy の Qt DLL 依存解析を実行できる | regression | package | Visual Studio の x64 `dumpbin.exe` を PATH の先頭へ置く |
| green | Windows standalone build と smoke が対象 warning なしで通る | regression | package | 実ビルドで確認 |
| green | standard package / static / unit gate が通る | regression | package | docs review を含む |

## 7. 設計メモ

- PySide6 6.11 の `project_file` は `pyproject.toml` または `*.pyproject` である。
  `packaging/demi.pyproject` に standalone launcher だけを宣言する。QML、resource、UI file を
  持たない現行 packaging 境界では、追加の source 列挙は不要である。
- `packaging/build.py` は PATH 上の `dumpbin.exe` を優先し、なければ `ProgramFiles` と
  `ProgramFiles(x86)` 下の Visual Studio x64 host/target tool を探索して PATH の先頭へ置く。
  どちらにもない Windows build は、依存解析 warning を出したまま続行せず失敗する。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `packaging/demi.pyproject` | new | Deploy 用の project source 宣言 |
| `pysidedeploy.spec` | modify | project file 参照 |
| `packaging/build.py` | modify | 依存解析手段の解決 |
| `tests/unit/test_packaging.py` | modify | package contract regression |
| `spec/complete/unit_058/PYSIDE6_DEPLOY_DIAGNOSTICS.md` | new | scope と検証記録 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/unit/test_packaging.py -q -p no:cacheprovider --basetemp .tmp_pytest_058_project_red` | failed as expected | `project_file = demi.pyproject` が未設定で 1 failed、10 passed |
| `uv run pytest tests/unit/test_packaging.py -q -p no:cacheprovider --basetemp .tmp_pytest_058_project_green` | pass | project file 設定後に 11 passed |
| `uv run pytest tests/unit/test_packaging.py -q -p no:cacheprovider --basetemp .tmp_pytest_058_dumpbin_red` | failed as expected | Visual Studio の `dumpbin` directory を PATH へ追加しないため 1 failed、11 passed |
| `uv run pytest tests/unit/test_packaging.py -q -p no:cacheprovider --basetemp .tmp_pytest_058_dumpbin_green` | pass | `dumpbin` 解決後に 12 passed |
| `uv run python packaging/build.py` | pass | `Unable to resolve a valid project file` と `Unable to find dumpbin` は出力されない。Nuitka は Windows SDK 未導入の別 warning を出すが artifact を生成した。 |
| `uv run python packaging/smoke.py` | pass | `demi.exe: version 0.1.0` |
| `uv sync --dev` | pass | 74 packages を確認 |
| `uv lock --check` | pass | lockfile は最新 |
| `uv run ruff format --check .` | pass | 154 files already formatted |
| `uv run ruff check .` | pass | All checks passed |
| `uv run ty check --no-progress` | pass | All checks passed |
| `uv run pytest tests/unit` | not run | 既存 `tmp/pytest` の ACL により 341 passed 後の 18 setup error。変更に起因しない一時ディレクトリ失敗。 |
| `uv run pytest tests/unit -p no:cacheprovider --basetemp .tmp_pytest_058_full` | pass | 359 passed |
| `uv build` | pass | sandbox の PyPI 接続制限後、許可済み環境で sdist と wheel を生成 |
| `uv run twine check --strict dist/*.whl dist/*.tar.gz` | pass | wheel と sdist を確認。`dist/*` は standalone directory も含むため不適切。 |
| `uv run pytest tests/integration` | not applicable | package build 設定のみの変更で、integration の対象振る舞いを変更しない。 |
| docs review | pass | 本仕様の scope、検証根拠、未実行理由、仮テキストを確認。 |
| `git diff --check` | pass | whitespace error なし |

## 10. 先送り事項

- none

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を更新した
- [x] 検証結果または未実行理由を実装後に記録した
- [x] package / release / public API に触れる場合の gate を記録した
