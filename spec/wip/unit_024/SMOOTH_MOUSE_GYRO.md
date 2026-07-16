# マウスジャイロ連続性 仕様書

## 1. 概要

### 1.1 目的

マウスを動かし続けている間にジャイロ角速度が 0 と非 0 を往復し、ゲーム内のカメラ移動がカクつく現象を再現可能な時系列として固定する。Raw Input、入力評価、runtime、swbt-python 変換の各境界を計測し、原因を切り分けたうえで、移動量を失わず連続したジャイロ入力へ修正する。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user report | マウスによるジャイロ入力でゲーム内カメラ移動がカクつき、滑らかに移動しない | 作業依頼 |
| input design | 8 ms 評価、実経過時間、マウス差分から角速度への変換 | `spec/initial/input.md` |
| swbt integration | 最新フレーム併合、3 IMU slot、`InputState` 一括反映 | `spec/initial/swbt-integration.md` |
| completed input pipeline | 現行の `PhysicalInputState`、`YawPitchModel`、`InputPublisher` 契約 | `spec/complete/unit_003/INPUT_PIPELINE.md` |
| completed raw input | Windows Raw Input と Qt 評価境界の実装・実機受入記録 | `spec/complete/unit_015/QT_INPUT_AND_CONTROLLER_PREVIEW.md` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| 利用者 | マウスを一定方向へ低速で連続移動する | 入力中のゲーム内カメラが同じ方向へ停止を挟まず移動する | 入力停止後にジャイロが残留しない |
| 入力パイプライン | 整数単位の Raw Input が 8 ms 評価より低い頻度で届く | 連続操作区間の送信角速度に周期的な 0 が入らない | 操作全体の角変位を増減させない |
| controller runtime | 入力評価と Bluetooth report の周期が一致しない | 最新値の併合後もジャイロの時間積分と向きが保たれる | queue を無制限に増やさない |
| 保守者 | 決定的な入力時系列を試験する | 数秒以内にカクつきの有無を pass / fail 判定できる | Bluetooth 実機なしで自動実行できる |

## 2. 対象範囲

- Windows Raw Input から `InputPublisher`、`ControllerRuntime`、swbt-python `InputState` までの時系列を計測する。
- 低速の一定方向入力、入力評価周期の揺れ、runtime のフレーム置換、3 IMU slot の値を個別に検証する。
- 原因となる境界へ回帰試験を追加し、移動中の 0 角速度区間を解消する。
- 入力停止時の収束、総角変位、向き、capture epoch の安全性を維持する。
- 自動試験後、実機でゲーム内カメラの連続移動を確認する。

## 3. 対象外

- マウスボタン、キーボード、スティックの mapping 変更。
- ジャイロ感度や pitch 上限を編集する新しい UI。
- swbt-python の非公開 HID report 構造への依存。
- カメラ側のモーションブラーやフレームレート変更。

## 4. 関連 docs

