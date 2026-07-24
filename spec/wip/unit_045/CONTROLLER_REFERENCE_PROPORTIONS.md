# コントローラーインジケータの実機に沿った比率 仕様書

## 1. 概要

### 1.1 目的

利用者提供のPro Controller正面画像と比較し、独自のコントローラー図を実機の外形と操作部の上下関係に沿って見直す。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user-provided reference image | フェイスプレート、下方グリップ、スティックと十字キーの位置関係を確認 | conversation attachment |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| 利用者 / コントローラー図 | 通常表示 | 上側が幅広い本体と、外側から下へ伸びる左右グリップとして読める | 公式画像・ロゴは使わない |
| 利用者 / 入力表示 | 左スティックと十字キー | 左スティックが十字キーより上、十字キーが左下に見える | 既存の押下表示を維持 |

## 2. 対象範囲

- 上側が幅広く下側中央が狭まる、独自のフェイスプレート外形を描く。
- フェイスプレートの外側から下へ伸びる左右グリップへ、既存の左右色設定を適用する。
- 左スティックを十字キーより上へ配置する。
- 状態バッジをグリップ下、IMU表示上へ維持する。

## 3. 対象外

- 参照画像、公式製品画像、ロゴ、材質感の複製。
- 入力評価、F5の切替、色設定値、各操作の入力契約。

## 4. 関連 docs

- `spec/initial/ui.md`
- `spec/complete/unit_044/CONTROLLER_INDICATOR_SILHOUETTE.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| 外形 | 通常表示 | フェイスプレートは上側が広く、中央下部は左右グリップの間で狭まる | 独自の簡略図 |
| 左右グリップ | 色設定あり | 本体外側から下へ連続し、左右色が各グリップ全体を示す | 内部パネルにはしない |
| 左側操作部 | 通常・押下 | 左スティックが十字キーの上、十字キーが左下にある | 方向別の押下表示を維持 |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-skipped | Grips extend outside the faceplate and finish above the mouse-input status | regression | unit | ui: red 2026-07-25, green 2026-07-25 |
| refactor-skipped | The left stick is above the directional pad in the controller layout | regression | unit | ui: red 2026-07-25, green 2026-07-25 |
| refactor-skipped | The complete controller silhouette contains both colored grip regions | regression | unit | geometry guard: red and green 2026-07-25 |
| green | Rendered grips visually match the reference's broad sloped shoulders, front-panel seam, and vertical handles | acceptance | manual | red: `unit_045-grip-union`, `unit_045-grip-visual-3`; green: `unit_045-grip-layer`,目視確認 2026-07-25 |
| deferred | IMU indicators remain readable at 800x520 | regression | integration | self-review finding 2; next cycle |
| deferred | Directional-pad directions render as one connected cross | regression | unit | self-review finding 3; later cycle |

## 7. 設計メモ

- 参照画像は形状関係を確認するために使い、画像データは製品へ含めない。
- 全体外周は1本のQPainterPathで描き、本体前面の輪郭線は色付きグリップ上部を横切る斜めの継ぎ目として残す。
- 描画順はグリップ、本体前面、外周線と継ぎ目、操作部とし、本体前面がグリップ上部を覆う。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/ui/preview_layout.py` | modify | フェイスプレート、グリップ、状態、操作部の配置 |
| `src/demi/ui/controller_preview.py` | modify | 本体・グリップ外形の描画 |
| `tests/unit/ui/test_controller_preview.py` | modify | 比率と操作部位置の回帰 |
| `spec/initial/ui.md` | modify | 図形の契約 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv lock --check` | pass | lockfile変更なし |
| `uv run ruff format --check .` / `uv run ruff check .` / `uv run ty check --no-progress` | pass | 2026-07-25 |
| `uv run pytest tests/unit -q -p no:cacheprovider --basetemp tmp/pytest-unit_045-final` | pass | 307 passed |
| `uv run pytest tests/integration -q -p no:cacheprovider --basetemp tmp/pytest-integration-unit_045-final` | pass | 131 passed |
| `uv build` | pass | sdistとwheelを生成 |
| `uv run python .agents/skills/inspect-gui-states/scripts/capture_gui.py --scenario tmp/gui-audit/unit_044/scenario.py --output tmp/gui-audit/unit_045-lower-grips` | pass | Windows Qt描画で外周、グリップ位置、ON/OFF、押下を確認 |
| `uv run pytest tests/unit/ui/test_controller_preview.py -q -p no:cacheprovider --basetemp tmp/pytest-unit_045-grip-green-2` | pass | 15 passed。外周外に残るグリップ面積がないことを確認 |
| `uv run python .agents/skills/inspect-gui-states/scripts/capture_gui.py --scenario tmp/gui-audit/unit_044/scenario.py --output tmp/gui-audit/unit_045-grip-union` | fail | グリップが細い接点から吊られた涙滴形であり、本体前面とグリップの継ぎ目も消えているため不合格 |
| `uv run python .agents/skills/inspect-gui-states/scripts/capture_gui.py --scenario tmp/gui-audit/unit_044/scenario.py --output tmp/gui-audit/unit_045-grip-visual-3` | fail | 肩と縦長比率は改善したが、グリップを本体前面より後に塗ったため色面が操作部側へ入り込んでいる |
| `uv run python .agents/skills/inspect-gui-states/scripts/capture_gui.py --scenario tmp/gui-audit/unit_044/scenario.py --output tmp/gui-audit/unit_045-grip-layer` | pass | 実機画像と目視比較し、グリップが背面、本体前面が手前となり、外側の肩、継ぎ目、縦長の把持部が読めることを確認 |
| `uv run ruff format --check .` / `uv run ruff check .` / `uv run ty check --no-progress` | pass | 外周修正後のstatic gate |
| `uv run pytest tests/unit -q -p no:cacheprovider --basetemp tmp/pytest-unit_045-grip-full` | pass | 308 passed |
| `uv run pytest tests/integration` / `uv build` | not run | 残る2件の修正後、unit_045再完了時に実行する |

## 10. 先送り事項

- 800x520でIMU表示が圧縮される問題は、外周修正後の次サイクルで扱う。
- 十字キーが4つの枠に見える問題は、IMU表示修正後のサイクルで扱う。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を更新した
- [ ] 再開後の検証結果を記録した
- [x] package / release / public API は対象外であることを確認した
