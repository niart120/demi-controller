# Standalone SDL と USB 診断の修正仕様書

## 1. 概要

### 1.1 目的

Nuitka standalone artifact に `pysdl2-dll` の SDL2 runtime DLL を確実に収集する。
USB adapter の失敗時には、GUI に安全な分類だけを表示したまま、ローカルログに元例外の型と許可した診断属性を記録する。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user report | standalone artifact が `pysdl2-dll` を source-only と警告し、USB adapter を開けない | conversation |
| artifact inspection | `sdl2dll/dll/SDL2.dll` が artifact にない。一方 `usb1/libusb-1.0.dll` はある | `dist/standalone/demi.dist/` |
| prior package record | Nuitka / PySide6 Deploy standalone builder の構成 | `spec/complete/unit_053/NUITKA_PYSIDE6_DEPLOY.md` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| release maintainer | Windows standalone build | `sdl2dll/dll/SDL2.dll` を含む artifact が生成される | installed `pysdl2-dll` の DLL directory を使う |
| application user | USB adapter discovery/open failure | GUI は既存の安全な分類を表示する | raw exception message は GUI へ出さない |
| support engineer | local application log | failure category、diagnostic id、root cause type、許可属性を確認できる | bond data、adapter id、raw exception text を記録しない |

## 2. 対象範囲

- `pysidedeploy.spec` の mutable build configuration に SDL2 DLL 用の Nuitka user package config を加える。
- build smoke で `sdl2dll/dll/SDL2.dll` の収集を確認する。
- runtime event に allowlist 方式の診断属性を載せ、application log へ記録する。
- packaging と controller runtime の回帰 test を追加する。

## 3. 対象外

- Bluetooth adapter、WinUSB driver、target device の実機検証。
- raw exception message、bond file path、adapter identifier のログ出力。
- `libusb` の収集方式または Qt plugin 構成の変更。

## 4. 関連 docs

- `spec/initial/risks.md`
- `spec/complete/unit_053/NUITKA_PYSIDE6_DEPLOY.md`
- `spec/publishing.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| SDL2 DLL collection | installed `sdl2dll/dll` | generated Nuitka config が `SDL2.dll` を `sdl2dll/dll` へ配置する | Nuitka user package config を使う |
| artifact smoke | Windows standalone directory | `sdl2dll/dll/SDL2.dll` が存在する | `--include-package-data` は DLL を収集しない |
| USB failure diagnostic | adapter exception chain | root cause type と allowlist attributes を event に載せる | raw message は除外する |
| local log | `ControllerError` | category、diagnostic id、diagnostic attributes を記録する | GUI text は変更しない |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| green | mutable Nuitka config が installed SDL2 DLL directory を artifact の `sdl2dll/dll` に収集する | regression | package | Nuitka user package config を指定する test が green |
| green | Windows artifact smoke が `SDL2.dll` の欠落を失敗にする | regression | package | filesystem contract が green |
| green | adapter failure event が root cause type と allowlist USB discovery attributes を保持する | regression | unit | raw message を含めない |
| green | application log callback が category ではなく安全な diagnostic event を受け取る | regression | unit | GUI message は変更しない |
| refactor-skipped | standalone build と standard gates が pass する | regression | package | hardware acceptance は対象外 |

## 7. 設計メモ

- Nuitka の `--include-package-data` と `--include-data-dir` は DLL を data file として収集しない。`sdl2dll` package に対する Nuitka user package config で `SDL2.dll` を明示収集する。
- `pyside6-deploy` が正本 config を書き戻すため、既存どおり mutable config へ build-time absolute path を書く。
- 診断属性は `backend`、`platform`、`libusb_available`、`bumble_version` の allowlist と root cause type に限定する。例外本文は log に渡さない。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `packaging/build.py` | modify | Nuitka user package config を mutable deploy config へ加える |
| `packaging/nuitka-package.config.yml` | new | `sdl2dll` の SDL2 runtime DLL 収集規則 |
| `packaging/smoke.py` | modify | SDL2 artifact collection を確認 |
| `src/demi/controller/events.py` | modify | safe diagnostic context を event に追加 |
| `src/demi/controller/runtime.py` | modify | exception chain から allowlist diagnostic context を生成 |
| `src/demi/app.py` | modify | diagnostic context を local log に記録 |
| `tests/unit/test_packaging.py` | modify | SDL2 collection contract を確認 |
| `tests/unit/controller/test_runtime.py` | modify | USB discovery diagnostic context を確認 |
| `tests/unit/application/test_app.py` | modify | application logging boundary を確認 |
| `spec/initial/risks.md` | modify | SDL2 runtime collection の確認済み範囲を更新 |
| `spec/publishing.md` | modify | standalone smoke の SDL2 contract を更新 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/unit/test_packaging.py -q -p no:cacheprovider --basetemp .tmp_pytest_054_package` | passed | 8 passed。SDL2 collection config と smoke contract を確認 |
| `uv run pytest tests/unit/controller/test_runtime.py -q -p no:cacheprovider --basetemp .tmp_pytest_054_runtime` | passed | 21 passed。allowlist USB diagnostics を確認 |
| `uv run pytest tests/unit/application/test_app.py -q -p no:cacheprovider --basetemp .tmp_pytest_054_app` | passed | 20 passed。exception summary を log へ出さないことを確認 |
| `uv run python packaging/build.py` | passed with warnings | `sdl2dll/dll/SDL2.dll` を含む Windows artifact を生成。project file と `dumpbin` 未検出の warning は継続 |
| `uv run python packaging/smoke.py` | passed | `demi.exe: version 0.1.0`。Qt platform plugin と SDL2 runtime を確認 |
| `uv sync --dev` | passed | 74 packages を解決 |
| `uv lock --check` | passed | lockfile は最新 |
| `uv run ruff format --check .` | passed | 154 files already formatted |
| `uv run ruff check .` | passed | All checks passed |
| `uv run ty check --no-progress` | passed | All checks passed |
| `uv run pytest tests/unit -p no:cacheprovider --basetemp .tmp_pytest_054_unit` | passed | 345 passed |
| `uv run pytest tests/integration -p no:cacheprovider --basetemp .tmp_pytest_054_integration` | passed | 133 passed |
| `uv build` | passed | source distribution と wheel を生成 |
| `git diff --check` | passed | whitespace error なし |

## 10. 先送り事項

- 実機での USB adapter open failure の原因特定は、WinUSB driver、adapter占有、機器構成を含むため別の hardware acceptance とする。local log は root cause type と allowlist attributes までを記録する。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を作成した
- [x] 検証結果または未実行理由を実装後に記録した
- [x] package / release / public API に触れる場合の gate を記録した
