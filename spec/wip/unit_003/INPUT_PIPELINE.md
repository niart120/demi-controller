# 入力状態とマッピング 仕様書

## 1. 概要

### 1.1 目的

キーボード・マウスの正規化された状態から、同時押しとフォーカス安全性を保った `ControllerFrame` を生成する。相対マウス差分は `YawPitchModel` でジャイロ角速度と姿勢整合した静的加速度へ変換し、実経過時間を使う 8ms 評価境界へまとめる。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| roadmap | Unit 003 の成果、完了条件、8ms publisher | `spec/initial/roadmap.md` |
| input design | 物理入力、binding、stick 合成、YawPitchModel、neutral | `spec/initial/input.md` |
| requirements | FR-005〜FR-008、FR-014、NFR-001/NFR-002/NFR-005 | `spec/initial/requirements.md` |
| testing design | physical state、mapping、stick、IMU の試験項目 | `spec/initial/testing.md` |
| architecture | 主スレッドの入力評価、ControllerFrame 境界 | `spec/initial/architecture.md` |
| completed domain | LogicalButton、BindingTarget、AppSettings、ControllerFrame | `spec/complete/unit_002/` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| input backend | 正規化された key/mouse press/release | 保持集合へ冪等に反映される | pyglet の具象型は持ち込まない |
| input backend | 1評価周期内の複数 `dx/dy` | 合計値を一度だけ消費する | 消費後は差分 0 |
| mapper | Default または指定 profile と保持状態 | ボタン OR 集約、反対方向 0、斜め stick を含む frame を得る | capture 外は全 neutral |
| yaw/pitch model | `dx`、`dy`、正の `dt` | rad/s の gyro と同じ仮想 pitch の 1G accel を得る | roll、raw 換算、ノイズなし |
| publisher | monotonic clock と capture epoch | sequence 付き frame を 8ms 評価境界から sink へ渡す | 実時間 sleep を内部で行わない |

## 2. 対象範囲

- `KeySource`、`MouseButtonSource`、`PhysicalSource` の正規化。
- `PhysicalInputState` の held set、マウス差分蓄積、consume、clear、revision。
- binding に基づくボタン OR 集約と `source_active XOR inverted`。
- 左右 stick の方向合成、反対方向相殺、amount、円形制限。
- `YawPitchModel` の yaw/pitch、独立感度、Y反転、pitch上限、dt境界、reset。
- neutral のボタン解放、stick 中央、gyro 0、accel `(0, 0, +1) G`。
- monotonic clock を注入した 8ms 評価 publisher と frame sequence/capture epoch。

## 3. 対象外

- pyglet のウィンドウイベント、排他マウス設定、F12 などの UI 優先順位。
- GUI、ControllerView、設定モーダル、接続 runtime、swbt-python 変換。
- Bluetooth、Bumble、Switch 本体。
- global hook、Raw Input、マクロ、連射、トグル、並進・遠心・ノイズ加速度。
- OS 固有のキー表示、OEM キーの別 OS 置換。未解決表示は Unit 007 以降で扱う。

## 4. 関連 docs

