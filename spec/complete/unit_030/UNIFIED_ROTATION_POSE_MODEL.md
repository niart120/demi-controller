# 統一回転意図・姿勢モデル 仕様書

## 1. 概要

### 1.1 目的

マウス変位とキーボード保持を1評価周期分の yaw / pitch 角変位へ正規化し、単一の姿勢モデルで pitch 制限、ジャイロ角速度、静的1G加速度を生成する。新モデルへ切り替えた後は旧 `YawPitchModel` と移行用状態・API・テストを削除し、二重モデルを残さない。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user observation | キーボード由来の姿勢加速度は直感的だが、pitch 制限を厳しくし、同じモデルをマウスへ適用したい | 対話 |
| user request | モデル置き換え後の旧モデル削除を作業工程と完了条件へ含める | 対話 |
| completed work | キー由来 Y 軸角速度を別の pitch 状態へ積分して静的加速度へ反映した | `spec/complete/unit_028/KEYBOARD_GYRO_ACCELERATION.md` |
| prerequisite | 現行マウス再標本化を Publisher から分離し、振る舞いを固定する | `spec/complete/unit_029/MOUSE_MOTION_RESAMPLER_EXTRACTION.md` |
| prerequisite | マウスジャイロのX/Y反転設定とGUI保存経路を確定する | `spec/complete/unit_031/MOUSE_GYRO_SETTINGS_GUI.md` |
| initial design | マウス yaw / pitch、区間中央 pitch 投影、静的1G、pitch 上限 | `spec/initial/input.md` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| 利用者 | マウスを上下左右へ動かす | 再標本化済み変位に対応する回転、姿勢、静的1Gを得る | Unit 024 の連続性と総角変位を維持する |
| 利用者 | Y 軸ジャイロキーを保持する | `rate * dt` の pitch 角変位をマウスと同じ姿勢へ反映する | マウスジャイロ無効時も有効 |
| 利用者 | マウスとキーを同時入力する | 同じ周期の yaw / pitch 角変位を合成してから姿勢を更新する | 入力順序に依存させない |
| 利用者 | 合成 pitch が設定上限へ達する方向に入力する | 姿勢は上限を越えず、実際に適用した角変位とジャイロ Y が一致する | 外向き入力で加速度だけを停止させない |
| 利用者 | pitch を持つ状態で yaw 操作する | 区間中央 pitch に従ってジャイロ X/Z へ投影される | マウスとキーで同じ規則を使う |
| 保守者 | 新モデルへの切替後にコードを調べる | 旧 `YawPitchModel`、移行用 API、二重姿勢状態が存在しない | 互換ラッパーを残さない |

## 2. 前提条件

- `spec/complete/unit_029/MOUSE_MOTION_RESAMPLER_EXTRACTION.md` の完了仕様により、マウス再標本化の現行出力が専用部品と回帰試験で固定されていること。
- `spec/complete/unit_031/MOUSE_GYRO_SETTINGS_GUI.md` の完了仕様により、マウスのX/Y反転設定と保存経路が固定されていること。
- `spec/complete/unit_028/KEYBOARD_GYRO_ACCELERATION.md` の完了仕様と回帰試験から、キー由来加速度の baseline を再現できること。

## 3. 対象範囲

- 1評価周期の回転要求を表す入力装置非依存の `RotationIntent` を導入する。
- 再標本化済みマウス差分を感度、X/Y反転、基準角度で yaw / pitch 角変位へ変換する。
- キーボードの固定 yaw / pitch 角速度を `dt_seconds` 倍して角変位へ変換する。
- 同じ周期のマウスとキーの角変位を軸ごとに加算する。
- 統一姿勢モデルが合成 pitch へ1つの設定上限を適用し、実適用角変位からジャイロと静的1Gを生成する。
- yaw は合成姿勢の区間中央 pitch を使ってジャイロ X/Z へ投影する。
- `ACCEL:ZERO` は姿勢更新後の最終 `ControllerFrame.accel_g` だけを 0G へ置換する。
- 捕捉解除、epoch 変更、再設定で統一姿勢を水平へ戻す。
- 新経路への切替後に旧モデル、旧ファイル、移行用 API、旧テストを削除する。
- `spec/initial` のマウス専用姿勢とキー専用姿勢の記述を統一モデルへ更新する。

