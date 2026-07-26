# USB DLL load diagnostics 仕様書

## 1. 概要

### 1.1 目的

Windows standalone application の USB adapter discovery で続く `FileNotFoundError` を診断し、Bumble が packaged `libusb_package` resource を探索せず、bundled `usb1/libusb-1.0.dll` を使うようにする。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user report | USB adapter open failure が解消しない | conversation |
| local log | 2026-07-26 16:53:33 に support diagnostics は成功したが、`ADAPTER_OPEN_FAILED` の root cause は `FileNotFoundError` | `Project_Demi/Logs/project-demi.log` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| support engineer | standalone の bundled libusb load が失敗する | DLL path の存在、Windows error code、例外種別を log から判別できる | raw exception message は記録しない |

## 2. 対象範囲

- `ctypes.WinDLL()` による bundled libusb load の失敗を限定して記録する。
- Bumble の `libusb_package.get_library_path()` を bundled DLL path に限定する。
- Nuitka の共用 cache ACL に依存しない build environment を設定する。

## 3. 対象外

- DLL search path や USB driver を変更する修正。
- USB adapter の実機 open を自動実行する test。
- raw exception message、ユーザー固有のディレクトリ名の記録。

## 4. 関連 docs

- `spec/complete/unit_055/STANDALONE_USB_RUNTIME_AND_METADATA.md`
- `spec/initial/risks.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| Bumble libusb lookup | Windows standalone、bundled `usb1/libusb-1.0.dll` | Bumble が resource package を探索せず、bundled DLL path を受け取る | `usb1.loadLibrary()` を先に完了する |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| green | bundled libusb path を Bumble の resource lookup に渡す | regression | unit | fake package module で観測 |
| green | Nuitka build が repository-scoped cache を使う | regression | package | 共用 cache ACL を避ける |
| green | standard gates が pass する | regression | unit | 実機 acceptance は user-operated |

## 7. 設計メモ

- 2026-07-26 17:19:16 の diagnostic log は Bumble dynamic import の `libusb_package` resource lookup が `FileNotFoundError` で失敗することを示した。
- インストール済み `libusb-package` は source-only で DLL を持たない。Bumble には既に loaded の `usb1/libusb-1.0.dll` を渡す。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/controller/swbt_adapter.py` | modify | bundled libusb path を Bumble helper に渡す |
| `tests/unit/controller/test_swbt_adapter.py` | modify | bundled path regression test |
| `packaging/build.py` | modify | repository-scoped Nuitka cache environment |
| `tests/unit/test_packaging.py` | modify | cache environment regression test |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/unit/controller/test_swbt_adapter.py -q -p no:cacheprovider --basetemp .tmp_pytest_056_red_retry` | failed as expected | bundled DLL load failure diagnostics が未実装 |
| `uv run pytest tests/unit/controller/test_swbt_adapter.py -q -p no:cacheprovider --basetemp .tmp_pytest_056_green_retry` | pass | 7 passed |
| `uv run pytest tests/unit/controller/test_swbt_adapter.py -q -p no:cacheprovider --basetemp .tmp_pytest_056_bumble_path_red` | failed as expected | Bumble resource lookup に bundled path を渡さない |
| `uv run pytest tests/unit/controller/test_swbt_adapter.py tests/unit/test_packaging.py -q -p no:cacheprovider --basetemp .tmp_pytest_056_bumble_path_green_final` | pass | 17 passed |
| `uv run pytest tests/unit/test_packaging.py -q -p no:cacheprovider --basetemp .tmp_pytest_056_cache_persistence_red` | failed as expected | Nuitka cache が reset 対象内 |
| `uv run pytest tests/unit/test_packaging.py -q -p no:cacheprovider --basetemp .tmp_pytest_056_cache_persistence_green` | pass | 9 passed |
| `uv run pytest tests/unit/test_packaging.py -q -p no:cacheprovider --basetemp .tmp_pytest_056_cache_red` | failed as expected | workspace-scoped cache environment が未実装 |
| `uv run pytest tests/unit/test_packaging.py -q -p no:cacheprovider --basetemp .tmp_pytest_056_cache_green` | pass | 9 passed |
| `uv lock --check` | pass | lockfile is consistent |
| `uv run ruff format --check .` | pass | 154 files already formatted |
| `uv run ruff check .` | pass | All checks passed |
| `uv run ty check --no-progress` | pass | All checks passed |
| `uv run pytest tests/unit -p no:cacheprovider --basetemp .tmp_pytest_056_final_unit` | pass | 348 passed |
| `uv run pytest tests/integration -p no:cacheprovider --basetemp .tmp_pytest_056_integration` | pass | 133 passed |
| `uv build` | pass | sandbox では network policy により失敗後、approved environment で sdist と wheel を作成 |
| `uv run python packaging/build.py` | pass with warnings | repository-scoped cache で `demi.exe` を作成。project file と `dumpbin` 未検出 warning は残る |
| `uv run python packaging/smoke.py` | pass | `demi.exe --version` が 0.1.0 を出力 |
| `git diff --check` | pass | whitespace error なし |
| standalone USB discovery acceptance | pass | 2026-07-26 17:32:11 の起動では、従来の `ADAPTER_OPEN_FAILED` と diagnostic error が発生しない |
| final standard gates | pass | ruff、ty、unit 347 passed、integration 133 passed |
| final package gates | pass | `uv build`、`packaging/build.py`、`packaging/smoke.py` を実行 |
| final standalone USB discovery | pass | 2026-07-26 17:43:59 の起動では `ADAPTER_OPEN_FAILED` と temporary diagnostic log が発生しない |

## 10. 先送り事項

- none

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を更新した
- [x] 検証結果または未実行理由を記録した
- [x] package / release / public API に触れる場合の gate を記録した
