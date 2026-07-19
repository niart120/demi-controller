# UI視覚設計の再検討 仕様書

## 目的

メイン画面、コントローラープレビュー、設定ダイアログの視覚設計を見直し、画面比により丸い操作要素が楕円になる問題を含めて、情報階層・形状・リサイズ時の振る舞いを検証可能な契約にする。

## 根拠

| 区分 | 内容 |
|---|---|
| 確認済みの視覚観察 | `480x300`、`960x640`、`1200x520`、`600x900` の通常 Windows 描画で、プレビュー内のフェイスボタン、十字キー、スティックが画面比に応じて楕円になる。横長・縦長では変形が明瞭である。 |
| 確認済みの実装 | `src/demi/ui/preview_layout.py` は幅・高さを独立して相対座標へ変換し、`src/demi/ui/controller_preview.py` はその矩形を `drawEllipse()` で描画する。 |
| 既存仕様の限界 | unit_034 は相対配置と要素の重なりを検証したが、円形の保持、コントローラー本体の縦横比、画面比ごとの情報階層を契約化していない。 |
| 依頼 | UI デザインを再考する作業仕様を作成する。 |

## 対象範囲

- メイン画面のツールバー、状態表示、コントローラープレビュー、接続・設定ダイアログの視覚的な優先順位を評価する。
- コントローラープレビューに表示する円形要素と、コントローラー本体の縦横比を保つ描画領域の設計を決める。
- 最小・標準・横長・縦長のウィンドウで、読み取りと操作の意味が損なわれない配置を定義する。
- 通常の Windows 描画を PNG で確認する手順と、レイアウト契約を検証するテストを定義する。

## 対象外

- Bluetooth、入力変換、保存形式、ローカライズの機能追加。
- 3D モデル、写真素材、テーマ編集、ブランド素材の導入。
- 既存の実機 Bluetooth 接続・入力遅延の受入確認のやり直し。
- 理由のない独自ウィジェット化。

## 関連文書

- `spec/initial/ui.md`
- `spec/initial/requirements.md`
- `spec/initial/testing.md`
- `spec/complete/unit_034/CONTROLLER_PREVIEW_VISUALIZATION.md`
- `spec/complete/unit_035/INLINE_KEY_MAPPING.md`
- `spec/complete/unit_036/COLOR_SWATCH_BUTTONS.md`

## 利用場面と振る舞い

| 利用場面 | 必要な振る舞い | 完了条件 |
|---|---|---|
| 標準サイズで状態を確認する | 接続状態、主要操作、プレビューの順に視線を誘導する。 | 操作の主目的と現在状態を短時間で区別できる。 |
| 横長・縦長にリサイズする | コントローラー本体と円形操作要素の形を保つ。余剰領域が要素を引き伸ばさない。 | フェイスボタン、十字キー、スティックを円として認識できる。 |
| 狭いウィンドウで使う | 最小サイズまで主要操作と状態表示を読める。 | 重要な操作が重ならず、文字や状態が切れない。 |
| キーボードで操作する | フォーカス位置とダイアログの主操作が視覚的に分かる。 | Tab 移動と Enter/Escape の結果を視覚的に確認できる。 |
| 支援技術を使う | 見た目だけに状態を閉じ込めない。 | ラベル、ツールチップ、アクセシブル名の要否を明記する。 |

## 設計判断

### 確認済みの事実

- `drawEllipse()` は与えられた矩形に従うため、幅と高さが異なれば楕円を描く。
- 現行の相対座標は幅と高さを独立に使うため、画面比が変わると円形要素と本体の比率も変わる。

### 採用した方針

- プレビューには `480x300` と一致する `8:5` の内容領域を設け、中央へ最大内接させる。
- 横長では左右、縦長では上下の余剰領域を背景として残し、操作要素やセンサー情報の位置を画面比で変えない。
- 円形要素の直径は内容領域の短辺を基準に算出し、幅・高さを別々に拡大しない。
- 四角形または方向を示す要素は、意味を損なわない範囲で基準縦横比を保つ。
- ツールバーは固定し、接続と捕捉を先頭へ置く。状態バーでは接続状態と通知を左側、補助状態を右側に置く。
- 設定ダイアログは保存を既定操作とし、不正入力ではダイアログを閉じず該当入力欄へフォーカスを戻す。
- ボタン押下は設定色から独立した黄系アクセント、太い輪郭、暗色文字へ切り替える。
- スティック押下は独立円を廃止し、スティック外周リングで示す。
- ボタンラベルは操作要素の短辺へ追従して拡大する。
- 左右グリップ色は本体下部のグリップ領域へ反映し、スティック表面にはボタン色を使う。

### 検証結果

