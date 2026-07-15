# Windows 排他マウス 仕様書

## 1. 概要

### 1.1 目的

Windows でDemiが前面かつ入力捕捉中である間、Demiの外側にあるwindowへ物理マウスの移動、ボタン、ホイール操作を配送しない。Demiはマウスボタン割り当てを従来どおりcontroller入力へ変換し、`F12`、focus loss、dialog表示、終了では必ず抑止を解除する。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user request | pygletの排他マウスと同じく、Demiにfocusがある間は他windowへmouse入力を送らない | ユーザー要望、2026-07-16 |
| manual observation | 外部windowをclickするとcaptureは安全に解除されるが、click自体は外部applicationへ届く | `spec/dev-journal.md` |
| input requirement | 明示開始、F12解除、focus loss解除を維持する | `spec/initial/requirements.md` FR-008 |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| user | Demiを前面にしてcaptureを開始し、外部window上でmouseを動かす・clickする・scrollする | 外部windowはmouse入力を受けず、Demiはcaptureを継続する | Windows限定 |
| user | capture中に割当済みmouse buttonを押下・解放する | 外部windowへ漏らさずcontroller入力だけが変化する | callbackでQtやBluetooth I/Oをしない |
| user | F12、Alt+Tab、dialog、終了を行う | mouse抑止を解除し、入力をneutralizeする | 自動再captureしない |

## 2. 対象範囲

- `WH_MOUSE_LL` をcapture lifecycleへ結び付けるWindows platform backend。
- move、button down/up/double-click、vertical/horizontal wheelの抑止。
- button down/upを`PhysicalInputState`へ反映する入力callback。
- `MainWindow` のpointer capture開始・解除・失敗時rollback。
- source-level unit / integration testとWindows手動受入手順。

## 3. 対象外

- macOS / Linuxのpointer lock実装。
- keyboardのglobal hook、`BlockInput`、UAC secure desktopへの入力抑止。
- capture解除中のDemi toolbar操作をmouseで可能にするUI変更。
- 複数mouse deviceの個別識別。

## 4. 関連 docs

- `spec/initial/requirements.md`
- `spec/initial/ui.md`
- `spec/ui-redesign/RELATIVE_MOUSE_INPUT.md`
- `spec/dev-journal.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| capture開始 | Windows、Demi前面、IDLE | low-level mouse hookを登録してからcaptureをactiveにする | 登録失敗時はcursorとmouse grabを戻し、capture開始は失敗する |
| active mouse message | capture中のmove/button/wheel | target windowへ配送せず、buttonのみstateへ反映する | hook callbackは短時間で返す |
| capture解除 | F12、focus loss、dialog、shutdown | hookを無効化し、登録解除を試み、stateをclearする | unregister失敗時もcallbackはpass-throughへ戻す |
| capture外 message | IDLE、SUSPENDED、CONFIGURING | hookは入力を抑止せず、button stateを変更しない | 外部applicationの通常操作を壊さない |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| green | capture中のlow-level mouse move、button、wheelは外部windowへの配送を抑止する | new | unit | fake registrarでcallbackの戻り値を確認する |
| green | capture中のbutton down/upは外部へ漏らさず物理入力stateを更新する | regression | unit | LEFT / RIGHT / MIDDLE / BUTTON_4 / BUTTON_5を確認する |
| green | hook登録失敗はpointer captureをrollbackし、active stateにしない | edge | integration | `CaptureCoordinator`の既存failure契約を使う |
| green | F12、focus loss、dialog、shutdownはhookを解除してneutralizeする | regression | integration | MainWindowのcapture lifecycleを確認する |
| green | F12で解除したcapture状態をtoolbarが直ちに表示する | regression | integration | QtInputAdapterからrouterのrefreshを要求する |
| green | Windows実displayで外部windowを背面に置き、move/click/wheelが到達しない | manual | hardware | ユーザーが2026-07-16に期待どおりの動作を確認。管理者権限windowとsecure desktopは対象外 |
| green | Windows実displayでF12解除後にtoolbarが入力開始へ戻る | manual | hardware | ユーザーが2026-07-16に確認 |

## 7. 設計メモ

`QWidget.grabMouse()` / Win32 `SetCapture` は別threadのwindow clickを抑止できない。mouseの配送を止める責務は`demi.platform`の`WH_MOUSE_LL` backendへ置く。Raw Inputは未加速relative motionの取得に使い続け、low-level hookは配送抑止とbutton state更新だけを担当する。

hook callbackはGUI threadのmessage loopで実行される。callback内ではcapture activeの確認、button callback、抑止判定だけを行い、Qt API、設定保存、controller runtimeを呼ばない。callbackの例外はpass-throughにして、入力が恒久的に塞がる状態を作らない。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/platform/windows_mouse_hook.py` | new | low-level hookの登録、解除、抑止、button callback |
| `src/demi/ui/main_window.py` | modify | hook lifecycleとpointer captureのrollback |
| `tests/unit/platform/test_windows_mouse_hook.py` | new | hook decisionとbutton stateのunit test |
| `tests/integration/ui/test_qt_input_capture.py` | modify | MainWindow capture lifecycleのintegration test |
| `spec/initial/requirements.md` | modify | Windows排他mouseの受入条件 |
| `spec/ui-redesign/RELATIVE_MOUSE_INPUT.md` | modify | Raw Inputとの責務分離 |
| `spec/dev-journal.md` | modify | 未決定観測をunit_023へ昇格 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/unit/platform/test_windows_mouse_hook.py -q -p no:cacheprovider` | passed | 2 passed。move、button、wheelの抑止とbutton source更新を確認 |
| `$env:QT_QPA_PLATFORM='offscreen'; uv run pytest tests/integration/ui/test_qt_input_capture.py -q -p no:cacheprovider` | passed | 5 passed。F12、focus loss、dialog、shutdown、登録失敗時rollbackを確認 |
| `$env:QT_QPA_PLATFORM='offscreen'; uv run pytest tests/integration/ui/test_qt_runtime_events.py::test_f12_capture_release_refreshes_the_bound_toolbar -q -p no:cacheprovider` | passed | F12後にIDLE、入力開始、uncheckedを確認 |
| `uv sync --dev` / `uv lock --check` / `uv run ruff format --check .` / `uv run ruff check .` / `uv run ty check --no-progress` | passed | 129 files、全静的検査が通過 |
| `uv run pytest tests/unit -q -p no:cacheprovider` / `$env:QT_QPA_PLATFORM='offscreen'; uv run pytest tests/integration -q -p no:cacheprovider` | passed | unit 199 passed、integration 71 passed |
| `uv build` / `git diff --check` | passed | sdistとwheelを生成、whitespace errorなし |
| Windows実display手動受入（外部windowへの配送抑止） | passed | ユーザーが2026-07-16に期待どおりの動作を確認 |
| Windows実display手動受入（F12後のtoolbar） | passed | ユーザーが2026-07-16に確認 |

## 10. 先送り事項

- 管理者権限window、secure desktop、他OSで同じ保証を提供する設計は、Windows手動受入の結果を起点に別work unitとする。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を更新した
- [x] 検証結果または未実行理由を記録した
- [x] package / release / public API に触れないことを確認した
