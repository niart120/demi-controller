# マウス移動再標本化の責務分離 仕様書

## 1. 概要

### 1.1 目的

`InputPublisher` に混在しているマウス移動の再標本化状態と計算処理を専用部品へ移し、入力評価の編成とマウス固有の時系列処理を分離する。現行の角変位、連続性、方向反転、停止、捕捉境界の挙動は変更しない。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user request | マウス側の複雑さを是正し、統一姿勢モデルへ置き換える前提を作る | 対話 |
| tidy-first decision | 構造変更と後続の振る舞い変更を別の作業単位へ分ける | `.agents/skills/tidy-first/SKILL.md` |
| completed work | 疎な Raw Input の連続性、総角変位、方向反転、停止収束を固定した | `spec/complete/unit_024/SMOOTH_MOUSE_GYRO.md` |
| current implementation | `InputPublisher` が X/Y の速度履歴、未出力変位、再標本化計算を直接所有する | `src/demi/input/publisher.py` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| 入力評価 | 一定速度相当のマウス差分を不規則周期で受け取る | 周期分割によらず同じ角速度と総角変位を出力する | 現行出力と一致する |
| 入力評価 | 1 count の疎な同方向入力を受け取る | 移動区間に 0 角速度を挟まず、停止後は 0 へ収束する | 入力した総変位を増減させない |
| 入力評価 | マウス移動が反対方向へ切り替わる | 0 のフレームを挟まず反対符号へ切り替わる | 累積出力が実入力を越えない |
| capture coordinator | 捕捉解除、epoch 変更、再設定を行う | 未出力変位と速度履歴を破棄する | 再開後に旧入力を送らない |
| 保守者 | `InputPublisher` を読む | ボタン・スティック・IMU の編成とマウス再標本化の詳細を別々に追える | 重複実装を残さない |

## 2. 対象範囲

- 現行のスカラー軸ごとの再標本化状態を専用部品へ移す。
- X/Y 軸の重複を、同じ規則を持つ軸状態の合成として表現する。
- `InputPublisher` はマウス差分と評価間隔を専用部品へ渡し、再標本化済み差分を受け取る。
- 捕捉解除、epoch 変更、再設定で専用部品を初期化する。
- 新経路への切替後、`InputPublisher` 内の旧状態変数と再標本化補助関数を削除する。
- Unit 024 の unit / integration 回帰を新しい責務境界へ整理する。

## 3. 対象外

- 2-tap 再標本化、未出力変位、方向反転判定の数式変更。
- Raw Input packet の到着時刻を使う速度推定と失効時刻の追加。
- マウス停止判定猶予、平滑化強度、評価周期の新しい設定。
- マウス感度、Y 反転、pitch 制限の変更。
- マウスとキーボードの回転意図または姿勢モデルの統一。
- GUI、設定ファイル、swbt-python 送信周期の変更。

## 4. 関連 docs

