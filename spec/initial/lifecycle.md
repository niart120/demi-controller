# ライフサイクル設計

## 1. アプリケーション状態

```python
class AppState(Enum):
    STARTING = auto()
    IDLE = auto()
    CAPTURED = auto()
    CONFIGURING = auto()
    SUSPENDED = auto()
    SHUTTING_DOWN = auto()
    STOPPED = auto()
```

状態遷移は `ApplicationCoordinator` だけが行う。UI部品が個別に状態を変更しない。

## 2. 接続状態

```python
class ConnectionState(Enum):
    STOPPED = auto()
    STARTING = auto()
    READY = auto()
    DISCOVERING = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    DISCONNECTING = auto()
    ERROR = auto()
    STOPPING = auto()
```

主要遷移:

```text
STOPPED -> STARTING -> READY
READY -> DISCOVERING -> READY
READY -> CONNECTING -> CONNECTED
CONNECTING -> ERROR -> READY
CONNECTED -> DISCONNECTING -> READY
CONNECTED -> ERROR -> READY
READY -> STOPPING -> STOPPED
ERROR -> STOPPING -> STOPPED
```

接続状態と入力捕捉状態は直交する。未接続でもプレビュー用に `CAPTURED` へ入れるが、実機送信は行わない。

## 3. 起動シーケンス

```text
1. logging bootstrap
2. SettingsRepository.load()
3. validate/migrate settings
4. create domain services
5. create ControllerRuntime
6. start worker thread
7. create pyglet window and UI
8. schedule 8ms input evaluation
9. render IDLE state
10. optionally request adapter discovery
11. optionally reconnect saved bond
12. pyglet.app.run()
```

`reconnect_on_start=true` でも新規ペアリングは行わない。アダプター未検出や再接続失敗は起動失敗にせず、UIを操作可能にする。

## 3.1 ニュートラル状態の定義

この文書でいうニュートラルは、単なる全rawゼロではなく、水平なPro Controllerが静止している状態を指す。

```text
buttons: none
sticks: centered
gyro: (0, 0, 0) rad/s
accel: (0, 0, +1) G
virtual pitch: 0 rad
```

主スレッドは `ControllerFrame` としてこの状態を生成し、接続ワーカーは完全な `InputState` へ変換して `apply()` する。swbt-pythonの `controller.neutral()` は通常経路ではなく、rest状態の送信に失敗した場合や終了時の最終フォールバックに限定する。

## 4. 入力捕捉開始

前提:

- `AppState == IDLE`
- モーダルなし
- ウィンドウがフォーカス中
- ワーカーが停止処理中ではない

シーケンス:

```text
1. PhysicalInputState.clear()
2. YawPitchModel.reset()
3. increment capture_epoch
4. window.set_exclusive_mouse(True)
5. AppState = CAPTURED
6. publish initial neutral ControllerFrame(capture_active=True)
7. update toolbar and border
```

排他マウス設定に失敗した場合は `IDLE` のままとし、入力を送らない。

## 5. 入力捕捉終了

契機:

- ツールバー
- F12
- Ctrl+C
- フォーカス喪失
- 設定モーダル
- 切断
- 停止監視
- 終了

シーケンス:

```text
1. AppState leaves CAPTURED
2. increment capture_epoch
3. window.set_exclusive_mouse(False), best effort
4. PhysicalInputState.clear()
5. YawPitchModel.reset()
6. create neutral ControllerFrame(capture_active=False)
7. ControllerPort.offer_frame(neutral)
8. update ControllerView immediately
9. show reason when not user initiated
```

## 6. 接続

### 6.1 保存済みボンド

```text
UI Connect
  -> validate adapter and slot
  -> state CONNECTING
  -> worker constructs ProController
  -> reconnect without pairing
  -> apply physical rest state
  -> state CONNECTED
```

失敗時:

```text
apply physical rest state, best effort
controller.neutral() only as final fallback
close controller
state ERROR
emit categorized error
return READY after UI acknowledgment
```

### 6.2 新規ペアリング