- `spec/initial/input.md`
- `spec/initial/appendix/aim-model.md`
- `spec/initial/requirements.md`
- `spec/initial/testing.md`
- `spec/initial/architecture.md`
- `spec/complete/unit_002/DOMAIN_AND_SETTINGS.md`
- `AGENTS.md`
- `SKILLS.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| key/mouse source を保持する | press、release、重複通知 | set が増殖せず、未保持 release は無害 | source は `KEY:F` / `MOUSE:LEFT` 形式 |
| 相対差分を蓄積・消費する | `dx=2,3,-1` | consume は `(4, 0)` を一度返し、次は `(0, 0)` | clear は差分も捨てる |
| button を集約する | 複数 source、inverted、capture flag | 有効 binding が一つでもあれば target を押下する | capture 外は inverted を評価しない |
| stick を合成する | positive/negative、斜め、amount | `positive-negative`、反対方向同時は 0 | circular limit は設定時だけ正規化 |
| neutral frame を生成する | capture 外または reset | buttons empty、stick 中央、gyro 0、accel +1G | yaw/pitch を 0 へ戻す |
| yaw/pitch を更新する | dx/dy、positive dt | yaw は world-up、pitch は上限付き、roll は蓄積しない | 中間 pitch で gyro を投影 |
| dt 境界を扱う | `dt <= 0` | gyro 0、姿勢を更新せず、現在姿勢の accel を返す | 例外や nan を生成しない |
| 移動なし周期を扱う | dx=dy=0、現在 pitch | gyro 0、現在 pitch の static 1G を維持する | pose は維持 |
| publisher が評価する | clock、capture epoch | monotonic_ns、sequence を付けて sink へ offer する | 8ms は評価周期の契約値 |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| todo | KeySource/MouseButtonSource と PhysicalInputState が press/release/duplicate/clear を扱う | new / edge | unit | pyglet なしで正規化を固定 |
| todo | PhysicalInputState が mouse dx/dy を加算し、一度だけ消費する | new / edge | unit | revision と差分 reset を確認 |
| todo | InputMapper が button を複数 source/inverted の OR で集約し capture 外を neutral にする | new / edge | unit | 任意 target、Default binding 境界 |
| todo | InputMapper が左右 stick の反対方向、斜め、amount、circular limit を合成する | new / edge | unit | `-1..1` の domain 値へ渡す |
| todo | YawPitchModel が yaw/pitch、符号、独立感度、Y反転、pitch上限、dt境界、resetを満たす | new / edge | unit | `GyroRate` と `AccelG` のみを返す |
| todo | YawPitchModel が移動なしでも姿勢整合した static 1G を維持する | new / regression | unit | accel norm 1、yaw非依存 |
| todo | InputPublisher が monotonic clock で sequence/epoch 付き frame を 8ms 評価境界へ渡す | new / edge | unit | 実時間 sleep と Bluetooth は使わない |
| todo | input pipeline の全 gate と package smoke が通る | characterization | package | `uv lock --check`、`uv build`、unit を含める |

## 7. 設計メモ

- source の正規化は `demi.domain.physical_input` に置き、pyglet の symbol/button 型を直接受けない。
- `PhysicalInputState` はイベント callback が更新し、mapper が評価周期で差分を consume する。mapper は callback ごとに出力を送らない。
- mapper は Unit 002 の `BindingTarget` と `InputProfile` を使う。button target は `logical_button_for_target()` で解決し、stick target は enum 値の kind から軸へ変換する。
- `YawPitchModel.update()` の返り値は `tuple[GyroRate, AccelG]` とし、`MotionSample` の追加を避ける。raw 値への変換は Unit 006 の責務である。
- `InputPublisher` は時計を注入し、初回評価または reset 後の dt を 0 と扱う。sleep や pyglet schedule は Unit 004 の接続で行う。
- capture epoch の変更後に古い publisher frame を送らない判定は Unit 005 の runtime で行うが、publisher は frame に epoch を付与する。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/domain/physical_input.py` | new | source と PhysicalInputState |
| `src/demi/input/__init__.py` | new | input package |
| `src/demi/input/mapper.py` | new | button/stick/IMU から ControllerFrame |
| `src/demi/input/yaw_pitch_model.py` | new | yaw/pitch と static accel |
| `src/demi/input/publisher.py` | new | Clock、frame sequence、8ms 評価境界 |
| `src/demi/domain/settings.py` | modify | pitch limit の radian 境界が必要な場合だけ追加 |
| `tests/unit/input/test_physical_input.py` | new | source/state behavior |
| `tests/unit/input/test_mapper.py` | new | button/stick aggregation |
| `tests/unit/input/test_yaw_pitch_model.py` | new | gyro/accel behavior |
| `tests/unit/input/test_publisher.py` | new | clock、sequence、epoch |
| `spec/complete/unit_003/INPUT_PIPELINE.md` | new / modify | TDD 状態、検証、完了記録 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv sync --dev` | passed | unit_002 merge 後の baseline |
| `uv lock --check` | passed | unit_002 merge 後の baseline |
| `uv run ruff format --check .` | passed | unit_002 merge 後の baseline |
| `uv run ruff check .` | passed | unit_002 merge 後の baseline |
| `uv run ty check --no-progress` | passed | unit_002 merge 後の baseline |
| `uv run pytest tests/unit` | passed | 42 passed、unit_002 merge 後 |
| `uv build` | passed | unit_002 merge 後の baseline artifact |
| `uv run pytest tests/integration` | not applicable | `tests/integration` tree は未作成 |

## 10. 先送り事項

- pyglet の実イベントから source へ変換する処理は Unit 004 で実装する。
- capture epoch の古い frame 破棄と 250ms watchdog は Unit 005 で扱う。
- swbt の IMU raw/physical API 変換は Unit 006 で扱う。
- OEM key の platform-specific 表示・未解決 UI は Unit 007 以降で扱う。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を作成した
- [ ] 検証結果または未実行理由を実装後に更新した
- [ ] package / release / public API に触れる場合の gate を記録した
- [ ] 完了時に `spec/complete/unit_003` へ移動した
