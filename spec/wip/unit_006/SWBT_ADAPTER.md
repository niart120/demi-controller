# swbt-python アダプター 仕様書

## 1. 概要

### 1.1 目的

Unit 005 の `ControllerAdapter` 境界へ swbt-python v0.3 系を接続する。Project_Demi の `ControllerFrame` を swbt の公開 `InputState` へ変換し、アダプター列挙、保存済み bond の再接続、新規 pairing、色設定、切断、例外分類を worker thread 内で実行する。Bluetooth ドングルや Switch 本体を使わず、swbt の公開値と注入 fake gamepad で契約を固定する。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| roadmap | Unit 006 の成果と完了条件 | `spec/initial/roadmap.md` |
| swbt integration | 公開 API、座標、frame 併合、lifecycle、例外境界 | `spec/initial/swbt-integration.md` |
| architecture | controller 層の依存方向と worker 所有 | `spec/initial/architecture.md` |
| lifecycle | 再接続、pairing、neutral、切断、色再生成 | `spec/initial/lifecycle.md` |
| testing | swbt 公開型を使う契約試験と fake adapter | `spec/initial/testing.md` |
| current public source | swbt-python v0.3.0 の `ProController`、`AdapterInfo`、入力値、例外 | `E:\documents\VSCodeWorkspace\swbt-python\src\swbt` |
| completed runtime | `ControllerAdapter`、command queue、frame apply、RuntimeEvent | `spec/complete/unit_005/CONTROLLER_RUNTIME.md` |

### 1.3 Intent Delta

- 初期仕様は swbt-python 0.2 系を前提としているが、実装時点の公開 API は v0.3.0 である。依存範囲を `>=0.3.0,<0.4.0` とし、`ProController.open()`、`reconnect()`、`connect(allow_pairing=...)`、`apply()`、`close(neutral=...)` を使う。
- 現行 `StartPairing` command には bond 保存先がない。pairing 結果を設定された `<data_dir>/bonds/pro-controller/<slot>.json` へ保存するため、`bond_path: Path` を追加する。
- swbt の import は controller の境界 module に閉じ込め、domain、application、UI が swbt 型を受け取らない。

### 1.4 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| runtime worker | `DiscoverAdapters` | swbt `AdapterInfo` が安全な `AdapterDescriptor` へ変換される | USB 列挙は worker でだけ行う |
| runtime worker | `ConnectSaved`、adapter id、bond path、timeout、colors | `ProController` を生成し、`open()` 後に pairing なしの `reconnect()` を実行する | `allow_pairing=True` を使わない |
| runtime worker | `StartPairing`、adapter id、bond path、timeout、colors | `open()` 後に `connect(timeout, allow_pairing=True)` を実行し、bond path を constructor へ渡す | ユーザーの明示操作が前提 |
| runtime worker | accepted `ControllerFrame` | buttons、sticks、3 IMU frames を 1 個の `InputState` として `apply()` へ渡す | raw 換算定数を Project_Demi に持たない |
| runtime worker | neutral frame | 3 slots の gyro 0、accel `(0, 0, +1) G` を apply する | `InputState.neutral()` の 0G を通常 rest に使わない |
| runtime worker | disconnect / recreate colors / close | neutral、controller close、参照破棄を順序どおり行う | controller object を main thread へ返さない |
| runtime worker | swbt exception | `ControllerErrorCategory` を持つ安全な runtime error へ分類される | swbt exception class を UI 契約に漏らさない |

## 2. 対象範囲

- `swbt-python>=0.3.0,<0.4.0` を runtime dependency として固定する。
- `SwbtControllerAdapter` を実装し、Unit 005 の `ControllerAdapter` Protocol を満たす。
- swbt 公開 `Button`、`Stick`、`IMUFrame`、`InputState`、`ControllerColors`、`AdapterInfo`、`ProController` だけを使う。
- 全 `LogicalButton` と swbt `Button` の対応、normalized stick、rad/s gyro、G accel、3-slot IMU を変換する。
- 保存済み reconnect と明示 pairing の constructor / lifecycle を実装する。
- adapter descriptor、color、bond path、例外 category の境界をテストする。
- fake gamepad と fake adapter lister を注入し、実 Bluetooth なしで lifecycle と apply payload を確認する。

