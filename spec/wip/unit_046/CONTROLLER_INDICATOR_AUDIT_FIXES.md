# コントローラーインジケータ画像監査指摘の修正 仕様書

## 1. 概要

### 1.1 目的

Windows の通常 Qt 描画で確認されたコントローラーインジケータの配置、比率、可動表示、IMU 可読性、日本語翻訳の不整合を解消する。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user request | 画像監査で検出した問題を順番に解消し、テストだけでなく再撮影でも確認する | conversation |
| visual audit | 既定表示、複合入力、800x520 表示で輪郭交差、比率、可動点、IMU、翻訳を確認した | `tmp/gui-audit/controller-indicator-review-20260725-005724/` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| 利用者 / コントローラー図 | ニュートラルまたはボタン入力 | 操作部が本体上の適切な位置に収まり、輪郭線が操作部を横切らない | 肩ボタンは上端に接続して見える |
| 利用者 / スティック表示 | 最大斜め入力 | 可動ノブ全体がスティック外周内に収まる | 入力方向は維持する |
| 利用者 / 最小ウィンドウ | 800x520 で IMU 入力を表示 | 見出し、軸、棒またはベクトルを分離して読める | tooltip の数値契約は維持する |
| 日本語利用者 / 状態表示 | マウス入力の有効・無効を表示 | 「マウス入力」を含めアプリ固有文言が日本語になる | 翻訳元は英語とする |

## 2. 対象範囲

- フェイスプレート、グリップ、肩ボタン、十字キー、ABXY、スティックの相対配置と比率。
- フェイスプレート内部の不要な輪郭線。
- スティック可動ノブの移動範囲。
- 最小ウィンドウでのジャイロ、加速度表示の配置。
- 日本語 `.ts` と実行時 `.qm` の同期、および主要翻訳の回帰検査。
- 変更ごとの Windows Qt 通常描画による画像監査。

## 3. 対象外

- 入力評価、Bluetooth 送信、色設定の保存動作。
- 公式製品画像、ロゴ、精密な実機再現。
- ピクセル完全一致の画像試験。
- コントローラーインジケータ以外のツールバー、状態バー、設定ダイアログの再設計。

## 4. 関連 docs

- `spec/initial/ui.md`
- `spec/complete/unit_034/CONTROLLER_PREVIEW_VISUALIZATION.md`
- `spec/complete/unit_037/UI_VISUAL_DESIGN_REASSESSMENT.md`
- `spec/complete/unit_044/CONTROLLER_INDICATOR_SILHOUETTE.md`
- `spec/complete/unit_045/CONTROLLER_REFERENCE_PROPORTIONS.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| 本体上の操作部 | ニュートラル、単独押下、複数押下 | 十字キー、ABXY、スティックがフェイスプレート内に収まり、輪郭線が背後を横切らない | 肩ボタンはフェイスプレート上端に接続する |
| 操作部の比率 | 960x640 と 800x520 | 十字キーがスティックより大きくならず、ABXY と肩ボタンが同一図内で不釣り合いにならない | 円形要素は円を維持する |
| スティック可動点 | `(-1, 1)`、`(1, -1)` | 可動ノブ全体が外周円内に収まる | スティック押下輪郭と併用できる |
| IMU 表示 | ニュートラルと複数軸入力 | 最小サイズでも見出し、軸ラベル、グラフが重ならない | 数値は tooltip とアクセシビリティ説明へ置く |
| 日本語状態バッジ | 日本語、マウス入力 ON/OFF | `マウス入力: 有効/無効 (F5)` と表示する | `.qm` の実際の翻訳結果を検査する |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-skipped | Face controls remain inside the faceplate and the visible faceplate boundary does not cross them | regression | unit | red / green 2026-07-25、画像監査 `unit_046-face-green` |
| refactor-skipped | Directional pad, face buttons, sticks, and shoulders keep a balanced relative scale at default and minimum sizes | regression | unit | red / green 2026-07-25、画像監査 `unit_046-proportions-green` |
| todo | Stick knobs remain completely inside their outer rings at maximum diagonal input | edge | unit | 左上、右下 |
| todo | IMU headings, axis labels, and plots have separate readable regions at the minimum window size | regression | unit | 800x520 |
| todo | The compiled Japanese catalog translates the mouse-input status label used at runtime | regression | integration | `.qm` を直接検査 |

## 7. 設計メモ

- 座標試験は矩形同士の非交差だけでなく、フェイスプレートのパスに操作部全体が含まれることを確認する。
- 外形、操作部、状態表示、IMU の描画層を分け、装飾線が操作部の背後へ残らない順序にする。
- 画像監査は既定サイズの無入力と複合入力、800x520 の複合入力を同じシナリオで比較する。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/ui/preview_layout.py` | modify | 本体、操作部、状態、IMU の相対配置 |
| `src/demi/ui/controller_preview.py` | modify | 外形、可動ノブ、IMU の描画 |
| `src/demi/i18n/demi_ja.qm` | modify | 日本語翻訳カタログの同期 |
| `tests/unit/ui/test_preview_layout.py` | modify | 本体内配置、比率、最小表示の回帰 |
| `tests/unit/ui/test_controller_preview.py` | modify | 描画、スティック、IMU の回帰 |
| `tests/integration/package/test_translation_catalog.py` | modify | 実行時翻訳の回帰 |
| `spec/initial/ui.md` | modify | 修正後の表示契約 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/unit/ui/test_controller_preview.py -q -p no:cacheprovider --basetemp tmp/pytest-unit046-face-red-2` | red | A がフェイスプレート外にあることを確認 |
| `uv run pytest tests/unit/ui/test_controller_preview.py tests/unit/ui/test_preview_layout.py -q -p no:cacheprovider --basetemp tmp/pytest-unit046-face-green-attempt2` | pass | 34 passed |
| `uv run python .agents/skills/inspect-gui-states/scripts/capture_gui.py --scenario tmp/gui-audit/controller-indicator-review-20260725-005724/scenario.py --output tmp/gui-audit/unit_046-face-green` | pass | 既定、複合入力、800x520 で輪郭交差がないことを画像確認 |
| `uv run pytest tests/unit/ui/test_controller_preview.py -q -p no:cacheprovider --basetemp tmp/pytest-unit046-proportions-red` | red | 十字キー全幅が左スティック直径の1.6倍であることを確認 |
| `uv run pytest tests/unit/ui/test_controller_preview.py tests/unit/ui/test_preview_layout.py -q -p no:cacheprovider --basetemp tmp/pytest-unit046-proportions-green-attempt2` | pass | 35 passed |
| `uv run python .agents/skills/inspect-gui-states/scripts/capture_gui.py --scenario tmp/gui-audit/controller-indicator-review-20260725-005724/scenario.py --output tmp/gui-audit/unit_046-proportions-green` | pass | 3状態で十字キー、肩ボタン、ABXY の比率と重なりを画像確認 |
| targeted pytest | not run | 残りの TDD item ごとに red / green を記録する |
| `inspect-gui-states` capture | not run | 残りの修正後に別出力先へ撮影する |
| standard gate | not run | 完了前に実行する |

## 10. 先送り事項

- none

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [ ] TDD Test List を更新した
- [ ] 検証結果または未実行理由を記録した
- [x] package / release / public API は変更対象外であることを確認した