## 4. 対象外

- マウス再標本化アルゴリズムの変更。
- Raw Input packet 到着時刻による速度推定と停止判定猶予。
- roll 軸、並進加速度、遠心加速度、接線加速度、センサーノイズの追加。
- pitch 制限値を設定する新しい GUI。
- 保存設定 schema のキー名変更。既存 `input.mouse.pitch_limit_degrees` は統一姿勢モデルへ渡す設定値として維持する。
- swbt-python の物理単位変換、report 周期、IMU slot 構成の変更。
- pitch 上限の既定値を 75 度から特定値へ変更すること。より厳しい既定値は実機比較後に別の小さい作業単位で決める。

## 5. 関連 docs

- `spec/initial/input.md`
- `spec/initial/requirements.md`
- `spec/initial/testing.md`
- `spec/complete/unit_024/SMOOTH_MOUSE_GYRO.md`
- `spec/complete/unit_025/IJKL_GYRO_DIAGNOSTIC.md`
- `spec/complete/unit_026/CONFIGURABLE_IMU_DIAGNOSTICS.md`
- `spec/complete/unit_028/KEYBOARD_GYRO_ACCELERATION.md`
- `spec/complete/unit_029/MOUSE_MOTION_RESAMPLER_EXTRACTION.md`
- `spec/complete/unit_031/MOUSE_GYRO_SETTINGS_GUI.md`

## 6. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| マウスを角変位へ変換する | 再標本化済み `dx`, `dy` とマウス設定 | 感度とX/Y反転を独立して適用した yaw / pitch 角変位を生成する | `gyro_enabled = false` ならマウス由来は 0 |
| キーを角変位へ変換する | Y/Z 軸の固定角速度と正の `dt_seconds` | `rate * dt_seconds` の pitch / yaw 角変位を生成する | 評価周期の分割によらず積分値を保つ |
| 回転意図を合成する | 同じ周期のマウスとキー | yaw / pitch ごとに角変位を加算する | source の評価順に依存しない |
| pitch を制限する | 現在 pitch と合成 pitch 角変位 | 次の pitch を `-limit..+limit` に制限し、実適用 pitch 角変位を求める | マウスとキーに同じ上限を適用する |
| 上限で角速度を整合させる | 上限から外向きの pitch 入力 | ジャイロ Y は 0、静的加速度は上限姿勢の1G | 入力要求値をそのまま送らない |
| 上限から戻す | 上限から内向きの pitch 入力 | 入力方向へ姿勢とジャイロ Y が直ちに変化する | ヒステリシスを追加しない |
| yaw を姿勢へ投影する | pitch を持つ状態で yaw 角変位 | 区間中央 pitch によりジャイロ X/Z へ投影する | マウスと Z 軸キーに同じ規則を適用する |
| 静的加速度を生成する | 更新後 pitch | `(-sin(pitch), 0, cos(pitch)) G` を出力する | ノルム1、yaw非依存 |
| 0G 診断を優先する | `ACCEL:ZERO` を保持 | 姿勢を更新した後、最終フレームだけ `(0, 0, 0) G` | 解放後は更新済み姿勢の1Gへ戻る |
| 境界で姿勢を消去する | 捕捉解除、epoch 変更、再設定 | ジャイロ0、加速度 `(0, 0, +1) G` | 保持入力と再標本化状態も各所有者で消去する |
| 非正の時間を扱う | `dt_seconds <= 0` | 姿勢を更新せず、回転由来ジャイロを0にする | 現在姿勢の静的1Gは維持する |