## 3. 対象外

- Bluetooth ドングル、Bumble、Switch 本体を使う `bumble` / `hardware` 試験。
- swbt-python 内部 module、HID report、raw IMU calibration、USB handle の直接利用。
- 設定 modal、接続 dialog、adapter 選択 UI、diagnostics の表示。
- Unit 007 の設定保存 UI、Unit 008 の実機 acceptance、Unit 010 の standalone packaging。
- Joy-Con profile。0.1.0 は Pro Controller だけを対象とする。

## 4. 関連 docs

- `spec/initial/roadmap.md`
- `spec/initial/swbt-integration.md`
- `spec/initial/architecture.md`
- `spec/initial/lifecycle.md`
- `spec/initial/testing.md`
- `spec/complete/unit_005/CONTROLLER_RUNTIME.md`
- `AGENTS.md`
- `SKILLS.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| adapter を列挙する | `list_adapters()` が `AdapterInfo` を返す | id、表示名、transport、非秘密 metadata を `AdapterDescriptor` へ写像する | empty tuple は empty tuple のまま返す |
| 保存済み bond へ接続する | `ConnectSaved` | `ProController(adapter=..., key_store_path=str(path), controller_colors=...)`、`open()`、`reconnect(timeout=...)` の順で呼ぶ | pairing fallback を禁止 |
| 新規 pairing する | `StartPairing` | 同じ constructor に bond path を渡し、`open()`、`connect(timeout=..., allow_pairing=True)` を呼ぶ | 自動起動から呼ばない |
| frame を変換する | valid `ControllerFrame` | `InputState` 1 個へ全ボタン、両 stick、3 IMU をまとめて変換する | `sequence`、epoch、monotonic は swbt payload へ渡さない |
| neutral を変換する | `capture_active=False` または watchdog rest | buttons empty、center sticks、gyro 0、accel +1G の同一 IMU 3件を apply する | swbt `InputState.neutral()` は 0G のため直接使わない |
| 色を変換する | `ControllerColorSettings` | `#RRGGBB` を 24-bit integer として `ControllerColors` へ渡す | settings 層で既に形式検証済み |
| 切断する | connected controller | best-effort neutral、`close(neutral=True)`、current reference 破棄 | Runtime が先に rest apply した場合も冪等 |
| 色を再生成する | current adapter、bond path、new colors | current controller を閉じ、同じ saved bond で new colors の ProController を再生成・再接続する | pairing を再開しない |
| 例外を分類する | discovery、open、reconnect、pairing、apply、close の swbt exception | `ControllerAdapterFailure` 経由で runtime の category へ変換する | UI へ traceback や bond 内容を渡さない |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-done | swbt-python v0.3 系 dependency と公開 import 境界が成立する | new / characterization | package | pyproject、uv.lock、公開 `swbt` 型 import を確認 |
| refactor-done | 全 LogicalButton、normalized stick、rad/s gyro、G accel が public swbt values へ変換される | new / edge | unit | 1 test green。raw 換算を行わず、実物の swbt value validation を使用 |
| refactor-done | neutral が 3 IMU slots の gyro 0 / accel +1G として 1 InputState へ変換される | new / regression | unit | 1 test green。`InputState.neutral()` の 0G を使わないことを固定 |
| todo | AdapterInfo と ControllerColors が安全な Project_Demi value へ変換される | new / edge | unit | bond 内容、秘密値、USB handle を返さない |
| todo | saved reconnect と explicit pairing が open / connect の順序と引数を守る | new / integration | integration | fake gamepad factory で `allow_pairing` と bond path を記録 |
| todo | frame apply、disconnect、recreate、close が controller lifecycle を壊さない | new / regression | integration | current reference の破棄、neutral fallback、冪等 close を確認 |
| todo | swbt exception が ControllerErrorCategory へ分類される | new / edge | unit | discovery、bond、timeout、input、transport、unexpected を確認 |
| refactor-done | StartPairing の bond path 境界が runtime command と fake adapter に反映される | new / regression | integration | 1 test green。Unit 005 contract の Intent Delta を回帰固定 |
| todo | unit 全 gate、integration、build、wheel smoke が通る | characterization | package | `uv lock --check`、`uv build`、hardware は対象外として記録 |

