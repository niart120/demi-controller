# コントローラーとインジケータのカラム整列 仕様書

## 1. 概要

### 1.1 目的

コントローラー下部のグリップが本体幅より外側へ膨らむ輪郭を内側へ収める。Mouse input、Gyro、Accelerationの左右端をコントローラー本体と同じラインへ揃え、プレビュー全体を一つの中央カラムとして読むことができる配置へ直す。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user feedback | コントローラーが下膨れして見えるため、下部の丸みを外側へ出さない | conversation |
| user feedback | GyroがMouse inputより外側へ飛び出して見えるため、左右ラインを揃える | conversation |
| user feedback | 個別修正に合わせてGUI全体の配置バランスも見直す | conversation |
| visual baseline | unit_048完了時の既定、複合入力、最小表示 | `tmp/gui-audit/unit_048-final/` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| 利用者 / コントローラー外形 | 既定または複合入力 | グリップの丸みが本体の左右ラインより外へ張り出さない | 約3:2の比率と操作部配置を維持する |
| 利用者 / 状態・IMU表示 | 既定または複合入力 | Mouse input、Gyro、Accelerationが本体と同じ左右ライン内に収まる | IMUの最小高さと数値表現を維持する |
| 利用者 / 最小表示 | 800x520ウィンドウ | 中央カラムの左右端、ラベル、グラフが切れずに読める | ステータスバーと重ねない |

## 2. 対象範囲

- 左右グリップの横方向境界。
- Mouse input、Gyro、Accelerationの横方向境界。
- 通常幅と最小幅のWindows Qt通常描画による全体バランス確認。

## 3. 対象外

- コントローラー上面曲線と操作部配置。
- Mouse input、Gyro、Accelerationの値と状態。
- IMU領域の縦位置と高さ。
- 色、入力処理、ピクセル一致試験。

## 4. 関連 docs

- `spec/initial/ui.md`
- `spec/complete/unit_048/CONTROLLER_COMPACT_LAYOUT.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| グリップ境界 | 960x600、800x475のプレビュー領域 | 左右グリップの外側境界が本体の左右境界内に収まる | 下側の曲率は維持する |
| 共通カラム | 同上 | 本体、Mouse input、IMU全体の左端と右端が一致する | Qt論理座標で比較する |
| IMU分割 | 同上 | GyroとAccelerationが共通カラムを左右均等に分け、中央に間隔を持つ | 両領域の幅を等しくする |
| 最小表示 | 800x475のプレビュー領域 | GyroとAccelerationが各90px以上の高さを維持する | unit_047契約 |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-skipped | Grip regions stay within the body horizontal bounds | regression | unit | 本体左右端と一致、追加整理は不要 |
| refactor-skipped | Body, mouse status, and combined IMU regions share both horizontal edges | regression | unit | 描画幅18%〜82%、追加整理は不要 |
| refactor-skipped | Gyro and acceleration regions have equal widths and a center gap | regression | unit | 各30%、中央4%、追加整理は不要 |
| refactor-skipped | Default, mixed-input, and minimum states retain readable plots in one aligned column | visual | integration | 3状態で確認、構造整理は対象外 |

## 7. 設計メモ

- グリップの丸みは削除せず、外接する横幅だけをフェイスプレート内へ移す。
- 状態表示とIMU全体は本体幅と同じ64%を使う。
- GyroとAccelerationは各30%、中央間隔4%として共通カラムを分割する。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/ui/preview_layout.py` | modify | グリップとIMU横境界 |
| `tests/unit/ui/test_preview_layout.py` | modify | 共通カラムとIMU分割 |
| `tests/unit/ui/test_controller_preview.py` | modify | グリップ内包 |
| `spec/initial/ui.md` | modify | 採用後の外形と配置契約 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run python .agents/skills/inspect-gui-states/scripts/capture_gui.py --scenario tmp/gui-audit/controller-indicator-review-20260725-005724/scenario.py --output tmp/gui-audit/unit_049-baseline` | pass | グリップが本体より外側へ張り出し、IMU全体がMouse inputより左右へ広がる基準状態を確認 |
| `uv run pytest tests/unit/ui/test_controller_preview.py::test_controller_layout_keeps_rounded_grips_within_the_faceplate_width -q -p no:cacheprovider --basetemp tmp/pytest-unit049-grips-red` | red | 左グリップが本体左端より9.6px外側にあるため1 failed |
| `uv run pytest tests/unit/ui/test_controller_preview.py tests/unit/ui/test_preview_layout.py -q -p no:cacheprovider --basetemp tmp/pytest-unit049-grips-green-attempt2` | pass | 52 passed、左右グリップ外端を本体端へ整列 |
| `uv run pytest tests/unit/ui/test_preview_layout.py::test_controller_status_and_imu_share_one_horizontal_column -q -p no:cacheprovider --basetemp tmp/pytest-unit049-column-red` | red | IMU左端がMouse input左端より115.2px外側にあるため2 failed |
| `uv run pytest tests/unit/ui/test_controller_preview.py tests/unit/ui/test_preview_layout.py -q -p no:cacheprovider --basetemp tmp/pytest-unit049-column-green` | pass | 54 passed、共通左右端とIMU等幅分割を確認 |
| `uv run python .agents/skills/inspect-gui-states/scripts/capture_gui.py --scenario tmp/gui-audit/controller-indicator-review-20260725-005724/scenario.py --output tmp/gui-audit/unit_049-column-attempt1` | pass | 既定、複合入力、最小表示で内向きグリップと中央カラムを確認 |
| standard gate | not run | 完了前に実行する |

## 10. 先送り事項

- none

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test Listを更新した
- [x] 検証結果または未実行理由を記録した
- [x] package / release / public APIは変更対象外であることを確認した
