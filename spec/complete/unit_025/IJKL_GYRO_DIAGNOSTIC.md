# I/J/K/L ジャイロ診断入力 仕様書

## 1. 概要

### 1.1 目的

マウス移動量と入力評価周期に依存しない一定角速度を I/J/K/L キーから生成し、Y 軸 / Z 軸のジャイロ挙動を検証できるようにする。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user request | マウスジャイロとは独立した Y 軸 / Z 軸の一定速度回転をキー入力する | 作業依頼 |
| intent delta | 右スティックと競合するアローキー、キーボード差を生むテンキーを避け、未使用の I/J/K/L を使う | 作業依頼 |
| input design | `CAPTURED` 中のキー保持状態、Pro Controller 基準の IMU 座標、入力優先順位 | `spec/initial/input.md` |
| completed input pipeline | `PhysicalInputState`、`InputPublisher`、`ControllerFrame` の現行契約 | `spec/complete/unit_003/INPUT_PIPELINE.md` |
| completed mouse gyro | マウス移動量の再標本化とジャイロ連続性 | `spec/complete/unit_024/SMOOTH_MOUSE_GYRO.md` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| 利用者 | 入力捕捉中に I/J/K/L を保持する | Y 軸または Z 軸へ一定角速度が出続ける | マウス移動や評価間隔に依存しない |
| 入力評価 | 同一軸の反対方向キーを同時に保持する | 対象軸の角速度が 0 になる | 他方の軸は独立して評価する |
| 入力評価 | 保存済み profile が I/J/K/L を割り当てている | 診断用ジャイロだけを生成し、スティックやボタンへ同じキーを流さない | 既存設定ファイルの移行を要求しない |
| 利用者 | マウスジャイロを無効にして I/J/K/L を保持する | キー由来のジャイロは有効なまま | マウス設定を診断入力へ適用しない |

## 2. 対象範囲

- `I / K` を Y 軸、`J / L` を Z 軸の固定診断入力として評価する。
- 角速度の絶対値を `1.0 rad/s` とする。
- 現行マウス操作と同じ符号に合わせ、`I = -Y`、`K = +Y`、`J = +Z`、`L = -Z` とする。
- マウス由来の `GyroRate` と I/J/K/L 由来の `GyroRate` を軸ごとに加算する。
- I/J/K/L を通常の profile binding より優先し、同一キーの binding を評価しない。
- 組み込み Default profile とアローキーの右スティック割り当ては変更しない。

## 3. 対象外

- 一定角速度の設定 UI、設定ファイル項目、実行時変更。
- X 軸の診断入力。
- アローキー、テンキー、Default profile の binding 変更。
- マウス差分の再標本化、感度、Y 反転、pitch 上限の変更。
- Raw Input、排他マウス、Qt のキー正規化処理の変更。
- Bluetooth report 周期、swbt-python、HID raw 値変換の変更。
- 実機またはゲーム画面を使う操作感の受入。

## 4. 関連 docs

