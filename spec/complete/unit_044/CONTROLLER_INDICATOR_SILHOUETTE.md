# コントローラーインジケータの外形と状態表示 仕様書

## 1. 概要

### 1.1 目的

マウス入力状態をコントローラー図の下へ置き、独自の簡略図をPro Controllerの正面形状として無理のない外形へ見直す。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user request | 状態表示をコントローラーの下へ移し、コントローラーインジケータを見直す | conversation |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| 利用者 / メイン画面 | F5でマウス入力を切替 | コントローラー図の直下にON/OFFが見える | 色設定は維持 |
| 利用者 / コントローラー図 | 通常表示 | 中央部から左右グリップが連続する簡略正面図に見える | 公式製品画像は使わない |

## 2. 対象範囲

- コントローラー図の下へマウス入力状態バッジを置く。
- 本体と、左右外側から下方へ伸びる縦長グリップを連続した簡略シルエットで描く。
- 十字キーを十字形として描く。
- 本体、ボタン、左右グリップの色設定と入力状態の表示を維持する。

## 3. 対象外

- 公式製品画像・ロゴ・精密な実機再現。
- F5の切替動作、入力評価、色設定画面の変更。

## 4. 関連 docs

- `spec/initial/ui.md`
- `spec/complete/unit_043/CONTROLLER_GUI_MOUSE_INPUT_STATUS.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| 状態表示の位置 | 通常表示 | バッジが本体とグリップの下、IMU表示の上にある | ON/OFF色とF5表記を維持 |
| 外形 | 通常表示 | 中央本体から左右外側へ縦長グリップが連続する | 独自の簡略図 |
| 十字キー | 十字キー入力 | 十字形の該当方向が押下表示になる | 既存の方向別入力を維持 |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-skipped | Mouse input status is laid out below the controller silhouette and above IMU indicators | regression | unit | ui: red 2026-07-24, green 2026-07-24 |
| refactor-skipped | Controller preview renders a connected vertical-grip silhouette and a cross-shaped directional pad while preserving per-direction input feedback | new | unit | ui: red 2026-07-24, green 2026-07-24 |

## 7. 設計メモ

- 外形はQPainterPathで描き、色設定は本体と左右の縦長グリップ領域へそれぞれ適用する。
- 形状の評価はWindowsのQt通常描画を画像で確認し、画素完全一致は契約にしない。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/ui/preview_layout.py` | modify | 状態・IMU領域の配置 |
| `src/demi/ui/controller_preview.py` | modify | 外形、グリップ、十字キーの描画 |
| `tests/unit/ui/test_controller_preview.py` | modify | レイアウトと方向入力の回帰 |
| `spec/initial/ui.md` | modify | 図形と状態表示の契約 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv lock --check` | pass | lockfile変更なし |
| `uv run ruff format --check .` / `uv run ruff check .` / `uv run ty check --no-progress` | pass | 2026-07-24 |
| `uv run pytest tests/unit -q -p no:cacheprovider --basetemp tmp/pytest-unit_044-final-vertical` | pass | 305 passed |
| `uv run pytest tests/integration -q -p no:cacheprovider --basetemp tmp/pytest-integration-unit_044-final-vertical` | pass | 131 passed |
| `uv build` | pass | sdistとwheelを生成 |
| `uv run python .agents/skills/inspect-gui-states/scripts/capture_gui.py --scenario tmp/gui-audit/unit_044/scenario.py --output tmp/gui-audit/unit_044-vertical-grips` | pass | Windows Qt描画でOFF、ON、十字キー左、A、青赤の縦長グリップを確認 |
| 文書レビュー | pass | `spec/initial/ui.md` と本仕様書の対象範囲、対象外、文言を確認 |

## 10. 先送り事項

- none

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を更新した
- [x] 検証結果を記録した
- [x] package / release / public API は対象外であることを確認した
