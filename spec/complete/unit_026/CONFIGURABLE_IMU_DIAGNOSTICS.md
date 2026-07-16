# 設定可能な IMU 診断入力 仕様書

## 1. 概要

### 1.1 目的

固定キーとして実装した Y 軸 / Z 軸の一定角速度を通常のキー割り当て対象へ移し、加速度を一時的に完全な 0G へ上書きする診断入力を追加する。これにより、ゲーム側で観測された pitch 方向の復元挙動について、加速度入力の有無を切り替えて比較できるようにする。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user request | 診断入力をキー割り当てへ追加し、加速度完全ゼロの挙動を試す | 作業依頼 |
| observed behavior | Z 軸方向ではカメラが連続回転し、Y 軸方向では元へ戻るような挙動が見えた | 利用者による実機観測 |
| observed behavior | 接続中に加速度を0Gへ切り替えると、対象側がジャイロ入力を反映しなくなった | 利用者による実機観測 |
| hypothesis | pitch 復元に姿勢対応の静的加速度が関与している | 未検証。0G 診断入力で比較する |
| hypothesis | 対象側が最初から0Gを受け取る場合は、接続中に切り替えた場合と挙動が異なる | 未検証。接続初期0Gで比較する |
| completed diagnostic input | I/J/K/L 固定入力、一定角速度、相殺、通常 mapping 抑止 | `spec/complete/unit_025/IJKL_GYRO_DIAGNOSTIC.md` |
| configuration design | profile binding、設定ダイアログ、保存と復旧 | `spec/initial/configuration.md` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| 利用者 | キー割り当て画面を開く | Y-/Y+/Z+/Z- の一定角速度と 0G 加速度を通常の割り当て行として確認できる | target の追加・削除 UI は設けない |
| 利用者 | 診断 target の割り当てキーを変更して保存する | 次回の入力評価から変更後のキーが診断入力を生成する | F12 予約と競合確認は既存規則を使う |
| 入力評価 | `ACCEL:ZERO` の source を保持する | マウス姿勢にかかわらずフレーム加速度が `(0, 0, 0) G` になる | 内部 pitch は変更しない |
| 入力評価 | 0G source を解放する | 現在の仮想 pitch に対応する静的 1G へ戻る | 原因判定はこの機能の対象外 |
| 利用者 | 未接続中に 0G source を保持してから接続する | 接続先が受け取る最初の IMU 加速度も `(0, 0, 0) G` になる | ジャイロと操作入力はニュートラルで開始 |
| 設定読込 | 旧 Default profile を読み込む | 既存 binding を保持したまま不足する診断 target だけが加わる | 設定ファイルへの書き戻しは次回保存時 |

## 2. 対象範囲

- `BindingTarget` に Y 軸 / Z 軸の一定角速度4方向と加速度 0G の診断 target を追加する。
- Default profile に `I = -Y`、`K = +Y`、`J = +Z`、`L = -Z`、`O = 0G` を追加する。
- 診断 target の source を既存のキー割り当て画面で変更し、設定 codec で保存・復元できるようにする。
- 診断用ジャイロは `1.0 rad/s` の一定値とし、同一軸の反対方向を相殺する。
- 診断 target に割り当てた source はボタン / スティック target より優先し、同じ物理入力を複数用途へ流さない。
- 0G 診断入力中は `YawPitchModel` が生成した加速度だけを最終フレームで `(0, 0, 0) G` へ上書きする。
- 未接続中の最新フレームが捕捉中かつ0Gの場合、接続成功直後の初期フレームも加速度だけを0Gとする。
- 旧 Default profile へ不足する診断 binding を読み込み時に補い、`MIGRATED` として返す。

## 3. 対象外

