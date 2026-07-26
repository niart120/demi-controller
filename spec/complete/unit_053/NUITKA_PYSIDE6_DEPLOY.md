# Nuitka / PySide6 Deploy パッケージング仕様書

## 1. 概要

### 1.1 目的

PyInstaller による旧 one-file builder を、PySide6 付属の `pyside6-deploy` を呼ぶ
Nuitka builder へ置き換える。Qt の収集対象は、実装で使用する Core、Gui、Widgets と、
起動に必要な `platforms` plugin に限定する。PySide6 の meta package は source runtime で維持し、
配布 artifact から不要な Qt Addons と plugin を除外する。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user request | Nuitka と PySide6 plugin による軽量化 | conversation |
| roadmap | PyInstaller / Nuitka の比較後に builder を固定する | `spec/initial/roadmap.md` |
| prior record | PyInstaller を採用した根拠と未検証事項 | `spec/complete/unit_010/PACKAGING.md` |
| risks | Qt plugin と runtime resource の収集監査 | `spec/initial/risks.md` |
| Qt documentation | `pyside6-deploy` は Nuitka wrapper で、Qt module / plugin を設定できる | https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-deploy.html |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| maintainer | locked dev environment、`packaging/build.py` | Nuitka による Windows standalone directory が生成される | Windows で native build する |
| GUI user | deployed `demi.exe` | Qt platform plugin を読み、GUI を起動できる | display / hardware acceptance は別検証 |
| release maintainer | `pysidedeploy.spec` | Qt Core / Gui / Widgets と platforms 以外を収集対象へ加えない | 将来の module 追加は明示的に設定を更新する |

## 2. 対象範囲

- `pyside6-deploy` を Nuitka の唯一の standalone builder とする。
- `PySide6` meta package を維持し、Nuitka artifact に不要な Qt Addons を収集しない。
- Qt module を Core、Gui、Widgets、plugin を platforms に固定した `pysidedeploy.spec` を version control する。
- Windows で standalone artifact をビルドし、`--version` と platform plugin の収集結果を確認する。
- builder metadata、license inventory、publishing runbook を現在の builder に揃える。

## 3. 対象外

- one-file executable。Nuitka の standalone directory を配布単位とする。
- QML、Qt Quick、WebEngine、SQL、SVG、画像形式、TLS の同梱。
- macOS / Linux の native build と clean environment acceptance。
- Bluetooth adapter、Bumble 接続、target device、exclusive mouse の実機確認。
- Qt のライセンス適合性に関する法的結論。

## 4. 関連 docs