- `spec/initial/input.md`
- `spec/initial/configuration.md`
- `spec/initial/testing.md`
- `spec/initial/architecture.md`
- `spec/complete/unit_003/INPUT_PIPELINE.md`
- `spec/complete/unit_024/SMOOTH_MOUSE_GYRO.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| Y 軸を一定回転する | `I` または `K` を保持 | `-1.0` または `+1.0 rad/s` を Y 軸へ出力 | 評価間隔によらない |
| Z 軸を一定回転する | `J` または `L` を保持 | `+1.0` または `-1.0 rad/s` を Z 軸へ出力 | 評価間隔によらない |
| 反対方向を相殺する | 同じ軸の両方向を保持 | 対象軸は `0.0 rad/s` | Y / Z は別々に相殺する |
| マウス設定から分離する | `gyro_enabled = false` で I/J/K/L を保持 | キー由来の角速度を出力 | マウス由来は 0 |
| マウス入力と合成する | マウス移動と I/J/K/L 保持 | 両方の角速度を軸ごとに加算 | 加速度は現行 `YawPitchModel` の姿勢を使う |
| 通常 mapping を抑止する | I/J/K/L と同じ source の binding が存在 | その binding のボタン / スティック入力を生成しない | 保存済み profile にも適用 |
| 捕捉外を neutral にする | `capture_active = false` | ジャイロ 0、スティック中央、保持キー消去 | 現行 neutral 契約を維持 |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-skipped | 捕捉中の I/J/K/L は、マウスジャイロ無効時も評価間隔によらない一定の Y / Z 角速度を生成し、同じ source の profile binding を評価しない | new | unit | red で角速度 0 を確認。green 後は 4 方向、4 / 16 ms、右スティック中央を確認。追加の構造変更は不要 |
| refactor-skipped | 同一軸の反対方向は相殺され、キー解放または捕捉解除で I/J/K/L 由来の角速度が残留しない | edge / regression | unit | red で片側解放後も角速度 0 を確認。green 後は相殺、片側解放、捕捉解除を確認。追加の構造変更は不要 |
| refactor-skipped | マウス移動と I/J/K/L を同時入力すると、マウス由来の角速度へ固定角速度が軸ごとに加算される | new | unit | red でマウス値だけが出ることを確認。green 後は Y / Z への加算と加速度不変を確認。追加の構造変更は不要 |

## 7. 設計メモ

I/J/K/L は profile binding ではなく、`CAPTURED` 中だけ有効な固定診断入力として扱う。入力評価時に同じ source を通常 mapping から除外し、保存済み profile に I/J/K/L が含まれていても二重入力を発生させない。アローキーは現行どおり右スティックへ割り当てる。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/input/mapper.py` | modify | 固定角速度の合成と I/J/K/L source の通常 mapping 抑止 |
| `src/demi/input/publisher.py` | modify | マウス由来と I/J/K/L 由来の角速度を合成 |
| `tests/unit/input/test_publisher.py` | modify | 一定速度、相殺、解放、マウス合成の回帰試験 |
| `spec/initial/input.md` | modify | 入力優先順位と固定診断操作を更新 |
| `spec/initial/configuration.md` | modify | profile 外の固定診断キーを記録 |
| `spec/initial/testing.md` | modify | I/J/K/L ジャイロの単体試験項目を追加 |
| `spec/initial/requirements.md` | modify | 固定ジャイロ診断入力の受入条件を追加 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/unit/input/test_publisher.py -q -p no:cacheprovider` | failed as expected | red: I/J/K/L 版で 6 failed、12 passed。固定ジャイロ合成が未実装のため失敗 |
| `uv run pytest tests/unit/input/test_publisher.py -q -p no:cacheprovider` | passed | green: 18 passed |
| `uv run pytest tests/unit/input/test_publisher.py tests/unit/domain/test_mapping.py tests/unit/domain/test_settings.py -q -p no:cacheprovider` | passed | 37 passed。アローキーを含む Default profile 28 binding も維持 |
| `uv sync --dev` | passed | 77 packages resolved、74 packages checked |
| `uv lock --check` | passed | 77 packages resolved |
| `uv run ruff format --check .` | passed | 129 files already formatted |
| `uv run ruff check .` | passed | All checks passed |
| `uv run ty check --no-progress` | passed | All checks passed |
| `uv run pytest tests/unit -q -p no:cacheprovider` | passed | 216 passed |
| `$env:QT_QPA_PLATFORM='offscreen'; $env:PYTHONUTF8='1'; uv run pytest tests/integration -q -p no:cacheprovider --basetemp <workspace-path>` | passed | 73 passed。既定 `%TEMP%` は権限エラー、sandbox 内の wheel install は cp932 decode error になったため、workspace 内 basetemp とネットワーク許可で再実行 |
| `uv build` | passed | 初回は sandbox の PyPI 接続制限で失敗。ネットワーク許可で sdist と wheel を生成 |
| `uv run pytest tests/unit/test_documentation.py tests/unit/test_work_unit_records.py -q -p no:cacheprovider` | passed | 3 passed |
| docs-quality review | passed | 対話依存語と仮テキストなし。既存の「前回評価」2件は時間境界を表す仕様用語 |
| agentic self-review | passed | 対象範囲、対象外、Intent Delta、diff、gate を照合。Default profile、設定 schema、Raw Input、swbt に変更なし。実機受入は先送り事項として明記 |
| `git diff --check` | passed | whitespace error なし |

## 10. 先送り事項

- 実機またはゲーム画面での回転方向と一定速度の受入は、機材を使う検証作業で記録する。
- 角速度の設定 UI と診断キーの任意割り当ては、固定診断入力の目的を超えるため別作業単位とする。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を作成した
- [x] TDD Test List を更新した
- [x] 検証結果または未実行理由を記録した
- [x] package / release / public API に触れないことを確認した