## 7. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-skipped | マウスだけの yaw / pitch 入力が現行と同じ角変位、ジャイロ、静的1Gを生成する | characterization | unit | redは新しいマウス変換部品が未実装で収集失敗。greenは角変位、区間中央pitch投影、静的1Gの1件。部品の責務が分離済みのため追加整理なし |
| refactor-skipped | キーだけの Y 軸入力が `rate * dt` の pitch 角変位を生成し、周期分割によらず同じ姿勢になる | regression | unit | redは回転意図生成関数が未実装で収集失敗。greenは0.2秒と0.1秒2回の同値を確認。旧関数はPublisher切替時に削除するため追加整理なし |
| refactor-skipped | マウスとキーの同時入力が yaw / pitch ごとの角変位を加算してから姿勢を更新する | new | unit | redは `RotationIntent` の加算未対応で1 failed。greenは入力順序を入れ替えた同値を含む3件。軸ごとの不変値加算で完結するため追加整理なし |
| refactor-skipped | 合成 pitch が設定上限へ達すると姿勢と実効ジャイロ Y が同時に停止し、内向き入力で直ちに戻る | new | unit | 試験追加直後からgreen。上限到達時の実効ジャイロ、外向き停止、内向き復帰を4件で確認。単一clamp経路のため追加整理なし |
| refactor-skipped | pitch を持つ状態のマウス yaw と Z 軸キー yaw が同じ X/Z 投影を生成する | new | unit | 試験追加直後からgreen。30度pitchで同じyaw角変位を与え、マウスとJキーのX/Z投影一致を5件で確認。単一投影経路のため追加整理なし |
| refactor-done | `ACCEL:ZERO` 保持中も統一姿勢を更新し、解放後に更新済み姿勢の静的1Gへ戻る | regression | unit | redは旧Publisherが上限外でも要求ジャイロ1.0を送信。greenは10度上限の実効0.4363と解放後1Gを確認。未使用の旧診断ジャイロ合成関数を削除後も37件green |
| refactor-skipped | 非正の `dt_seconds`、捕捉解除、epoch 変更、再設定で姿勢と残留入力を安全に処理する | edge | unit | 新モデルの非正時間とreset、既存Publisherの捕捉解除・epoch・再設定を9件で確認。各所有者の既存reset経路で完結するため追加整理なし |
| refactor-skipped | 疎な Raw Input とキー同時入力を `InputPublisher` から偽 gamepad まで通し、総回転量、pitch 制限、3 IMU slot を保持する | regression | integration | 試験追加直後からgreen。偽gamepad変換後に3 countの総yaw、10度pitch上限、3 slot同値を確認。既存fixtureを再利用し追加整理なし |
| refactor-done | 新モデル切替後の全 unit / integration tree が旧モデルなしで通る | regression | integration | 旧テストの感度、反転、無効化、上限、無入力、resetを新所有者へ移植し、旧source/testと未使用関数を削除。unit 250件、integration 80件がgreen |

## 8. 設計メモ

### 8.1 Tidy First 判定

- classification: behavior
- action: split after Unit 029 and Unit 031
- reason: 回転意図の統一、共通 pitch 制限、キー yaw 投影は観測可能な出力を変える。再標本化の責務移動と混ぜない。
- verification: 角変位、実効角速度、姿勢、静的1Gを入力源ごとと合成時に確認する。

### 8.2 回転意図

`RotationIntent` は `yaw_delta_radians` と `pitch_delta_radians` だけを持つ不変値とする。マウスの native 値は差分なので感度変換後に直接格納する。キーの native 値は角速度なので、正の `dt_seconds` を掛けてから格納する。姿勢モデルはマウス count、キー名、感度、反転、profile を知らない。

### 8.3 姿勢とジャイロの整合

統一姿勢モデルは要求された pitch 角変位ではなく、上限適用後の実角変位を `dt_seconds` で割ってジャイロ Y を生成する。これにより、上限で姿勢と加速度が停止しているのに固定ジャイロだけが残る不整合を避ける。yaw は区間中央 pitch を使って右手座標系の X/Z へ投影する。

### 8.4 pitch 制限値

