# キーボードジャイロ姿勢加速度 仕様書

## 1. 概要

### 1.1 目的

キーボード由来のジャイロ角速度を仮想姿勢へ反映し、Y 軸回転に対応する静的 1G 加速度を生成する。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user request | キーボード入力でジャイロ操作するとき、加速度も回転に応じて補正する | 対話 |
| completed work | profile 設定済みキーから Y / Z 軸の固定角速度を生成する | `spec/complete/unit_026/CONFIGURABLE_IMU_DIAGNOSTICS.md` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| 利用者 | `GYRO:Y_NEGATIVE` または `GYRO:Y_POSITIVE` のキーを保持する | 経過時間と角速度に対応して加速度の X / Z 成分が変化する | 加速度ノルムは 1G |
| 利用者 | Y 軸キーを解放する | ジャイロ Y は 0 になり、加速度は解放時の姿勢を維持する | 捕捉解除時は水平姿勢へ戻す |
| 利用者 | `GYRO:Z_POSITIVE` または `GYRO:Z_NEGATIVE` のキーを保持する | ジャイロ Z は出力するが、静的加速度は変化しない | Z 軸入力はワールド上方向まわりの yaw |

## 2. 対象範囲

- profile 設定済み Y 軸ジャイロキーの角速度を実経過時間で仮想 pitch へ積分する。
- マウス pitch とキー由来 pitch を合成した姿勢から静的加速度を生成する。
- キー解放後の姿勢維持と捕捉境界での姿勢初期化を既存契約へ揃える。
- 関連する初期仕様と単体試験を更新する。

## 3. 対象外

- Z 軸 yaw による静的加速度の変更。
- 並進加速度、遠心加速度、接線加速度の生成。
- roll 軸入力の追加。
- ジャイロ角速度、キー割り当て、設定画面の変更。
- `ACCEL:ZERO` の上書き契約変更。

## 4. 関連 docs

- `spec/initial/input.md`
- `spec/initial/requirements.md`
- `spec/initial/testing.md`
- `spec/complete/unit_025/IJKL_GYRO_DIAGNOSTIC.md`
- `spec/complete/unit_026/CONFIGURABLE_IMU_DIAGNOSTICS.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| Y 軸キー回転を姿勢へ反映する | Y 軸角速度 `r` を `dt` 秒出力 | キー由来 pitch を `r * dt` ラジアン更新し、合成 pitch の `(-sin(pitch), 0, cos(pitch)) G` を出力 | キー由来 pitch はマウス操作用 pitch 上限の対象外 |
| 評価周期に依存させない | 同じ Y 軸角速度を同じ合計時間だけ保持 | 評価周期の分割によらず同じ姿勢と加速度になる | 実経過時間を積分に使う |
| 解放姿勢を維持する | Y 軸キーを解放して次周期を評価 | ジャイロ Y は 0、加速度は直前の姿勢に対応する 1G | `ACCEL:ZERO` 中は最終フレームだけ 0G |
| yaw では加速度を変えない | Z 軸キーだけを保持 | 静的加速度は保持前と同じ | 既存のワールド上方向 yaw 契約 |
| 捕捉境界で初期化する | 捕捉解除、epoch 変更、再設定 | 次の静的加速度は `(0, 0, +1) G` | 保持キーも消去する |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-skipped | Y 軸ジャイロキーを保持すると、実経過時間で積分した姿勢に対応する静的 1G を出力する | new | unit | red で角速度だけが変わり加速度 X が 0 のままになることを確認。green 後は 0.25 秒の保持と分割周期を確認し、追加の構造変更は不要と判断した |
| refactor-skipped | Y 軸キー解放後は回転を止めて直前の静的加速度を維持し、Z 軸キーだけでは加速度を変えない | edge | unit | 解放後の姿勢維持と yaw の加速度不変を確認し、追加の構造変更は不要と判断した |
| refactor-skipped | 捕捉解除と epoch 変更でキー由来姿勢を水平へ戻す | regression | unit | 両方の捕捉境界でジャイロ 0、加速度 `(0, 0, +1) G` を確認し、追加の構造変更は不要と判断した |

## 7. 設計メモ

マウス由来 pitch はポインター操作向けの設定上限を維持する。キー由来 pitch は固定角速度を連続して送る診断入力であり、同じ上限で停止すると送信角速度と加速度姿勢が不整合になるため、別の姿勢成分として積分する。静的加速度の計算には両者を合成した pitch を使う。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/input/yaw_pitch_model.py` | modify | キー由来 pitch 角速度の積分と合成姿勢 |
| `src/demi/input/publisher.py` | modify | 診断 Y 軸角速度を姿勢モデルへ入力 |
| `tests/unit/input/test_publisher.py` | modify | キー回転と加速度の振る舞い |
| `tests/unit/input/test_yaw_pitch_model.py` | modify | 合成姿勢の単体契約 |
| `spec/initial/input.md` | modify | キー由来姿勢と加速度の設計 |
| `spec/initial/requirements.md` | modify | 受入条件 |
| `spec/initial/testing.md` | modify | 試験項目 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/unit/input/test_publisher.py::test_keyboard_pitch_gyro_updates_pose_consistent_acceleration -q -p no:cacheprovider` | failed as expected | red: 加速度 X が期待値 `0.2474... G` に対して `0.0 G` のまま、1 failed |
| `uv run pytest tests/unit/input/test_yaw_pitch_model.py tests/unit/input/test_publisher.py -q -p no:cacheprovider` | passed | 対象 33 passed |
| `uv sync --dev` | passed | 77 packages resolved、74 packages checked |
| `uv run pytest tests/unit -q -p no:cacheprovider` | passed | 232 passed |
| `uv run pytest tests/integration -q -p no:cacheprovider` | passed | 77 passed |
| `uv run ruff format --check .` | passed | 129 files already formatted |
| `uv run ruff check .` | passed | all checks passed |
| `uv run ty check --no-progress` | passed | all checks passed |
| `uv lock --check` | passed | 77 packages resolved |
| `uv build` | passed | sdist と wheel を生成 |
| `git diff --check` | passed | whitespace error なし。Git の CRLF 変換警告のみ |
| GUI と実機でのキー保持操作 | not run | 自動試験で入力評価から送信境界まで確認。Bluetooth 対象機器を使う主観的な操作感は未検証 |

## 10. 先送り事項

- none

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を更新した
- [x] 検証結果または未実行理由を記録した
- [x] package / release / public API は変更対象外と確認した
