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
| red | 16 ms ごとの 1 count を 8 ms ごとに評価しても、移動区間の swbt ジャイロ値に 0 が入らない | regression | integration | 3 回とも `[-0.065973..., 0.0, ...]` となり、非入力 tick が 0 になることを再現した |
| todo | 連続入力の総角変位が平滑化の有無で変わらず、入力停止後に 0 へ収束する | regression / edge | unit | ドリフトと感度変化を防ぐ |
| todo | 評価間隔が揺れても一定速度入力の角速度と総角変位を保つ | regression | unit | 4 ms から 16 ms の時刻列を使う |
| todo | runtime が評価フレームを置換しても送信ジャイロの連続性を保つ | characterization / regression | integration | `apply()` 待機を制御する fake を使う |
| todo | swbt の 3 IMU slot が移動中の連続した標本として変換される | characterization / regression | unit | 公開 `IMUFrame.to_gyro_rate()` で観測する |
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

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `tests/integration/ui/test_windows_raw_input_capture.py` | modify | Raw Input から swbt 物理値までの連続性再現 |
| `spec/wip/unit_024/SMOOTH_MOUSE_GYRO.md` | new | 原因分析、TDD 状態、検証結果、実機受入記録 |

原因を担う production file は仮説検証で特定した時点で追加する。

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/integration/ui/test_windows_raw_input_capture.py tests/unit/input/test_publisher.py -q -p no:cacheprovider` | passed (9 passed) | 変更前 baseline |
| `uv run pytest tests/integration/ui/test_windows_raw_input_capture.py::test_steady_low_speed_raw_mouse_motion_has_no_zero_gyro_gaps -q -p no:cacheprovider` | expected failed (1 failed, 3/3 runs) | 各実行 0.18 秒から 0.20 秒。角速度が `-0.065973...` と `0.0` を交互に取り、低速連続移動の停止・再開を決定的に再現した |

## 10. 先送り事項

- 実機試験は自動回帰試験と原因修正が完了した後に行い、`spec/hardware-test-log.md` にも結果を反映する。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を更新した
- [x] 検証結果または未実行理由を記録した
- [x] package / release / public API に触れる場合の gate を記録した
