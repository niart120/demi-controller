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
7. create Qt application, main window, and UI
8. schedule 8ms input evaluation
9. render IDLE state
10. optionally request adapter discovery
11. optionally reconnect saved bond
12. `QApplication.exec()`
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

主スレッドは `ControllerFrame` としてこの状態を生成し、接続ワーカーは完全な `InputState` へ
変換して `send()` がBumbleの送信キューへ受理されるまで待つ。rest送信成功後は
`close(neutral=False)`、送信失敗時だけ `close(neutral=True)` を最終フォールバックにする。

## 4. マウス捕捉開始

前提:

- `AppState == IDLE`
- モーダルなし
- ウィンドウがフォーカス中
- ワーカーが停止処理中ではない

シーケンス:

```text
1. PhysicalInputState.clear_mouse()
2. increment capture_epoch
3. PointerCapturePort.set_pointer_capture(True)
4. AppState = CAPTURED
5. publish ControllerFrame(capture_active=True, pointer_capture_active=True)
6. update toolbar and status
```

排他マウス設定に失敗した場合は `IDLE` のままとし、入力を送らない。

## 5. マウス捕捉終了と全入力中立化

契機:

- ツールバー
- F4
- Ctrl+C
- フォーカス喪失
- 設定モーダル
- 切断
- 停止監視
- 終了

シーケンス:

```text
1. AppState = IDLE
2. increment capture_epoch
3. PointerCapturePort.release(), best effort
4. PhysicalInputState.clear_mouse()
5. create ControllerFrame(capture_active=True, pointer_capture_active=False)
6. keyboard bindingとkeyboard由来poseを維持する
7. update ControllerPreviewWidget immediately
```

フォーカス喪失、設定モーダル、停止監視、終了ではmouseだけでなくkeyboardとposeも消去し、`capture_active=False`の安全ニュートラルを発行する。

## 6. 接続

### 6.1 保存済みボンド

```text
UI Connect
  -> validate adapter and slot
  -> state CONNECTING
  -> worker constructs DirectProController(profile_path=...)
  -> reconnect without pairing
  -> send physical rest state and await enqueue acceptance
  -> state CONNECTED
```

失敗時:

```text
send physical rest state, best effort
close(neutral=True) only if rest send failed
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
  -> if the slot is unused:
       DirectProController.create_profile(local_address=None)
       receive the paired controller without reopening it
  -> else:
       DirectProController(profile_path=...)
       connect(allow_pairing=True)
  -> send physical rest state and await enqueue acceptance
  -> state CONNECTED
```

取消やタイムアウト時も、swbtプロファイルは再試行用に残る。`create_profile()`は既存パスを
上書きしない。swbt 0.4のkey-store JSONは互換でないため、利用者は未使用スロットを選ぶか、
旧ファイルを明示削除してから再ペアリングする。

## 7. 切断

ユーザー切断:

```text
1. leave CAPTURED if needed
2. stop accepting non-neutral frames
3. state DISCONNECTING
4. await send_rest_state()
5. close(neutral=False), or close(neutral=True) only if rest send failed
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

Linux環境で排他マウス中のOSショートカットが制約される場合も、F4とツールバーによる解除を維持する。

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
send physical rest state and await completion
disconnect
destroy DirectProController
construct with new ControllerColors
reconnect saved bond
send physical rest state and await completion
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

ワーカーがニュートラル化した後に遅延フレームが届いても、`capture_epoch` が一致しなければ破棄する。これにより、終了済み捕捉セッションの遅延フレームを再生しない。

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
7. ControllerRuntime.close() marks shutdown started and signals the worker outside the command queue
8. worker cancels and collects the active adapter operation
9. worker apply physical rest state, best effort
10. worker neutral fallback if needed
11. worker close controller
12. emit RuntimeStopped and stop asyncio loop
13. join non-daemon worker thread
14. save window/settings if valid
15. close Qt main window
16. AppState = STOPPED
```

ワーカースレッドの終了待ちは上限を持つ。上限超過時はエラーを記録し、デーモンスレッドへ放置せず、可能な範囲でイベントループ停止を要求する。

## 13. 未処理例外

主スレッド:

- 例外フックでログ
- 捕捉解除
- ニュートラルフレーム
- `ControllerRuntime.close()`
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
- フォーカス喪失とF4の同時発生
- 停止監視後の遅延フレーム破棄
- 色再接続中の接続失敗
- 初回起動でアダプターなし