- pitch 復元挙動の原因確定、ゲーム側の姿勢推定方式の解析。
- マウスの yaw / pitch モデル、pitch 上限、感度、入力再標本化の変更。
- 角速度の大きさ、加速度ベクトル、診断 target 数を変更する UI。
- X 軸ジャイロ、任意加速度、ノイズ、並進加速度の生成。
- Default profile 以外の保存済み profile への自動補完。
- swbt-python の IMU raw 値変換、Bluetooth report 周期、実機受入。
- 切断、捕捉解除、watchdog、終了時の安全ニュートラルを0Gへ変更すること。

## 4. 関連 docs

- `spec/initial/configuration.md`
- `spec/initial/input.md`
- `spec/initial/requirements.md`
- `spec/initial/testing.md`
- `spec/initial/ui.md`
- `spec/initial/naming.md`
- `spec/complete/unit_025/IJKL_GYRO_DIAGNOSTIC.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| 診断 target を公開する | Default profile またはキー割り当て画面 | `GYRO:Y_NEGATIVE`、`GYRO:Y_POSITIVE`、`GYRO:Z_POSITIVE`、`GYRO:Z_NEGATIVE`、`ACCEL:ZERO` の5行が存在 | 既定 source は I/K/J/L/O |
| 設定で source を変更する | 診断行へ別のキーまたはマウスボタンを割り当てて保存 | 再読込後も target と source が維持され、変更後の source が入力を生成 | 診断 binding は反転不可、amount は `1.0` 固定 |
| 旧 Default profile を補完する | 診断 target が一部または全部ない組み込み `default` profile | 不足分だけを既定順で末尾へ加え、既存 binding と source を変更しない | 他 profile は変更しない |
| 一定角速度を生成する | 診断用ジャイロ target の source を保持 | 対応軸へ符号付き `1.0 rad/s` を生成 | マウス由来角速度へ加算 |
| 反対方向を相殺する | 同一軸の正負 source を同時保持 | 対象軸は `0.0 rad/s` | Y / Z は独立 |
| 診断入力を優先する | 同じ source が診断 target と通常 target に重複 | 診断 target だけを評価 | 競合警告は既存 UI で表示 |
| 加速度を 0G にする | `ACCEL:ZERO` の source を保持 | `ControllerFrame.accel_g == AccelG(0.0, 0.0, 0.0)` | ジャイロと同時利用可 |
| 0G を解除する | 0G source を解放 | 次の評価で現在 pitch に対応する静的 1G に戻る | pitch を初期化しない |
| 接続初期から 0G にする | 未接続中の最新フレームが捕捉中かつ0Gで、その状態のまま接続 | 接続直後にニュートラル操作と0G加速度を適用 | 最新フレームのボタン、スティック、ジャイロは初期フレームへ流さない |
| 捕捉外を neutral にする | `capture_active = false` または epoch 変更 | ジャイロ 0、加速度 `(0, 0, +1) G`、保持状態消去 | 0G を残留させない |
| 安全ニュートラルを維持する | 切断、watchdog、終了 | 加速度 `(0, 0, +1) G` を適用 | 接続初期0Gの例外を適用しない |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-skipped | Default profile と設定 codec は5つの診断 target を I/K/J/L/O の既定 source で公開し、診断 binding の不正な反転または amount を拒否する | new | unit | red は未定義 target による collection error。green は16 passed。追加の構造変更は不要 |
| refactor-skipped | 旧 Default profile の読み込みは既存 binding を保持して不足する診断 target だけを補い、`MIGRATED` を返す | regression | unit | red は `LOADED` のまま。green は7 passed。補完処理を repository 内へ閉じたため追加 refactor は不要 |
| refactor-skipped | profile で割り当てた4方向の診断 source は一定角速度を生成し、反対方向を相殺し、同じ source の通常 target を抑止する | new / regression | unit | red は任意 source 4方向で4 failed。green は mapper と publisher の25 passed。評価 helper の責務が分離済み |
| refactor-skipped | 0G 診断 source の保持中だけ最終フレームの加速度が完全な0となり、解放後は内部 pitch に対応する1Gへ戻る | new / edge | unit | red は姿勢対応加速度が残り1 failed。green は26 passed。最終フレーム上書きに限定 |
| refactor-skipped | 接続前の最新フレームが捕捉中の0Gなら接続初期フレームも0Gとし、切断とwatchdogの安全ニュートラルは1Gを維持する | new / safety | integration | red は接続初期が1Gで1 failed。green はruntime 6 passed。接続初期専用helperへ分離 |
| refactor-skipped | キー割り当て画面は5つの診断行を表示し、既存操作で source を変更できる | new | unit / integration | red は診断行で反転欄が有効なため失敗。green は21 passed。既存model/viewを拡張 |
| refactor-skipped | 初期仕様は設定可能な診断 target、旧設定補完、0G の診断目的と非定常性を説明する | docs | docs | 観測事実と未検証仮説を分離。docs reviewで仮テキストと旧固定入力説明の残存なし |

## 7. 設計メモ

固定 I/J/K/L の分岐は廃止し、profile の診断 target を入力評価する。一定角速度と 0G は挙動検証専用であり、`amount` や反転を使う連続設定にはしない。source が通常 target と重複した場合は診断 target を優先することで、unit_025 の二重入力抑止を維持する。

0G は `YawPitchModel` の内部姿勢を変えず、最終 `ControllerFrame` の `accel_g` だけを上書きする。これにより、保持中と解放後で同じ pitch 状態を使い、加速度を入力した場合と除いた場合を比較できる。観測結果から加速度が復元原因だとはまだ断定しない。

通常の接続経路は接続成功直後に静的1Gの安全な rest frame を適用するため、途中切替と接続初期0Gは同じ実験にならない。接続前に runtime が受け取った最新フレームが捕捉中かつ完全な0Gの場合に限り、接続初期 frame の加速度だけを0Gへ置換する。通常操作は初期 frame へ引き継がず、切断、watchdog、終了の rest frame にもこの例外を適用しない。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/domain/mapping.py` | modify | 診断 target、既定 binding、分類 helper |
| `src/demi/config/repository.py` | modify | 旧 Default profile の不足 target 補完 |
| `src/demi/input/mapper.py` | modify | 設定駆動の診断ジャイロ、0G 判定、通常 mapping 抑止 |
| `src/demi/input/publisher.py` | modify | 診断角速度の合成と加速度上書き |
| `src/demi/controller/runtime.py` | modify | 捕捉中0Gを接続初期フレームへ限定的に反映 |
| `tests/unit/` | modify | domain、codec、repository、mapper、publisher、UI の TDD |
| `tests/integration/ui/` | modify | 診断行の表示と割り当て変更 |
| `tests/integration/controller/test_runtime_commands.py` | modify | 接続初期0Gと切断時1Gの安全境界 |
| `spec/initial/*.md` | modify | 設定、入力、要件、試験、UI、命名の整合 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/unit/domain/test_mapping.py tests/unit/config/test_codec.py -q -p no:cacheprovider` | failed as expected | red: `BindingTarget.GYRO_Y_NEGATIVE` が未定義のため collection error |
| `uv run pytest tests/unit/domain/test_mapping.py tests/unit/config/test_codec.py -q -p no:cacheprovider` | passed | green: 16 passed |
| `uv run pytest tests/unit/config/test_repository.py -q -p no:cacheprovider` | failed as expected | red: 旧 Default profile が `LOADED` のままで診断 target を補完しないため1 failed、6 passed |
| `uv run pytest tests/unit/config/test_repository.py -q -p no:cacheprovider` | passed | green: 7 passed |
| `uv run pytest tests/unit/input/test_publisher.py -q -p no:cacheprovider` | failed as expected | red: profile へ割り当てた任意 source 4方向が角速度を生成せず4 failed、14 passed |
| `uv run pytest tests/unit/input/test_publisher.py tests/unit/input/test_mapper.py -q -p no:cacheprovider` | passed | gyro green: 25 passed |
| `uv run pytest tests/unit/input/test_publisher.py -q -p no:cacheprovider` | failed as expected | red: `ACCEL:ZERO` 保持中も姿勢対応加速度が残り1 failed、18 passed |
| `uv run pytest tests/unit/input/test_publisher.py tests/unit/input/test_mapper.py -q -p no:cacheprovider` | passed | 0G green: 26 passed |
| `$env:QT_QPA_PLATFORM='offscreen'; uv run pytest tests/unit/ui/test_mapping_model.py tests/unit/domain/test_settings.py tests/integration/ui/test_mapping_dialog.py -q -p no:cacheprovider` | failed as expected | red: 診断行の反転欄が有効で1件失敗。新規既定キーと既存試験用 `KEY:K` の競合による主題外失敗も確認 |
| `$env:QT_QPA_PLATFORM='offscreen'; uv run pytest tests/unit/ui/test_mapping_model.py tests/unit/domain/test_settings.py tests/integration/ui/test_mapping_dialog.py -q -p no:cacheprovider` | passed | green: 21 passed |
| `uv run pytest tests/integration/controller/test_runtime_commands.py::test_captured_zero_g_is_used_only_for_the_connection_initial_frame -q -p no:cacheprovider` | failed as expected | red: 接続初期フレームが `(0, 0, +1) G` のため1 failed |
| `uv run pytest tests/integration/controller/test_runtime_commands.py -q -p no:cacheprovider` | passed | green: 6 passed |
| `uv sync --dev` | passed | 77 packages resolved、74 packages checked |
| `uv lock --check` | passed | 77 packages resolved |
| `uv run ruff format --check .` | passed | 129 files already formatted |
| `uv run ruff check .` | passed | All checks passed |
| `uv run ty check --no-progress` | passed | All checks passed |
| `uv run pytest tests/unit -q -p no:cacheprovider` | passed | 225 passed |
| `$env:QT_QPA_PLATFORM='offscreen'; $env:PYTHONUTF8='1'; uv run pytest tests/integration -q -p no:cacheprovider --basetemp .pytest-tmp-unit026` | failed (environment) | 73 passed、2 failed。sandboxのPyPI接続制限でisolated build backendを取得できなかった |
| `$env:QT_QPA_PLATFORM='offscreen'; $env:PYTHONUTF8='1'; uv run pytest tests/integration -q -p no:cacheprovider --basetemp .pytest-tmp-unit026-net` | passed | ネットワーク許可と新規basetempで75 passed |
| `uv build` | passed | sdistとwheelを生成 |
| `uv run pytest tests/unit/test_documentation.py tests/unit/test_work_unit_records.py -q -p no:cacheprovider` | passed | 3 passed |
| docs-quality review | passed | 固定IJKL説明、仮テキスト、会話依存語の残存なし。「前回評価」は時間境界の仕様用語 |
| agentic self-review | passed | Intent Delta、対象外、public configuration target、接続初期0G例外、安全ニュートラル、diff、gateを照合 |
| `git diff --check` | passed | whitespace errorなし。作業環境のLFからCRLFへの変換警告のみ |
| 実機での pitch 復元比較 | not run | 利用者による後続検証 |

## 10. 先送り事項

- 実機で、同じ Y 軸一定角速度について通常加速度と 0G を比較し、pitch 復元挙動の差を記録する。
- 実機で、接続中に0Gへ切り替えた場合と、未接続中から0Gを保持して接続した場合を比較する。
- 比較結果に応じた姿勢推定モデルまたは加速度生成方式の変更は、原因を確認してから別作業単位で扱う。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を作成した
- [x] TDD Test List を更新した
- [x] 検証結果または未実行理由を記録した
- [x] public configuration target の追加を初期仕様へ反映し、package gateを記録した