- `8:5` 内容領域と背景余白は、4 画面比の幾何テストと通常描画で形状保持を確認した。
- センサー情報は内容領域内の本体下へ置き、本体と交差しないことを幾何テストで確認した。
- メインウィンドウの最小 `800x520` では、主要操作と状態表示に文字切れがないことを通常描画で確認した。
- 接続前、接続中、接続エラーの通常描画で、固定ツールバーと状態バーの優先順位を確認した。

## TDD Test List

| ID | 状態 | 検証する契約 |
|---|---|---|
| T-037-01 | refactor-skipped | 基準縦横比を保つプレビュー内容領域を算出できる。8:5 の領域を中央へ最大内接させる。 |
| T-037-02 | refactor-skipped | 円形のフェイスボタン、十字キー、スティックは任意のウィンドウ比でも幅と高さが等しい。 |
| T-037-03 | refactor-done | 内容領域内で主要要素が重ならず、許容領域をはみ出さない。 |
| T-037-04 | refactor-skipped | 最小・標準・横長・縦長の通常描画を取得し、各状態の期待する視覚契約を確認する。 |
| T-037-05 | refactor-skipped | メイン画面の接続状態、主要操作、プレビューの優先順位を UI テストで確認する。 |
| T-037-06 | refactor-skipped | 接続・設定ダイアログのフォーカス、入力検証、主操作の視覚的な一貫性を確認する。 |
| T-037-07 | refactor-skipped | UI 利用上の制約とリサイズ時の仕様を利用者向け文書へ反映する。 |
| T-037-08 | refactor-done | ボタン押下は未押下の塗りに対して 3:1 以上のコントラストを持ち、暗色・明色の設定に依存せず判別できる。 |
| T-037-09 | refactor-done | スティック押下はノブと重なる別円を描かず、スティック全体の状態変化として判別できる。 |
| T-037-10 | refactor-skipped | ボタン内の文字はボタン短辺に追従して拡大し、最小表示でも識別できる。 |
| T-037-11 | refactor-done | 左右グリップ色は本体の左右グリップ領域へ反映し、スティック表面にはボタン色を使う。 |

## 予定する変更箇所

| 区分 | パス | 作業 |
|---|---|---|
| レイアウト | `src/demi/ui/preview_layout.py` | 内容領域、基準縦横比、円形要素の算出を実装する。 |
| 描画 | `src/demi/ui/controller_preview.py` | 内容領域を用いて本体と各要素を描画する。 |
| 画面構成 | `src/demi/ui/main_window.py`、ツールバー、状態表示、ダイアログ | 視覚的優先順位の評価結果に応じて変更する。 |
| テスト | `tests/unit/`、`tests/integration/` | 幾何契約、キーボード操作、画面状態の回帰テストを追加する。 |
| 文書 | `README.md`、`spec/initial/` | 実際に変更した利用者向けの操作・制約と設計契約を更新する。 |

## 検証記録

