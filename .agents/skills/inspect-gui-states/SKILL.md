---
name: inspect-gui-states
description: "この Python repo の PySide6 GUI の任意の画面状態を Windows の通常描画で PNG に取得し、Codex の画像理解で UI/UX を確認、改善前後を比較し、UI テストを組み立てやすくする skill。画面のレイアウト、可読性、情報階層、操作状態、ダイアログ、入力検証、エラー表示を確認または改善するときに使う。"
---

# GUI 状態の画像レビュー

実際の Qt Widget と一時シナリオから任意の画面状態を取得し、画像として確認する。画面遷移は対象状態へ到達する手段であり、記録自体を目的にしない。

## 手順

1. UI/UX の確認目的と、比較する画面状態を決める。通常、選択中、無効、処理中、空、エラー、ダイアログ表示など、依頼に関係する状態だけを選ぶ。
2. 対象画面に最も近い `tests/integration/ui` のテストを探し、実 Widget の組み立て方、状態データ、操作経路を確認する。
3. `tmp/gui-audit/<task>/scenario.py` に `run(capture)` を定義する。製品の実行系、Bluetooth、入力捕捉は起動せず、既存テスト相当のメモリー内代替実装を使う。
4. Windows の通常 Qt platform で各状態を PNG にする。操作経路も確認対象なら QAction や Widget の公開操作で状態へ到達する。
5. 生成された PNG を `view_image` の `original` で開き、見えている事実と UI/UX 上の解釈を分けて確認する。
6. 改善を行った場合は同じ状態を再撮影し、情報階層、可読性、配置、操作への応答がどう変わったかを比較する。
7. UI テストを追加する場合は、画像で見つけた重要な状態を文字列、表示、活性、選択、配置などの振る舞いに基づく検証へ落とす。

```powershell
uv run python .agents/skills/inspect-gui-states/scripts/capture_gui.py `
  --scenario tmp/gui-audit/<task>/scenario.py `
  --output tmp/gui-audit/<task>
```

## 確認観点

- 情報の優先順位、見出し、ラベル、値の読み取りやすさ。
- 余白、整列、切れ、重なり、過密、不要な空白。
- 通常、選択、無効、処理中、エラーの違いと操作可能性の伝わり方。
- ツールバー、ステータスバー、ダイアログ間の語彙、配置、操作への応答の一貫性。

所見は画像で確認できる事実、そこからの解釈、改善提案、未確認状態に分ける。画像だけで操作性や内部状態を断定しない。

## シナリオ契約

シナリオは次の形にする。

```python
from demi.app import WindowSpec
from demi.ui.main_window import MainWindow


def run(capture) -> None:
    window = MainWindow(WindowSpec(width=960, height=640, maximized=False))
    capture.state("main-idle", window)
```

`capture` は次を提供する。

- `capture.application`: プロセス全体で共有する `QApplication`。
- `capture.settle()`: Qt の保留イベントを1巡処理する。
- `capture.state(name, widget)`: Widget を表示し、イベント反映後に連番 PNG を保存する。
- `capture.paths`: 取得済み PNG の読み取り専用一覧。

操作後に生成された Widget を取得する場合は、`capture.settle()` の後で取得する。ツールバーの action を発火した後に `window.active_settings_dialog` を確認し、その Widget を `capture.state()` へ渡す使い方を想定する。

## UI テスト支援

- 既存テストの fixture と代替実装を画面状態の正本として再利用する。
- 一時シナリオで必要な状態を再現できた後、回帰価値がある状態だけを恒久テストへ移す。
- PNG は視覚レビューの証跡とし、自動テストの合否は安定した Widget の状態と振る舞いで判定する。

## Guardrails

- シナリオと画像は git 管理外の `tmp/gui-audit` に置く。既存 PNG がある出力先は再利用しない。
- 基準画像、ピクセル差分、動画、OCR、座標ベースの汎用操作は追加しない。
- デスクトップ全体を撮影しない。PNG は `QWidget.grab()` が返す Qt Widget の描画領域だけを含む。
- `offscreen` へ暗黙に切り替えない。Windows の通常描画を使えない場合は未実行として報告する。
- 撮影のために製品コードや恒久テストへ一時処理を残さない。