モデル置き換え時は保存済み値と既定値 75 度を維持し、その値をマウスとキーの合成 pitch へ適用する。45 度は実機比較の候補であり、確認済みの既定値として扱わない。既定値変更では 30、45、60、75 度の操作感と対象側姿勢推定を比較し、別の変更として記録する。

### 8.5 置き換え後の削除

新モデルを `InputPublisher` へ接続し、対象回帰が green になった後、同じ作業単位内で次を削除する。

- `src/demi/input/yaw_pitch_model.py`
- `YawPitchModel` とその `update(dx, dy, additional_pitch_rate_radians_per_second)` API
- `_mouse_pitch_radians` と `_additional_pitch_radians` の二重姿勢状態
- `additional_pitch_rate_radians_per_second` という移行用引数
- 旧モデルを直接対象にした `tests/unit/input/test_yaw_pitch_model.py`
- 旧モデルへの import、互換ラッパー、切替フラグ、fallback

基準角度定数とマウス感度変換の試験は、マウス回転意図を生成する新しい所有者へ移す。Unit 028 の完了仕様は履歴として残し、初期仕様を統一モデルの現在契約へ更新する。

## 9. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/input/rotation_intent.py` | new | 1周期分の yaw / pitch 角変位 |
| `src/demi/input/rotation_pose_model.py` | new | 共通 pitch 制限、実効ジャイロ、静的1G、reset |
| `src/demi/input/mouse_rotation_mapper.py` | new | 再標本化済み差分とマウス設定から回転意図への変換 |
| `src/demi/input/mapper.py` | modify | profile の診断キーから yaw / pitch 角速度要求を生成 |
| `src/demi/input/publisher.py` | modify | 回転意図の合成、新モデル接続、旧モデル import の削除 |
| `src/demi/input/yaw_pitch_model.py` | delete | マウス依存モデルと移行用二重姿勢の撤去 |
| `tests/unit/input/test_rotation_pose_model.py` | new | 合成、上限、投影、静的1G、reset |
| `tests/unit/input/test_mouse_rotation_mapper.py` | new | 感度、X/Y反転、無効化、基準角度 |
| `tests/unit/input/test_mapper.py` | modify | キー由来 yaw / pitch 角速度要求 |
| `tests/unit/input/test_publisher.py` | modify | 入力源の合成、0G、捕捉境界、旧経路なしの回帰 |
| `tests/unit/input/test_yaw_pitch_model.py` | delete | 振る舞いを新しい所有者のテストへ移植後に撤去 |
| `tests/unit/application/test_app.py` | modify | 基準yaw角定数の新所有者を参照 |
| `tests/integration/ui/test_windows_raw_input_capture.py` | modify | Raw Input、キー、姿勢、偽 gamepad の統合回帰 |
| `spec/complete/unit_029/MOUSE_MOTION_RESAMPLER_EXTRACTION.md` | modify | 完了した後続仕様へのリンク |
| `spec/complete/unit_031/MOUSE_GYRO_SETTINGS_GUI.md` | modify | 完了した関連仕様へのリンク |
| `spec/initial/README.md` | modify | 統一回転姿勢モデルを現在判断として記録 |
| `spec/initial/appendix/aim-model.md` | modify | モデル選定理由を統一姿勢へ更新 |
| `spec/initial/architecture.md` | modify | 新しい入力部品と合成フロー |
| `spec/initial/configuration.md` | modify | 設定値を消費する責務境界 |
| `spec/initial/input.md` | modify | 入力源非依存の回転意図と姿勢モデル |
| `spec/initial/lifecycle.md` | modify | 統一姿勢のreset境界 |
| `spec/initial/naming.md` | modify | 回転意図、マウス変換、姿勢モデルの名称 |
| `spec/initial/requirements.md` | modify | 共通 pitch 制限と実効角速度 |
| `spec/initial/roadmap.md` | modify | 入力モデル成果の現在名称 |
| `spec/initial/swbt-integration.md` | modify | 姿勢モデルとデバイス軸補正の境界 |
| `spec/initial/testing.md` | modify | 合成、上限、投影、削除後の回帰 |
| `spec/complete/unit_030/UNIFIED_ROTATION_POSE_MODEL.md` | new | 作業範囲、TDD 状態、旧モデル削除条件、検証記録 |