- `spec/initial/input.md`
- `spec/initial/testing.md`
- `spec/complete/unit_024/SMOOTH_MOUSE_GYRO.md`
- `spec/complete/unit_028/KEYBOARD_GYRO_ACCELERATION.md`
- `spec/wip/unit_030/UNIFIED_ROTATION_POSE_MODEL.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| 一定速度を再標本化する | 同じ速度に相当する差分を 4、8、16、12、5 ms で順に入力 | 初期過渡後の出力速度が一致する | 現行の初回 0.5 倍を含めて固定する |
| 疎な入力を保存する | 8 ms ごとに `1, 0, 1, 0, 1, 0, 0` count | 移動区間は同符号の非 0、最終評価は 0、積分値は 3 count | 変位保存を優先する |
| 不規則周期で変位を保存する | `1@4ms, 0@16ms, 1@12ms, 0@5ms, 0@8ms` | 積分値は 2 count、最終評価は 0 | 周期揺れで増幅しない |
| 方向反転を即時反映する | `+1` の次に `-1` count | 反転評価で逆符号を出力する | 2-tap 平均による 0 を出さない |
| 過走を防ぐ | `+1@4ms, -1@16ms, 0@8ms` | 累積出力は最大 `+1` count 以下、最後は 0 count | 未出力変位を上限にする |
| 状態を破棄する | 捕捉解除、epoch 変更、再設定 | 再開後の無入力評価は 0 | X/Y の履歴を同時に初期化する |
| Publisher 出力を維持する | 同じ入力列を新旧責務境界で評価 | `ControllerFrame` のジャイロ、加速度、ボタン、スティックが一致する | sequence と時刻は同じ偽時計で比較する |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| green | 現行 `InputPublisher` が一定速度、不規則周期、疎な入力で生成する角速度列と総角変位を固定する | characterization | unit | 構造変更前に Publisher と Windows Raw Input integration の 27 件を確認 |
| refactor-skipped | 専用再標本化部品が一定速度と不規則周期で現行と同じ差分列を返す | regression | unit | red は module 不在。軸状態の共通化を含む最小実装で初回過渡と不規則周期が green となり、追加整理は不要 |
| refactor-skipped | 専用再標本化部品が疎な同方向入力を非 0 の連続列へ変換し、総変位を保存して停止する | regression | unit | 固定8 msと不規則周期で非0列、停止0、総変位3 / 2 countを確認。追加の製品コード変更と構造整理は不要 |
| refactor-skipped | 専用再標本化部品が方向反転を同じ評価で出力し、累積変位を実入力の範囲内に保つ | regression | unit | 反転評価の逆符号、最大+1 count以下、最終0 countを確認。追加の製品コード変更と構造整理は不要 |
| refactor-skipped | 専用再標本化部品を初期化すると未出力変位と速度履歴が残らない | edge | unit | X/Y に未出力変位を作った後の reset と無入力0を確認。追加の製品コード変更と構造整理は不要 |
| refactor-done | `InputPublisher` を新しい再標本化部品へ切り替えても入力から `ControllerFrame` と swbt state までの時系列が変わらない | regression | integration | Publisher 切替と旧状態・旧補助関数の削除後に unit 28件、Windows Raw Input integration 5件が green |

## 7. 設計メモ

### 7.1 Tidy First 判定

- classification: structure
- action: tidy-first
- reason: Unit 024 で確定した出力を変えず、状態と計算の所有者だけを分離するため。
- verification: 構造変更前後で同じ入力時系列、角速度列、総角変位、停止結果を比較する。

### 7.2 責務境界

専用部品は物理マウス差分と `dt_seconds` を受け取り、再標本化済み差分を返す。感度、角度単位、姿勢、加速度、ボタン、スティックを扱わない。軸単位の状態は直前速度と未出力変位だけを持ち、2軸の部品が X/Y の軸状態を合成する。

### 7.3 置き換え後の削除

新しい部品へ切り替えた同じ作業単位内で、`InputPublisher` の `_previous_mouse_x_per_second`、`_previous_mouse_y_per_second`、`_unemitted_mouse_x_units`、`_unemitted_mouse_y_units`、`_resample_mouse_motion()`、`_can_emit_reversed_motion()`、`_limit_to_unemitted_motion()`、`_reset_mouse_resampling()` を削除する。互換ラッパー、二重計算、切替フラグは残さない。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/input/mouse_motion_resampler.py` | new | 軸状態と2軸再標本化の専用部品 |
| `src/demi/input/publisher.py` | modify | 専用部品の生成、評価、初期化と旧処理の削除 |
| `tests/unit/input/test_mouse_motion_resampler.py` | new | 一定速度、疎な入力、変位保存、反転、初期化 |
| `spec/initial/input.md` | modify | 再標本化の責務境界 |
| `spec/initial/testing.md` | modify | 専用部品と統合境界の試験項目 |
| `spec/complete/unit_029/MOUSE_MOTION_RESAMPLER_EXTRACTION.md` | new | 作業範囲、TDD 状態、削除条件、検証記録 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/unit/test_documentation.py -q -p no:cacheprovider` | passed | spec 作成時、1 passed |
| `rg -n "T[O]DO\|T[B]D\|x[x]x\|前[回]\|今[回]\|一[旦]\|上[述]\|適[宜]\|必要に応じ[て]" spec/initial/input.md spec/initial/testing.md spec/complete/unit_029/MOUSE_MOTION_RESAMPLER_EXTRACTION.md` | passed | `spec/initial/input.md:252` の既存用語1件は評価周期の定義に必要と確認 |
| `uv run pytest tests/unit/input/test_publisher.py tests/integration/ui/test_windows_raw_input_capture.py -q -p no:cacheprovider` | passed | 構造変更前 baseline、27 passed |
| `uv run pytest tests/unit/input/test_mouse_motion_resampler.py -q -p no:cacheprovider` | failed as expected | red: `demi.input.mouse_motion_resampler` が存在せず collection error |
| `uv run pytest tests/unit/input/test_mouse_motion_resampler.py -q -p no:cacheprovider` | passed | 一定速度と不規則周期、1 passed |
| `uv run pytest tests/unit/input/test_mouse_motion_resampler.py::test_sparse_motion_stays_nonzero_and_preserves_total_displacement tests/unit/input/test_mouse_motion_resampler.py::test_sparse_motion_preserves_displacement_across_irregular_intervals -q -p no:cacheprovider` | passed | 疎な入力の固定 / 不規則周期、2 passed |
| `uv run pytest tests/unit/input/test_mouse_motion_resampler.py::test_direction_reversal_is_emitted_without_a_zero_interval tests/unit/input/test_mouse_motion_resampler.py::test_direction_reversal_does_not_overshoot_input_displacement -q -p no:cacheprovider` | passed | 即時反転と過走上限、2 passed |
| `uv run pytest tests/unit/input/test_mouse_motion_resampler.py::test_reset_discards_both_axes_history_and_unemitted_motion -q -p no:cacheprovider` | passed | X/Y の履歴と未出力変位の破棄、1 passed |
| `uv run pytest tests/unit/input/test_mouse_motion_resampler.py tests/unit/input/test_publisher.py -q -p no:cacheprovider` | passed | 専用部品と Publisher 回帰、28 passed |
| `uv run pytest tests/integration/ui/test_windows_raw_input_capture.py -q -p no:cacheprovider` | passed | Raw Input から送信境界、5 passed |
| `rg -n "_previous_mouse_[xy]_per_second|_unemitted_mouse_[xy]_units|_resample_mouse_motion|_can_emit_reversed_motion|_limit_to_unemitted_motion|_reset_mouse_resampling" src/demi/input/publisher.py` | passed | 該当なし |
| `uv sync --dev` | passed | 77 packages resolved、74 packages checked |
| `uv lock --check` | passed | 77 packages resolved |
| `uv run ruff format --check .` | passed | 131 files already formatted |
| `uv run ruff check .` | passed | All checks passed |
| `uv run ty check --no-progress` | passed | All checks passed |
| `uv run pytest tests/unit -q -p no:cacheprovider` | passed | 238 passed |
| `uv run pytest tests/integration -q -p no:cacheprovider` | passed | 77 passed |
| `uv build` | passed | sdist と wheel を生成 |
| `git diff --check` | passed | whitespace error なし。既存変更の CRLF 変換警告のみ |

## 10. 先送り事項

- Raw Input 到着時刻から速度標本と失効時刻を作る方式は、実入力 trace で現行再標本化の問題を確認した場合に別の作業仕様へ切り出す。Unit 029 ではアルゴリズムを変更しない。
- マウスとキーボードを統一姿勢モデルへ接続する変更は `spec/wip/unit_030/UNIFIED_ROTATION_POSE_MODEL.md` で扱う。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を更新した
- [x] 検証結果または未実行理由を記録した
- [x] package / release / public API は変更対象外と確認した
- [x] 新経路へ切り替えた後に旧状態と旧補助関数を削除した
- [x] 互換ラッパー、二重計算、切替フラグが残っていないことを確認した
