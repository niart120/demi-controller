# OS 別移植確認 仕様書

## 1. 概要

### 1.1 目的

Windows、macOS、Linux の各 runner で、display や Bluetooth 機材を必要としない source-level の unit / integration gate を実行できる CI matrix を整える。OS 固有処理は既存の platformdirs、pyglet 境界、fake adapter に閉じ込め、未実行の表示・排他マウス・実機確認を確認済みと誤記しない。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| roadmap | macOS、Linux の起動、設定、pyglet 入力、排他マウス、adapter 列挙の移植確認 | `spec/initial/roadmap.md` |
| requirements | OS 固有処理の隔離、パス・設定保存先の固定禁止、OS 別 build | `spec/initial/requirements.md` |
| testing | OS matrix、display-free UI、hardware 分離 | `spec/initial/testing.md` |
| architecture | pyglet / swbt の import 境界、platform adapter の位置 | `spec/initial/architecture.md` |
| user scope | Bluetooth / Switch 本体の実機検証完了は対象外 | user request |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| CI | Windows / macOS / Linux、Python 3.12 / 3.13 | 同じ unit、integration、static、build gate を各 OS で実行する | hardware / bumble は選択しない |
| config boundary | platformdirs が OS ごとの user path を返す | `SettingsPaths` が Path として設定・データ・ログを保持する | OS 固有の区切り文字を組み立てない |
| input/UI boundary | fake window、pyglet event protocol、display なし | key、mouse、focus、capture の既存契約を確認できる | 実ウィンドウと排他 mouse は未検証 |
| controller boundary | fake adapter / swbt public values | adapter 列挙と lifecycle の契約を OS matrix で確認する | USB Bluetooth と target device は未使用 |

## 2. 対象範囲

- GitHub Actions の CI runner を Windows、macOS、Linux の matrix へ広げる。
- Python 3.12 / 3.13 の両方で unit と integration を実行する。
- static gate、lock check、package build を各 matrix job で維持する。
- CI workflow の matrix と integration gate を repository test で回帰固定する。
- macOS / Linux の実機、実表示、排他 mouse、Bluetooth adapter、Switch 接続の確認範囲を記録する。

## 3. 対象外

- macOS / Linux の実ウィンドウ表示、OpenGL、フォント、DPI、排他 mouse の手動確認。
- Bluetooth dongle、Bumble、Switch 本体を使う adapter 列挙・pairing・入力。
- OS 固有の sleep 通知、Raw Input、追加 input backend。
- OS 別配布物の clean environment 起動と standalone packaging（Unit 010）。
- CI runner 上の hardware / bumble marker を有効化すること。

## 4. 関連 docs

- `spec/initial/roadmap.md`
- `spec/initial/requirements.md`
- `spec/initial/testing.md`
- `spec/initial/architecture.md`
- `spec/complete/unit_004/UI_AND_PYGLET.md`
- `spec/complete/unit_006/SWBT_ADAPTER.md`
- `spec/complete/unit_008/HARDWARE_STABILITY.md`
- `spec/hardware-test-log.md`
- `AGENTS.md`
- `SKILLS.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| OS matrix を生成する | Windows / macOS / Linux × Python 3.12 / 3.13 | 同じ gate command が各組み合わせで実行される | 交差 build は行わない |
| unit gate を実行する | matrix runner、display-free tests | domain、input、config、application、UI boundary の unit が通る | 実表示を要求しない |
| integration gate を実行する | matrix runner、fake adapter / fake window | runtime、swbt public boundary、settings modal の integration が通る | hardware は対象外 |
| path を解決する | OS ごとの platformdirs | config、data、log path が `Path` として扱われる | user path の実値は OS ごとに異なる |
| 未検証範囲を表示する | Linux / macOS の実表示・排他 mouse・hardware | experimental / not run と記録される | CI pass を実機互換性の証拠にしない |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| green | CI が Windows / macOS / Linux × Python 3.12 / 3.13 matrix を持つ | new / regression | package | workflow の構造を repository test で確認した |
| green | 各 matrix job が unit と integration gate を実行する | new / regression | package | hardware / bumble は通常 job から除外する workflow へ追加した |
| green | path、CLI、input/UI boundary、fake adapter の既存契約を OS 非依存 test として維持する | characterization | unit / integration | 新しい OS 固有分岐を追加していない |
| green | OS 別の未検証範囲と Linux 排他 mouse の実験扱いを記録する | new | docs | CI pass と manual acceptance を分けた |
| green | unit / integration / static / package gate が通る | characterization | package | build と sdist / wheel smoke を含めた |

## 7. 設計メモ

- 現在の実装は `platformdirs`、`pathlib.Path`、pyglet / swbt の遅延 import と Protocol 境界を利用しており、OS 名による分岐を新設しない。
- CI の OS matrix は source-level の import、settings、input、runtime、fake adapter 契約を確認する。実ウィンドウの表示成功や排他 mouse の OS ショートカット挙動は判定しない。
- Linux の排他 mouse は初期設計どおり experimental と記録する。実機・実デスクトップで未確認の状態を supported と書かない。
- Unit 009 の完了は CI matrix と未検証範囲の記録を意味し、macOS / Linux の hardware acceptance を意味しない。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `.github/workflows/ci.yml` | modify | Windows / macOS / Linux matrix、unit / integration gate |
| `tests/unit/test_ci.py` | modify | OS matrix と integration gate の workflow 契約 |
| `spec/complete/unit_009/OS_PORTABILITY.md` | new | 完了記録、CI 結果、未検証範囲 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/unit/test_ci.py -q` | passed | 2 passed。OS matrix、integration gate、既存 gate の workflow 契約を確認 |
| `uv run pytest tests/unit` | passed | 120 passed。Windows local runner |
| `uv run pytest tests/integration` | passed | 11 passed。Windows local runner |
| `uv run pytest -m "not hardware and not bumble"` | passed | 131 passed、1 deselected。通常試験から hardware / bumble を分離 |
| `uv sync --dev` | passed | 68 packages resolved、66 packages checked |
| `uv lock --check` | passed | lockfile は最新 |
| `uv run ruff format --check .` | passed | 75 files already formatted |
| `uv run ruff check .` | passed | All checks passed |
| `uv run ty check --no-progress` | passed | All checks passed |
| `uv build` | passed | `demi_controller-0.1.0.tar.gz` と `demi_controller-0.1.0-py3-none-any.whl` を生成 |
| `uv run python -c "...wheel/sdist smoke..."` | passed | wheel の runtime / dependency metadata と sdist の unit_009 spec を確認 |
| `git diff --check` | passed | whitespace error なし |
| GitHub Actions OS matrix | not run | PR の remote workflow で確認する |

## 10. 先送り事項

- macOS / Linux の実ウィンドウ、排他 mouse、DPI、OpenGL、フォントは manual / display runner で未確認。
- macOS / Linux の Bluetooth adapter と target device は、ユーザー指定により未実行。
- OS 別 standalone package の build と clean environment 起動は Unit 010 へ送る。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を更新した
- [x] 検証結果または未実行理由を実装後に更新した
- [x] OS 別の未検証範囲を記録した
- [x] package / release / public API に触れる場合の gate を記録した