| 確認 | 状態 | 根拠 |
|---|---|---|
| 現行の視覚再現 | pass | `tmp/gui-audit/ui-self-review-preview/capture-01/` に 4 サイズの通常 Windows 描画を保存した。 |
| 変形原因のコード確認 | pass | 相対座標の独立スケールと `drawEllipse()` の組合せを確認した。 |
| 旧 docs test | historical pass | 固定文字列 assertion 3件は pass だったが、この仕様書を読まず、意味上の整合性を検証していなかった。unit_038 で削除済み。 |
| 文書品質確認 | pass | `README.md`、`spec/initial/ui.md`、`spec/initial/requirements.md`、`spec/initial/testing.md`、本仕様を読み、役割、事実整合、リンク、未検証表示を確認した。仮テキストと文脈依存語の `rg` 検索は該当なし、`git diff --check` は pass。 |
| T-037-01 内容領域 | pass | `uv run pytest -p no:cacheprovider --basetemp tmp\\pytest\\unit037-content-green tests\\unit\\ui\\test_preview_layout.py -q`。9 passed。480x300、1200x520、600x900 で中央配置した 8:5 領域を確認した。 |
| T-037-02 円形要素 | pass | `uv run pytest -p no:cacheprovider --basetemp tmp\\pytest\\unit037-circles-green tests\\unit\\ui\\test_preview_layout.py -q`。12 passed。最小・横長・縦長でフェイスボタン、十字キー、スティックの幅と高さが一致することを確認した。 |
| T-037-03 主要領域 | pass | `uv run pytest -p no:cacheprovider --basetemp tmp\\pytest\\unit037-regions-green tests\\unit\\ui\\test_preview_layout.py tests\\unit\\ui\\test_controller_preview.py -q`。20 passed。本体・状態・センサー・操作要素の境界と実描画の利用を確認した。 |
| T-037-04 通常描画 | pass | `tmp/gui-audit/unit-037-layout/` の 4 PNG と `tmp/gui-audit/unit-037-main-min/` の 800x520 メイン画面を原寸確認した。円形保持、文字切れなし、意図しない重なりなし。横長は左右、縦長は上下を背景余白とする。 |
| T-037-05 メイン画面階層 | pass | `uv run pytest -p no:cacheprovider --basetemp tmp\\pytest\\unit037-hierarchy-green tests\\integration\\ui\\test_main_window_snapshot.py tests\\unit\\ui\\test_toolbar.py tests\\unit\\ui\\test_status_bar.py -q`。6 passed。`tmp/gui-audit/unit-037-hierarchy/` の接続前・接続中・エラー画面で主要操作、接続状態、通知、プレビューの順序と文字切れなしを確認した。 |
| T-037-06 ダイアログ | pass | `uv run pytest -p no:cacheprovider --basetemp tmp\\pytest\\unit037-dialog-green tests\\integration\\ui\\test_dialog_validation.py tests\\integration\\ui\\test_connection_dialog.py tests\\integration\\ui\\test_mapping_dialog.py tests\\integration\\ui\\test_colors_dialog.py -q`。46 passed。`tmp/gui-audit/unit-037-dialogs/` の 3 PNG で保存フォーカス、色見本、タイムアウト選択とエラー説明を確認した。 |
| T-037-07 利用者向け文書 | pass | README へ最小サイズ、`8:5` 内容領域、背景余白、円形保持を記載し、初期 UI・要件・テスト仕様を同じ契約へ更新した。固定文言 assertion は追加していない。 |
| unit test | pass | `uv run pytest -p no:cacheprovider --basetemp tmp\\pytest\\unit037-unit tests\\unit -q`。284 passed。 |
| integration test | pass | 非 UI 15 passed、source entry point 3 passed。UI 一括実行は assertion failure ではなく Qt top-level object の終了処理中に Windows access violation で異常終了したため、16 test file を別プロセスで実行し、合計 102 passed を確認した。 |
| 改善後の通常 Windows 描画確認 | pass | プレビュー 4 画面比、メイン画面 3 状態と最小 800x520、ダイアログ 3 状態の PNG を Windows 通常描画で取得し原寸確認した。 |
| 標準品質ゲート（初回） | historical pass | `uv sync --dev`、`uv lock --check`、`uv run ruff format --check .`、`uv run ruff check .`、`uv run ty check --no-progress`、`uv build`、`git diff --check` はすべて pass。build は sdist と wheel を生成した。 |
| T-037-08～11 視覚意味 | pass | red では既定ボタン色の押下前後が `RGB(15,15,15)` と `RGB(25,25,25)`、コントラスト比1.09:1であり、stick clickの独立円、ラベル拡大関数とグリップ領域の欠落を確認した。`uv run pytest -p no:cacheprovider --basetemp tmp\\pytest\\unit037-grip-final-green tests\\unit\\ui\\test_controller_preview.py tests\\unit\\ui\\test_preview_layout.py -q` は24 passed。 |
| 押下コントラスト改善後の通常描画 | pass | `tmp/gui-audit/unit-037-contrast-final2/` の neutral、複数ボタン押下、左stick click、左右グリップ別色、最小押下の5 PNGを原寸確認した。押下判別、文字サイズ、外周リング、色の反映先に問題なし。 |
| 押下コントラスト改善後の標準品質ゲート | pass | `uv sync --dev`、`uv lock --check`、`uv run ruff format --check .`、`uv run ruff check .`、`uv run ty check --no-progress`、`uv build`、`git diff --check` は pass。unit test は 288 passed、integration test は非 UI 15 passed、UI 102 passed、source entry point 3 passed。仮テキスト検索は該当なし。 |

## 先送り事項

- 立体的なコントローラー表現や画像素材は、2D の形状・階層・可読性が安定してから別作業単位で判断する。
- 実機接続・入力遅延の手動受入は、既存の受入項目のままとし、本作業の変更対象に含めない。

## 完了チェックリスト

- [x] 現行画面の変形を複数のウィンドウ比で再現した。
- [x] 実装上の原因と未検証のデザイン判断を分離した。
- [x] 対象範囲と対象外を定義した。
- [x] リサイズ、形状、情報階層を検証する TDD Test List を作成した。
- [x] 実装前である検証項目を `not run` と記録した。
- [x] 基準縦横比と余剰領域の扱いを決定する。
- [x] メイン画面とダイアログの優先順位を画面状態ごとに評価する。
- [x] 実装、通常描画確認、品質ゲートを完了する。
- [x] ボタン押下のコントラストとスティック押下表示を改善する。
- [x] 改善後の通常描画と標準品質ゲートを完了する。