```text
open connection dialog
  -> user selects "new pairing"
  -> confirmation
  -> verify adapter
  -> state CONNECTING
  -> connect(allow_pairing=True)
  -> apply physical rest state
  -> state CONNECTED
```

取消やタイムアウト時に空または部分的なボンドが残る可能性は、swbt-pythonの契約と実機試験で確認する。Project_Demiは既存ボンドを上書きする前にバックアップ名を確保する。

## 7. 切断

ユーザー切断:

```text
1. leave CAPTURED if needed
2. stop accepting non-neutral frames
3. state DISCONNECTING
4. await apply_rest_state()
5. controller.neutral() only if rest apply failed
6. close controller
7. state READY
```

切断中に終了要求が来た場合、終了処理が切断タスクを引き継ぎ、同じコントローラーへ並行して `close()` を呼ばない。

## 8. フォーカス喪失

```text
on_deactivate
  -> leave CAPTURED
  -> exclusive mouse off
  -> clear physical state
  -> neutral frame
  -> AppState = SUSPENDED
```

復帰:

```text
on_activate
  -> AppState = IDLE
  -> no automatic recapture
```

Linux環境で排他マウス中のOSショートカットが制約される場合も、F12とツールバーによる解除を維持する。

## 9. 色変更と再接続

```text
save colors
  -> update UI model immediately
  -> settings atomic save
  -> mark controller_configuration_dirty
```

接続中に「再接続して反映」:

```text
leave CAPTURED
apply physical rest state
disconnect
destroy ProController
construct with new ControllerColors
reconnect saved bond
apply physical rest state
CONNECTED
remain IDLE
```

入力捕捉は自動再開しない。

## 10. 停止監視

ワーカーは最後の捕捉中フレーム受信時刻を持つ。

```text
if connected
and latest.capture_active
and now - last_frame_at >= 250 ms
and not already_tripped:
    apply_rest_state()
    emit WatchdogNeutralized
```

UIイベント受信時:

```text
leave CAPTURED
clear state
AppState = IDLE
show warning
```

ワーカーがニュートラル化した後に遅延フレームが届いても、`capture_epoch` が一致しなければ破棄する。これにより、前回捕捉セッションの遅延フレームを再生しない。

## 11. OSスリープとアダプター抜去

0.1.0ではOS固有のスリープ通知へ依存せず、接続例外を検出する。

- アダプター抜去: `CONNECTION_LOST`
- スリープ復帰後の接続不良: READYへ戻し、再接続をユーザーへ提示
- 自動無限再接続はしない
- 再接続回数を隠れて増やさない

将来、OSイベントを扱う場合は `demi.platform` へ隔離する。

## 12. 終了

通常終了:

```text
1. AppState = SHUTTING_DOWN
2. unschedule input publisher
3. disable UI commands
4. release exclusive mouse
5. clear physical input
6. offer neutral frame
7. post Shutdown
8. worker apply physical rest state, best effort
9. worker neutral fallback if needed
10. worker close controller
11. stop asyncio loop
12. join worker thread
13. save window/settings if valid
14. close pyglet window
15. AppState = STOPPED
```

ワーカースレッドの終了待ちは上限を持つ。上限超過時はエラーを記録し、デーモンスレッドへ放置せず、可能な範囲でイベントループ停止を要求する。

## 13. 未処理例外

主スレッド:

- 例外フックでログ
- 捕捉解除
- ニュートラルフレーム
- Shutdown
- 非ゼロ終了

ワーカー:

- 例外を `ControllerError(UNEXPECTED)` へ変換
- ニュートラルとcloseを最善努力
- `RuntimeStopped` を通知
- 主スレッドが終了方針を決める

`BaseException` を広く握り潰さない。`KeyboardInterrupt` と `SystemExit` は終了経路へ流す。

## 14. 状態遷移試験

- 二重接続要求を拒否
- 接続中の切断要求を順序化
- 切断中の終了
- 捕捉中の設定モーダル
- フォーカス喪失とF12の同時発生
- 停止監視後の遅延フレーム破棄
- 色再接続中の接続失敗
- 初回起動でアダプターなし
