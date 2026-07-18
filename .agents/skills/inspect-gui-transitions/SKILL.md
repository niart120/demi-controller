---
name: inspect-gui-transitions
description: "この Python repo の PySide6 GUI を Windows の通常描画で起動し、タスク固有の一時シナリオから任意の画面状態へ遷移して PNG を取得、目視確認する skill。GUI の見た目、レイアウト、ダイアログ遷移を画像で確認するときに使う。"
---

# GUI 遷移の画像確認

製品へ撮影機能を追加せず、実際の Qt Widget と一時シナリオを使って画面状態を PNG にする。

## Workflow

1. 対象画面に最も近い `tests/integration/ui` のテストを探し、実 Widget の組み立て方と操作経路を確認する。
2. `tmp/gui-audit/<task>/scenario.py` に `run(capture)` を定義する。実 runtime、Bluetooth、入力捕捉は起動せず、既存テスト相当のメモリー内 fake を使う。
3. ユーザー操作の遷移を確認する場合は QAction や Widget の公開操作を使う。単独画面のレイアウト確認だけなら対象 Widget を直接生成してよい。
4. Windows の通常 Qt platform で撮影スクリプトを実行する。
5. 生成された PNG を `view_image` で開き、画面ごとに確認する。
6. 実際に見えた事実、画像のパス、未確認の状態を分けて報告する。

```powershell
uv run python .agents/skills/inspect-gui-transitions/scripts/capture_gui.py `
  --scenario tmp/gui-audit/<task>/scenario.py `
  --output tmp/gui-audit/<task>
```

## Scenario contract

シナリオは次の形にする。

```python
from demi.app import WindowSpec
from demi.ui.main_window import MainWindow


def run(capture) -> None:
    window = MainWindow(WindowSpec(width=960, height=640, maximized=False))
    capture.frame("main", window)
```

`capture` が提供する操作は次の3つだけとする。

- `capture.application`: process-wide `QApplication`。
- `capture.settle()`: Qt の保留イベントを1巡処理する。
- `capture.frame(name, widget)`: Widget を表示し、イベント反映後に連番 PNG を保存する。

操作後に生成された Widget を取得する必要がある場合は、`capture.settle()` の後で取得する。たとえば toolbar action を発火した後に `window.active_settings_dialog` を確認し、その Widget を `capture.frame()` へ渡す。

## Guardrails

- シナリオと画像は git 管理外の `tmp/gui-audit` に置く。既存 PNG がある出力先は再利用しない。
- 画像による合否を自動判定しない。基準画像、pixel diff、動画、OCR、座標ベースの汎用操作は追加しない。
- デスクトップ全体を撮影しない。PNG は `QWidget.grab()` が返す Qt Widget の描画領域だけを含む。
- `offscreen` へ暗黙に切り替えない。Windows の通常描画を使えない場合は未実行として報告する。
- 撮影のために production source や恒久テストへ一時処理を残さない。
