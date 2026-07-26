# Standalone USB runtime と診断 metadata の修正仕様書

## 1. 概要

### 1.1 目的

Nuitka standalone artifact に含まれる `usb1/libusb-1.0.dll` を、USB adapter discovery の前に絶対パスで登録する。support diagnostics が参照する `swbt-python` の distribution metadata も artifact に含める。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user report | standalone application が USB adapter open に失敗した | conversation |
| local log | `ADAPTER_OPEN_FAILED` の root cause は `FileNotFoundError` | `Project_Demi/Logs/project-demi.log` |
| artifact inspection | `usb1/libusb-1.0.dll` は存在し、絶対パスの `WinDLL` load は成功した | `dist/standalone/demi.dist/` |
| source inspection | `usb1` は module `__file__` 基準で DLL を探索する | installed `libusb1` source |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| standalone application | Windows USB adapter discovery | packaged `usb1` DLL を使って enumeration を開始する | adapter の実機 open は別検証 |
| support engineer | application startup | support diagnostics に swbt version が記録される | package metadata を artifact に含める |

## 2. 対象範囲

- Windows で `usb1` package の bundled `libusb-1.0.dll` を明示 load する。
- Nuitka config に `swbt-python` metadata collection を加える。
- USB runtime preparation と metadata config の回帰 test を追加する。

## 3. 対象外

- WinUSB driver の導入、変更、実機 Bluetooth adapter の open。
- `swbt-python` 以外の distribution metadata の網羅収集。
- USB failure の raw exception text をログへ記録する変更。

## 4. 関連 docs

- `spec/complete/unit_054/STANDALONE_SDL_AND_USB_DIAGNOSTICS.md`
- `spec/initial/risks.md`
- `spec/publishing.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| USB DLL preparation | Windows、`usb1` bundled DLL | `usb1.loadLibrary()` が absolute DLL path の loader を受け取る | USB enumeration は行わない |
| diagnostics metadata | standalone Nuitka config | `swbt-python` metadata inclusion が明示される | `importlib.metadata.version()` を満たす |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| done | adapter discovery 前に bundled libusb DLL を absolute path で `usb1` に登録する | regression | unit | fake usb1 module で観測 |
| done | mutable Nuitka config が `swbt-python` metadata を含める | regression | package | config contract |
| done | standalone build / smoke と standard gates が pass する | regression | package | hardware acceptance は対象外 |

## 7. 設計メモ

- `usb1` の通常探索は module `__file__` に依存する。standalone artifact では探索位置がずれても、artifact 内 DLL の absolute path を明示すれば Windows loader が解決できる。
- support diagnostics は `swbt-python` だけを `importlib.metadata.version()` で参照するため、その distribution metadata だけを収集する。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `pyproject.toml` | modify | direct USB runtime dependency を宣言 |
| `uv.lock` | modify | dependency record を更新 |
| `packaging/build.py` | modify | Nuitka metadata collection を追加 |
| `packaging/LICENSES.md` | modify | direct USB runtime dependency の通知対象を追加 |
| `src/demi/THIRD_PARTY_NOTICES.md` | modify | direct USB runtime dependency の通知対象を追加 |
| `src/demi/controller/swbt_adapter.py` | modify | bundled libusb runtime preparation |
| `tests/unit/controller/test_swbt_adapter.py` | modify | absolute DLL path registration を確認 |
| `tests/unit/test_packaging.py` | modify | metadata collection config を確認 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/unit/controller/test_swbt_adapter.py tests/unit/test_packaging.py -q -p no:cacheprovider --basetemp .tmp_pytest_055_red` | failed as expected | DLL registration helper と metadata collection config が未実装 |
| `uv run pytest tests/unit/controller/test_swbt_adapter.py tests/unit/test_packaging.py -q -p no:cacheprovider --basetemp .tmp_pytest_055_green` | pass | 14 passed |
| `uv run pytest tests/unit/test_packaging.py -q -p no:cacheprovider --basetemp .tmp_pytest_055_license_green` | pass | 8 passed |
| `uv sync --dev` | pass | lockfile の解決済み 74 packages を確認 |
| `uv lock --check` | pass | lockfile は pyproject と整合 |
| `uv run ruff format --check .` | pass | 154 files already formatted |
| `uv run ruff check .` | pass | All checks passed |
| `uv run ty check --no-progress` | pass | All checks passed。旧一時ディレクトリの ACL に起因する走査警告あり |
| `uv run pytest tests/unit -p no:cacheprovider --basetemp .tmp_pytest_055_unit` | pass | 346 passed |
| `uv run pytest tests/integration -p no:cacheprovider --basetemp .tmp_pytest_055_integration` | pass | 133 passed |
| `uv build` | pass | `demi_controller-0.1.0` sdist と wheel を作成 |
| `uv run python packaging/build.py` | pass with warnings | `demi.exe` を作成。project file と `dumpbin` 未検出の PySide6 Deploy warning は残る |
| `uv run python packaging/smoke.py` | pass | `demi.exe --version` が 0.1.0 を出力 |
| artifact inspection | pass | `usb1/libusb-1.0.dll` (157,696 bytes)、`sdl2dll/dll/SDL2.dll` (1,586,176 bytes) を確認 |
| `git diff --check` | pass | whitespace error なし |

## 10. 先送り事項

- packaged USB adapter discovery / open の実機確認は、ユーザーが Windows driver と adapter を操作する acceptance として扱う。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を作成した
- [x] 検証結果または未実行理由を実装後に記録した
- [x] package / release / public API に触れる場合の gate を記録した