## 10. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/unit/test_documentation.py -q -p no:cacheprovider` | passed | spec 作成時、1 passed |
| `rg -n "T[O]DO\|T[B]D\|x[x]x\|前[回]\|今[回]\|一[旦]\|上[述]\|適[宜]\|必要に応じ[て]" spec/complete/unit_029/MOUSE_MOTION_RESAMPLER_EXTRACTION.md spec/wip/unit_030/UNIFIED_ROTATION_POSE_MODEL.md spec/complete/unit_031/MOUSE_GYRO_SETTINGS_GUI.md` | passed | Unit 031完了後、該当なし |
| `uv run pytest tests/unit/test_documentation.py tests/unit/test_work_unit_records.py -q -p no:cacheprovider` | passed | 完了移動後の文書構造、3 passed |
| `rg -n "T[O]DO\|T[B]D\|x[x]x\|前[回]\|今[回]\|一[旦]\|上[述]\|適[宜]\|必要に応じ[て]" spec/initial spec/complete/unit_029/MOUSE_MOTION_RESAMPLER_EXTRACTION.md spec/complete/unit_030/UNIFIED_ROTATION_POSE_MODEL.md spec/complete/unit_031/MOUSE_GYRO_SETTINGS_GUI.md` | passed | 該当なし |
| `rg -n "YawPitchModel\|yaw_pitch_model\|キー由来pitch\|角速度を軸ごとに加算" spec/initial` | passed | 現在契約に旧モデル記述なし |
| `uv run pytest tests/unit/input/test_rotation_pose_model.py -q -p no:cacheprovider` | failed as expected | red: `demi.input.mouse_rotation_mapper` が未実装で収集失敗 |
| `uv run pytest tests/unit/input/test_rotation_pose_model.py -q -p no:cacheprovider` | passed | マウス角変位、区間中央pitch投影、静的1G、1 passed |
| `uv run pytest tests/unit/input/test_rotation_pose_model.py -q -p no:cacheprovider` | failed as expected | red: `synthesize_diagnostic_rotation_intent` が未実装で収集失敗 |
| `uv run pytest tests/unit/input/test_rotation_pose_model.py tests/unit/input/test_mapper.py -q -p no:cacheprovider` | passed | キー角変位の時間積分と周期分割、既存mapper回帰、9 passed |
| `uv run pytest tests/unit/input/test_rotation_pose_model.py -q -p no:cacheprovider` | failed as expected | red: `RotationIntent` が加算を実装しておらず1 failed、2 passed |
| `uv run pytest tests/unit/input/test_rotation_pose_model.py -q -p no:cacheprovider` | passed | マウスとキーの軸別加算、入力順序の同値、3 passed |
| `uv run pytest tests/unit/input/test_rotation_pose_model.py -q -p no:cacheprovider` | passed | pitch上限到達、外向き停止、内向き復帰。試験追加直後から4 passed |
| `uv run pytest tests/unit/input/test_rotation_pose_model.py -q -p no:cacheprovider` | passed | 30度pitchでマウスとJキーのyaw X/Z投影一致。試験追加直後から5 passed |
| `uv run pytest tests/unit/input/test_publisher.py::test_accel_zero_keeps_updating_the_shared_pitch_limited_pose -q -p no:cacheprovider` | failed as expected | red: 10度上限でも旧Publisherの要求ジャイロYが1.0のまま、1 failed |
| `uv run pytest tests/unit/input/test_publisher.py::test_accel_zero_keeps_updating_the_shared_pitch_limited_pose -q -p no:cacheprovider` | passed | 0G中の共通上限、実効ジャイロY、解放後の制限済み1G、1 passed |
| `uv run pytest tests/unit/input/test_rotation_pose_model.py tests/unit/input/test_mapper.py tests/unit/input/test_publisher.py -q -p no:cacheprovider` | passed | Publisher切替とyaw投影期待値更新、37 passed |
| `uv run pytest tests/unit/input/test_rotation_pose_model.py tests/unit/input/test_mapper.py tests/unit/input/test_publisher.py -q -p no:cacheprovider` | passed | 未使用の旧診断ジャイロ合成関数を削除したrefactor後、37 passed |
| `uv run pytest tests/unit/input/test_rotation_pose_model.py tests/unit/input/test_publisher.py::test_keyboard_pitch_pose_resets_at_capture_boundaries tests/unit/input/test_publisher.py::test_capture_boundary_discards_unemitted_resampled_mouse_motion tests/unit/input/test_publisher.py::test_publisher_reconfigures_input_settings_and_resets_held_state -q -p no:cacheprovider` | passed | 非正時間、reset、捕捉解除、epoch変更、再設定、9 passed |
| `uv run pytest tests/integration/ui/test_windows_raw_input_capture.py::test_sparse_raw_mouse_and_keyboard_rotation_reach_limited_three_slot_imu -q -p no:cacheprovider` | passed | 疎なRaw Input、Kキー、総yaw、10度pitch上限、3 IMU slot、1 passed |
| `uv run pytest tests/unit/input/test_rotation_pose_model.py tests/unit/input/test_mouse_rotation_mapper.py tests/unit/input/test_mapper.py tests/unit/input/test_publisher.py -q -p no:cacheprovider` | passed | 回転意図、姿勢、入力変換、Publisher、48 passed |
| `uv run pytest tests/integration/ui/test_windows_raw_input_capture.py -q -p no:cacheprovider` | passed | Raw Inputから偽gamepad、6 passed |
| `rg -n "YawPitchModel|additional_pitch_rate_radians_per_second|_mouse_pitch_radians|_additional_pitch_radians|yaw_pitch_model" src tests` | passed | 該当なし |
| `Test-Path src/demi/input/yaw_pitch_model.py` | passed | `False` |
| `Test-Path tests/unit/input/test_yaw_pitch_model.py` | passed | `False` |
| `uv sync --dev` | passed | 77 packages resolved、74 packages checked |
| `uv lock --check` | passed | 77 packages resolved |
| `uv run ruff format --check .` | passed | 134 files already formatted |
| `uv run ruff check .` | passed | All checks passed |
| `uv run ty check --no-progress` | passed | All checks passed |
| `uv run pytest tests/unit -q -p no:cacheprovider` | passed | 250 passed |
| `uv run pytest tests/integration -q -p no:cacheprovider` | passed | 80 passed |
| `uv build` | passed | sdistとwheelを生成 |
| `git diff --check` | passed | whitespace errorなし。作業treeの改行変換警告のみ |

## 11. 先送り事項

- pitch 上限の既定値変更は実機比較後に別の作業単位で扱う。候補値は 30、45、60、75 度とし、比較前に 45 度を確定値として扱わない。
- Raw Input 到着時刻、速度標本、失効時刻を使う別のマウス平滑化方式は Unit 029/030 に含めない。現行再標本化の実入力 trace で問題を確認した場合だけ仕様化する。
- 保存設定の `input.mouse.pitch_limit_degrees` を入力源非依存の名前へ移す schema 変更は、利用者向け移行価値が実装コストを上回ると確認できた場合に別単位で扱う。

## 12. チェックリスト

- [x] 対象範囲、前提条件、対象外を確認した
- [x] TDD Test List を更新した
- [x] Unit 029とUnit 031の完了後に実装へ着手した
- [x] 検証結果または未実行理由を記録した
- [x] package / release / public API は変更対象外と確認した
- [x] 新モデルへ切り替えた後に旧モデル、旧 API、旧テストを削除した
- [x] 旧モデルの import、互換ラッパー、fallback、切替フラグが残っていないことを確認した
- [x] 初期仕様を統一モデルの現在契約へ更新した