## 7. 設計メモ

- `SwbtControllerAdapter` の constructor は gamepad factory と adapter lister を注入可能にし、通常値は `swbt.ProController` と `swbt.list_adapters` とする。
- `ControllerFrame` の conversion は swbt public constructors (`Stick.normalized`、`IMUFrame.gyro_rate`、`with_accel_g`) へ単位付き値を渡す。Project_Demi に `0.070`、`1/4096` などの calibration constant を追加しない。
- `InputState` の `imu_frames` は同じ converted frame を 3 回渡す。swbt の `apply()` を一度だけ呼ぶ。
- adapter は current controller、adapter id、bond path、colors を worker thread 内だけで保持する。main thread から参照可能な status は RuntimeEvent のみとする。
- `StartPairing` の bond path は settings path resolver が作成した path を受け取り、adapter は path の内容を読まず swbt constructor へ文字列として渡す。
- error category の mapping は swbt class 名を Project_Demi の public event に出さず、`ControllerAdapterFailure` に閉じ込める。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `pyproject.toml` | modify | swbt-python runtime dependency |
| `uv.lock` | modify | dependency lock |
| `src/demi/controller/commands.py` | modify | `StartPairing.bond_path` |
| `src/demi/controller/adapter.py` | modify | pairing bond path、adapter failure boundary |
| `src/demi/controller/runtime.py` | modify | updated pairing call、adapter failure category |
| `src/demi/controller/swbt_adapter.py` | new | swbt public API adapter、conversion、lifecycle |
| `tests/unit/controller/test_swbt_adapter.py` | new | conversion、descriptor、color、error behavior |
| `tests/integration/controller/test_swbt_lifecycle.py` | new | fake gamepad lifecycle と command boundary |
| `spec/complete/unit_006/SWBT_ADAPTER.md` | new / modify | TDD 状態、検証、完了記録 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv sync --dev` | not run | implementation 後に依存を同期する |
| `uv run pytest tests/unit/controller/test_swbt_dependency.py` | passed | 1 passed。swbt-python 0.3 系と必要な公開型を確認 |
| `uv run pytest tests/unit/controller/test_swbt_adapter.py -q` | passed | 1 passed。buttons、sticks、rad/s gyro、G accel、3 IMU slots を確認 |
| `uv run pytest tests/unit/controller/test_swbt_adapter.py -q` | passed | 2 passed。neutral の gyro 0 / accel +1G / 3 IMU slots を追加確認 |
| `uv run ruff format --check src/demi/controller/swbt_adapter.py tests/unit/controller/test_swbt_adapter.py` | passed | 2 files already formatted |
| `uv run ruff check src/demi/controller/swbt_adapter.py tests/unit/controller/test_swbt_adapter.py` | passed | All checks passed |
| `uv run ty check --no-progress` | passed | All checks passed |
| `uv run pytest tests/integration/controller/test_runtime_commands.py -q` | passed | 4 passed。StartPairing の bond path を含む command boundary を確認 |
| `uv lock --check` | not run | swbt dependency 追加後に確認する |
| `uv run ruff format --check .` | not run | implementation 後に実行する |
| `uv run ruff check .` | not run | implementation 後に実行する |
| `uv run ty check --no-progress` | not run | implementation 後に実行する |
| `uv run pytest tests/unit` | not run | implementation 後に実行する |
| `uv run pytest tests/integration` | not run | swbt fake lifecycle test 追加後に実行する |
| `uv build` | not run | package dependency の build gate として実行する |
| `git diff --check` | not run | 実装後に確認する |

## 10. 先送り事項

- swbt-python の hardware / bumble marker 試験は Unit 008 の実機検証へ送る。
- Unit 007 の UI から `StartPairing` を発行する導線と settings path resolver の組み立ては後続で扱う。
- swbt status / snapshot の Project_Demi diagnostics snapshot への変換は Unit 008 以降へ送る。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を作成した
- [ ] 検証結果または未実行理由を実装後に更新した
- [ ] package / release / public API に触れる場合の gate を記録した