- `spec/initial/input.md`
- `spec/initial/testing.md`
- `spec/initial/swbt-integration.md`
- `spec/initial/architecture.md`
- `spec/complete/unit_003/INPUT_PIPELINE.md`
- `spec/complete/unit_006/SWBT_ADAPTER.md`
- `spec/complete/unit_015/QT_INPUT_AND_CONTROLLER_PREVIEW.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| 低速の連続移動を送る | 1 count の Raw Input が 16 ms ごと、入力評価が 8 ms ごと | 最初と最後の入力間に 0 のジャイロ slot がない | 整数入力の量子化を含む決定的な再現列 |
| 角変位を保存する | 既知の mouse count 列と評価時刻列 | 出力角速度の時間積分が設定から求めた角変位と一致する | 平滑化による過大・過小移動を禁止 |
| 入力停止へ収束する | 最後の Raw Input 後に評価を継続 | 有限時間内に角速度 0 となり、残留移動しない | capture 解除時は即座に neutral |
| 評価周期の揺れを扱う | 同じ一定速度、8 ms を中心に異なる評価間隔 | 角速度の符号と時間積分を保ち、周期の長短だけで停止しない | 実経過時間を使用する |
| runtime で併合する | 入力評価が `apply()` より速い | Bluetooth 側で観測する時系列に周期的な 0 を作らない | 最新値 slot の上限 1 は維持する |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-done | 16 ms ごとの 1 count を 8 ms ごとに評価しても、移動区間の swbt ジャイロ値に 0 が入らない | regression | integration | 全 9 frame の swbt 物理値が同符号かつ同値であることを固定した |
| refactor-done | 保存済み入力評価周期と swbt-python の report 周期が一致する | characterization / regression | integration | 16 ms の保存値が swbt 公開 constructor の 16000 µs へ渡ることを固定した |
| green | frame 変換と swbt-python state 差し替えが 8 ms 周期内に完了する | characterization | integration | 各 10,000 回の p99 は 9.5 µs と 0.9 µs |
| green | swbt の 3 IMU slot が移動中の連続した標本として変換される | characterization / regression | unit | 現行の断続列は 3 slot 単位の非 0 block と 0 block になる |
| refactor-skipped | 連続入力の総角変位が平滑化の有無で変わらず、入力停止後に 0 へ収束する | regression / edge | unit | 3 count の積分を保ち、1 評価の tail 後に 0 へ収束する。追加の production 整理は不要 |
| green | 評価間隔が揺れても一定速度入力の角速度と総角変位を保つ | regression | unit | 4、8、16、12、5 ms で角速度が一致した |
| todo | runtime が評価フレームを置換しても送信ジャイロの連続性を保つ | characterization / regression | integration | `apply()` 待機を制御する fake を使う |
| todo | 実機で低速・中速・高速のカメラ移動が滑らかで、停止後に流れない | regression | hardware | 環境値と時刻、入力条件、観測結果を記録する |

status は `todo`、`red`、`green`、`refactor-done`、`refactor-skipped`、`deferred` を使う。

## 7. 設計メモ

- 再現判定は画面描画ではなく、一定方向へ移動している区間の swbt 公開物理値に 0 の標本が含まれるかで行う。
- 2026-07-16 時点の lock は swbt-python 0.3.0 である。

### 7.1 確認済みの近接要因

runtime を通さない Raw Input、`InputPublisher`、swbt 公開物理値の経路で、16 ms ごとの 1 count が `-0.065973...`、`0.0` の交互列へ変換された。整数 mouse count のない評価 tick を即座に角速度 0 とする現行処理は、低速連続移動をパルス列にする。

### 7.2 原因仮説

以下は未検証の順位である。利用者の指摘を反映し、Project_Demi と swbt-python の入力・送信周期不一致を最初に検証する。

1. Project_Demi の 125 Hz 入力評価と swbt-python の HID report 周期が一致せず、短い非 0 / 0 の状態を不均一に標本化している。report 周期を計測し、同じ入力列をその周期で標本化すると欠落位置を再現できるはずである。
2. 整数 mouse count の量子化と評価 tick ごとの即時 0 化が主因である。swbt-python と runtime を除いた現行の再現結果はこの予測と一致する。周期を合わせても低速 count が評価周期より疎なら 0 が残るはずである。
3. runtime の latest-only mailbox と非同期 `apply()` が中間フレームを置換し、仮説 2 のパルス列を増幅している。`apply()` を意図的に遅らせると非 0 フレームの欠落数が増えるはずである。
4. 同一値を複製した 3 IMU slot と swbt-python 0.3.0 の report 生成が時間軸を粗くしている。1 report 内の 3 slot と連続 report の物理値を観測すれば、重複標本と更新境界を特定できるはずである。
5. Qt timer の揺れが角速度の振幅を変調している。mouse count を実経過時間に比例させた入力でも出力角速度が変動する場合に成立する。

### 7.3 入力評価と report 周期の検証

2026-07-16 に次を確認した。

- 保存済み `settings.toml` の `evaluation_interval_ms` は 8 であり、Project_Demi は 125 Hz で入力を評価する。
- Project_Demi は swbt-python の `ProController` 生成時に `report_period_us` を渡さない。
- swbt-python 0.3.0 の Pro Controller profile と `ReportLoop` の既定周期は 8000 µs であり、125 Hz で current state を送る。
- swbt-python の `apply()` は state store を更新するだけで即送信しない。独立した report loop が各周期で snapshot を取得する。

仮説 1 の単純な周波数不一致は、この環境では棄却する。両者は公称周期が同じでも別スレッド・別イベントループで位相同期しないため、`apply()` 遅延と report snapshot の前後関係による置換は仮説 3 と合わせて未検証である。

### 7.4 frame 変換と state 差し替えの計測

同一プロセスで各処理を 10,000 回実行した。

| 境界 | mean | p95 | p99 | max |
|---|---:|---:|---:|---:|
| `frame_to_input_state()` | 8.63 µs | 8.8 µs | 9.5 µs | 47.9 µs |
| swbt-python `ProController.apply()` | 0.841 µs | 0.9 µs | 0.9 µs | 10.7 µs |

`apply()` は通信を行わず state store を差し替える。通常時の変換と差し替えは 8 ms 周期より 2 桁以上短いため、仮説 3 の通常処理による backlog は主因として棄却する。GUI または worker が別要因で停止した場合の latest-only 置換は成立し得るが、runtime を除いた再現経路で同じ断続が発生するため、本現象の必要条件ではない。

### 7.5 3 IMU slot の wire 値

`frame_to_input_state()` と swbt-python 0.3.0 の report builder へ `-0.065973... rad/s`、`0.0 rad/s` の交互列を渡し、各 0x30 report の raw gyro Z を確認した。

```text
(-54, -54, -54)
(  0,   0,   0)
(-54, -54, -54)
(  0,   0,   0)
```

swbt-python は state の 3 slot を順に wire へ書き込み、追加の 0 や補間を生成しない。Project_Demi が同じ標本を 3 slot に複製するため、上流の断続は report 内の全 3 標本が非 0 または 0 となる block 列へ変換される。仮説 4 は断続の発生源としては棄却し、上流のパルス列をそのまま report block へ伝播する増幅境界として確認した。production code は引き続き swbt-python の公開 API だけを使い、この計測で参照した内部 report builder へ依存しない。

### 7.6 入力評価間隔の揺れ

整数 mouse count の量子化を分離するため、500 input units/s の一定速度から各評価区間の移動量を計算し、4、8、16、12、5 ms の順で `InputPublisher` を評価した。5 frame の gyro Z は同じ値となり、試験は 0.03 秒で通過した。

`YawPitchModel` は各区間の移動量を実経過時間で割るため、移動量が経過時間に比例する限り、評価間隔の揺れだけでは角速度を変調しない。仮説 5 は単独原因として棄却する。Raw Input の整数 count が疎になる量子化と timer jitter の組み合わせは入力間隔を変えるが、近接要因は count のない評価 tick を即 0 とする処理である。

### 7.7 平滑化 TDD red

1 count、0 count を交互に 3 回入力し、最後に 0 count を追加して全出力を積分する unit test を作成した。現行値は `[-0.0654498..., -0.0, -0.0654498..., -0.0, -0.0654498..., -0.0, -0.0]` となり、移動区間に 0 を含まないという assertion が期待どおり失敗した。

Tidy 分類は behavior change である。公開 API と設定を増やさず `InputPublisher` の時系列だけを変更できるため、先行する構造整理は行わない。候補は現在 count と直前 count を半分ずつ次の角速度へ反映する 2-tap 処理であり、全出力の時間積分で元の 3 count 分を保ち、最後の入力から 1 評価後に 0 へ収束させる。

### 7.8 平滑化 TDD green

`InputPublisher` は各評価区間の `dx`、`dy` を input units/s へ変換し、現在値と直前値の算術平均を同じ区間の移動量へ戻してから `YawPitchModel` へ渡す。count の単純平均ではなく速度を平均するため、4 ms から 16 ms に評価間隔が変わっても、開始 tick の半量出力後は一定速度を保つ。

固定 8 ms では各入力を現在と次の評価へ半分ずつ分配する。1 count と 0 count の交互列は全移動区間で同符号となり、時間積分は元の 3 count 分と一致し、最後の入力から 1 評価後に 0 となる。reconfigure、capture epoch 変更、capture 解除では履歴を破棄し、古い移動を次の状態へ持ち越さない。

### 7.9 Refactor review

`InputPublisher` が入力評価時系列を所有し、`YawPitchModel` が 1 区間の yaw/pitch 変換を所有する境界は維持できている。private helper の追加だけで公開 API、設定、runtime を変更しておらず、production の追加分割は行わない。

integration test は非 0 の確認だけでは振幅変調を見逃すため、全 9 frame の swbt 角速度が同値である assertion を追加した。同じ再現 command は 0.17 秒で通過した。

### 7.10 入力評価と report 周期の整合

`SwbtControllerAdapter` は `report_period_us` を受け取り、swbt-python の公開 `ProController` constructor へ明示的に渡す。app 組み立ては保存済み `evaluation_interval_ms` を 1000 倍し、入力評価と同じ周期を runtime の adapter factory に固定する。既定 8 ms だけでなく、16 ms の保存設定が 16000 µs として渡ることを app と adapter の境界試験で確認した。

`SwbtControllerAdapter` は package root から export されない controller adapter 境界である。追加引数は `int` と µs 単位の Google style docstring が一致し、`ty`、ruff、関係試験を通過した。production の `Any`、`cast()`、type ignore は追加していない。test の `cast()` は `**kwargs: object` で受けた既存 runtime factory 引数を `ControllerAdapterFactory` へ絞る局所境界に限定する。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/input/publisher.py` | modify | 評価区間の mouse 速度を 2-tap 平滑化し、状態遷移で履歴を破棄する |
| `src/demi/app.py` | modify | 保存済み入力評価周期を adapter factory の report 周期へ渡す |
| `src/demi/controller/swbt_adapter.py` | modify | report 周期を swbt 公開 constructor へ渡す |
| `tests/integration/ui/test_windows_raw_input_capture.py` | modify | Raw Input から swbt 物理値までの連続性再現 |
| `tests/unit/application/test_app.py` | modify | 保存済み 16 ms と swbt 16000 µs の組み立て境界 |
| `tests/unit/controller/test_swbt_adapter.py` | modify | report 周期の公開 gamepad 境界 |
| `tests/unit/input/test_publisher.py` | modify | 評価周期の揺れを分離した一定速度の回帰試験 |
| `spec/wip/unit_024/SMOOTH_MOUSE_GYRO.md` | new | 原因分析、TDD 状態、検証結果、実機受入記録 |