- `spec/initial/roadmap.md`
- `spec/initial/risks.md`
- `spec/publishing.md`
- `spec/complete/unit_010/PACKAGING.md`
- `packaging/LICENSES.md`
- `src/demi/THIRD_PARTY_NOTICES.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| builder 選択 | package build | PyInstaller を実行せず PySide6 deploy / Nuitka を実行する | builder は一意 |
| Qt runtime 依存 | `uv sync --dev` | source runtime は PySide6 meta package を解決し、artifact は必要な Qt module / plugin だけを収集する | source 実行を維持 |
| Qt 配置 | `pysidedeploy.spec` | Core、Gui、Widgets と platforms が明示される | QML なし |
| artifact | `packaging/build.py` | `dist/standalone/demi.dist/demi.exe` と metadata / licenses が生成される | Windows path |
| version smoke | standalone artifact、`--version` | package metadata と一致し終了コード 0 | display 不要 |
| Qt plugin smoke | standalone artifact | `qwindows.dll` があり、plugin family は platforms だけである | GUI 操作不要 |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-skipped | packaging contract が PySide6 deploy / Nuitka と最小 Qt module / plugin を宣言し、PyInstaller を参照しない | new | package | `tests/unit/test_packaging.py` が green |
| green | source runtime は PySide6 meta package を維持し、artifact は Qt Addons を収集しない | new | package | source import failure を検証して方針を確定 |
| green | builder が standalone directory と metadata / license inventory を生成する | new | package | Windows native build が `demi.dist` を生成 |
| green | standalone artifact の version smoke が pass する | new | package | `demi.exe --version` が `0.1.0` を返した |
| green | standalone artifact が platforms plugin だけを含む | integration | package | `qwindows.dll` と plugin family を smoke で確認 |
| refactor-skipped | standard package / static / release gates が pass する | characterization | package | full gate と artifact smoke を完了 |

## 7. 設計メモ

- `pyside6-deploy` は PySide6 Essentials が提供する Nuitka wrapper である。Nuitka を直接起動せず、
  `pysidedeploy.spec` を builder 設定の正本にする。`project_dir` は `packaging` に固定し、
  repository root の `.uv-cache` を QML 探索対象にしない。
- `pyside6-deploy` は実行時に config へ検出結果と絶対 path を書き戻す。builder は正本の
  `pysidedeploy.spec` を `build/pyside6-deploy/` へ複製し、相対 source path を展開して渡す。
  これにより作業ツリーを変更せず、staging directory を探索根と誤認しない。
- `modules` は Core、Gui、Widgets、`plugins` は platforms のみを明示する。Windows では
  `qwindows.dll` が platform plugin となる。Nuitka plugin の既定 `sensible` collection を
  `--include-qt-plugins=platforms` と、対象ごとに繰り返す `--noinclude-qt-plugins` で絞り込む。
- Nuitka の main module が `demi` package を隠さないよう entry point は `launcher.py` とする。
  builder は生成後の `launcher.exe` だけを `demi.exe` に改名する。
- Windows standalone の初回 build は Nuitka が Dependency Walker を利用する。`extra_args` の
  `--assume-yes-for-downloads` は、その依存解析ツールを Nuitka の user cache へ取得する確認を
  非対話 build でも肯定する。
- `pyside6-deploy` の onefile mode は一時展開とトラブル診断を複雑にするため採用しない。
- GUI startup smoke では Qt 実行資源だけを観測し、Bluetooth 接続を起動条件に含めない。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `pyproject.toml` | modify | PySide6 meta package と Nuitka development dependency |
| `uv.lock` | modify | dependency lock の更新 |
| `pysidedeploy.spec` | new | PySide6 deploy / Nuitka と Qt runtime 設定 |
| `packaging/build.py` | modify | PyInstaller 呼び出しを PySide6 deploy に置換 |
| `packaging/smoke.py` | modify | standalone directory artifact を smoke |
| `packaging/launcher.py` | modify | builder-neutral な entry point |
| `packaging/LICENSES.md` | modify | source runtime と standalone artifact の Qt 構成を記録 |
| `src/demi/THIRD_PARTY_NOTICES.md` | modify | wheel notice を揃える |
| `spec/publishing.md` | modify | Nuitka standalone preflight を記録 |
| `tests/unit/test_packaging.py` | modify | package contract を更新 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/unit/test_packaging.py -q` | passed | 6 passed。config、builder、runtime dependency contract を確認 |
| `uv run pyside6-deploy --force --keep-deployment-files --config-file pysidedeploy.spec --dry-run` | passed with findings | root を探索すると `.uv-cache` の QML を拾うことを確認し、`project_dir=packaging` へ絞った |
| `uv run python packaging/build.py` | passed with warnings | Windows、Nuitka 4.0.8。Dependency Walker を user cache へ取得。`dumpbin` 未検出のため Qt dependency 自動解析は未実行 |
| `uv run python packaging/smoke.py` | passed | `demi.exe --version` が `0.1.0`。`qwindows.dll` と platforms のみを確認 |
| artifact inspection | passed | 121.8 MiB、53 files。Core / Gui / Widgets / Network DLL と platforms plugin 4 DLL |
| `uv run ty check --no-progress` with Essentials-only dependency | failed as expected | PySide6 package root がなく 90 import diagnostics。dependency replacement を棄却 |
| `uv sync --dev` | passed | 74 packages。PySide6 meta package と Nuitka 4.0.8 を同期 |
| `uv lock --check` | passed | lockfile は最新 |
| `uv run ruff format --check .` | passed | 154 files already formatted |
| `uv run ruff check .` | passed | All checks passed |
| `uv run ty check --no-progress` | passed | All checks passed |
| `uv run pytest tests/unit -p no:cacheprovider` | passed | 341 passed。cache provider は Windows の既存 cache permission を避けるため無効化 |
| `uv run pytest tests/integration -p no:cacheprovider` | passed | 133 passed。既存の `tmp/pytest` を削除後に実行 |
| `uv build` | passed | `demi_controller-0.1.0.tar.gz` と wheel を生成 |
| docs review | passed | 対象文書の事実整合、未検証表示、仮テキスト残りを確認 |
| `git diff --check` | passed | whitespace error なし |

## 10. 先送り事項

- macOS / Linux native build と clean environment acceptance は OS runner を確保した別 work unit で扱う。
- Qt plugin の追加が必要になった場合は、使用する Qt API と失敗する smoke を先に示してから
  `pysidedeploy.spec` を拡張する。
- Windows GUI を表示して操作する acceptance と Bumble/libusb の接続確認は未実行。version と plugin
  artifact の smoke を GUI acceptance と扱わない。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を作成した
- [x] 検証結果または未実行理由を実装後に記録した
- [x] package / release / public API に触れる場合の gate を記録した