原因を担う production file は仮説検証で特定した時点で追加する。

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/integration/ui/test_windows_raw_input_capture.py tests/unit/input/test_publisher.py -q -p no:cacheprovider` | passed (9 passed) | 変更前 baseline |
| `uv run pytest tests/integration/ui/test_windows_raw_input_capture.py::test_steady_low_speed_raw_mouse_motion_has_no_zero_gyro_gaps -q -p no:cacheprovider` | expected failed (1 failed, 3/3 runs) | 各実行 0.18 秒から 0.20 秒。角速度が `-0.065973...` と `0.0` を交互に取り、低速連続移動の停止・再開を決定的に再現した |
| `Get-Content` / `rg` による保存設定、Project_Demi 構築引数、swbt-python 0.3.0 `ReportLoop` の照合 | passed | 入力評価 8 ms、report 8000 µs、`apply()` は即送信せず state store を差し替えることを確認した |
| `uv run python -` による `frame_to_input_state()` と `ProController.apply()` の各 10,000 回計測 | passed | frame 変換 p99 9.5 µs、state 差し替え p99 0.9 µs。実接続と thread scheduling は含まない |
| `uv run python -` による交互ジャイロ列の 0x30 report 展開 | passed | 3 slot の raw gyro Z は `(-54, -54, -54)` と `(0, 0, 0)` を report ごとに交互送信する |
| `uv run pytest tests/unit/input/test_publisher.py::test_publisher_preserves_constant_gyro_rate_across_irregular_intervals -q -p no:cacheprovider` | passed (1 passed) | 4、8、16、12、5 ms の評価間隔で一定速度から同じ角速度を得た |
| `uv run pytest tests/unit/input/test_publisher.py::test_publisher_smooths_sparse_mouse_counts_without_changing_total_rotation -q -p no:cacheprovider` | expected failed (1 failed) | `[-0.0654498..., -0.0, ...]` となり、総角変位と停止は保つが移動区間の連続性がない |
| `uv run pytest tests/unit/input/test_publisher.py tests/unit/input/test_yaw_pitch_model.py tests/unit/application/test_coordinator.py tests/integration/ui/test_windows_raw_input_capture.py -q -p no:cacheprovider` | passed (25 passed) | 疎な Raw Input、総角変位、周期揺れ、既存 yaw/pitch、capture coordinator を確認した |
| `uv run ruff format --check src/demi/input/publisher.py tests/unit/input/test_publisher.py` / `uv run ruff check src/demi/input/publisher.py tests/unit/input/test_publisher.py` / `uv run ty check --no-progress` / `git diff --check` | passed | format、lint、型、空白を確認した |
| `uv run pytest tests/integration/ui/test_windows_raw_input_capture.py::test_steady_low_speed_raw_mouse_motion_has_no_zero_gyro_gaps -q -p no:cacheprovider` | passed (1 passed) | 全 9 frame の swbt 角速度が同符号かつ同値であることを確認した |
| `uv run pytest tests/unit/application/test_app.py::test_application_runner_aligns_report_period_with_saved_input_interval tests/unit/controller/test_swbt_adapter.py::test_configured_report_period_crosses_the_public_gamepad_boundary tests/integration/controller/test_swbt_lifecycle.py -q -p no:cacheprovider` | passed (4 passed) | 保存済み 16 ms、adapter 16000 µs、既存 swbt lifecycle を確認した |
| `uv run ty check --no-progress` / `uv run ruff check src/demi/app.py src/demi/controller/swbt_adapter.py tests/unit/application/test_app.py tests/unit/controller/test_swbt_adapter.py` / `uv run ruff format --check src/demi/app.py src/demi/controller/swbt_adapter.py tests/unit/application/test_app.py tests/unit/controller/test_swbt_adapter.py` | passed | 型境界、Google style docstring、lint、format を確認した |

## 10. 先送り事項

- 実機試験は自動回帰試験と原因修正が完了した後に行い、`spec/hardware-test-log.md` にも結果を反映する。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を更新した
- [x] 検証結果または未実行理由を記録した
- [x] package / release / public API に触れる場合の gate を記録した
