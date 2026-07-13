# 相対マウス入力方式の選定

## 1. 目的

PySide6 UI で画面端に制限されないマウス移動量を取得し、OS のカーソル加速を含む値と
未補正の値を区別して `YawPitchModel` へ渡す方式を定める。

検討対象は `QAbstractNativeEventFilter` を入口にした OS 固有入力と GLFW の raw mouse
motion である。

## 2. 結論

| 項目 | 判断 |
|---|---|
| GLFW | 採用しない |
| `QAbstractNativeEventFilter` | OS 固有メッセージを受ける入口として採用する |
| Windows | Win32 Raw Input を第一実装とする |
| macOS | Qt 通常イベントを暫定実装とし、`NSEvent` の差分値を別途評価する |
| Linux/X11 | Qt 通常イベントを暫定実装とし、XInput2 raw motion を後続候補にする |
| Linux/Wayland | Qt/QPA が提供する pointer lock と relative motion の実測を先行する |
| framework 境界 | raw / accelerated / unavailable を区別する `RelativePointerBackend` を設ける |

`QAbstractNativeEventFilter` は raw input backend そのものではない。Qt の native event
dispatcher に届いた `MSG`、XCB event、`NSEvent` へ到達するための hook である。raw input の
登録、構造体の読出し、capture lifecycle、delta の蓄積は OS 別 backend が実装する。

## 3. 必要な振る舞い

- capture 中はカーソルが画面端へ到達しても相対移動を継続できる。
- 1評価周期内の複数イベントを加算し、`InputPublisher` が1回だけ消費する。
- focus loss、F12、dialog open、shutdown で入力受付を停止し、未消費 delta を消去する。
- OS 補正前の値か、補正後の相対値かを backend が明示する。
- raw input が利用不能なとき、補正後の値を raw として扱わない。
- UI の button、text field、dialog 操作へ必要な通常の Qt mouse event を壊さない。
- worker thread ではなく GUI 主スレッドで native event を受ける。
- device 固有値、native pointer、Qt event object を domain 層へ渡さない。

## 4. `QAbstractNativeEventFilter` の評価

### 4.1 利点

- Qt application の native event loop 内で処理できる。
- Windows では `windows_generic_MSG` / `windows_dispatcher_MSG` として `MSG` を受け取れる。
- X11 では `xcb_generic_event_t`、macOS では `mac_generic_NSEvent` を受け取れる。
- Qt main window の native handle を raw input の受信先にできる。
- GLFW の別 window と event loop を追加しなくてよい。
- filter が `False` を返せば、通常の Qt event への変換を継続できる。

### 4.2 制約

- OS と実行時の QPA platform plugin ごとに event type と構造体が異なる。
- Windows Raw Input は `QAbstractNativeEventFilter` の設置だけでは届かない。
- PySide6 から native pointer を読む処理は `ctypes` 等を使う低水準境界になる。
- Qt 公式文書が具体例を示すのは Windows、X11、macOS であり、Wayland の raw motion を
  この API だけで得られるとは確認できない。
- native event filter は application 全体のイベントを受けるため、capture state と対象 window を
  必ず確認する。

Qt は可搬性を最大化する場合、通常の `QEvent` と `installEventFilter()` を先に使うよう案内している。
Project_Demi では通常の button、key、focus event はその方針に従い、未補正の相対マウス値だけを
native event filter へ分離する。

## 5. GLFW の評価

### 5.1 利点

- `GLFW_CURSOR_DISABLED` が cursor の非表示、固定、再中心化、仮想位置をまとめて扱う。
- 対応環境では `GLFW_RAW_MOUSE_MOTION` により未加速の移動量を取得できる。
- `glfwRawMouseMotionSupported()` で実行時に対応可否を確認できる。
- zlib/libpng license で、ライセンス上の導入条件は比較的軽い。

### 5.2 不採用理由

GLFW の入力 mode と callback は `GLFWwindow` に対して設定する。Qt が生成した
`QMainWindow` は `GLFWwindow` ではなく、GLFW の raw mouse motion をそのまま Qt window に
取り付ける API は公式仕様にない。

GLFW window を別に作る方式には次の問題がある。

- 入力 focus が Qt main window と GLFW window に分かれる。
- raw mouse motion は cursor を無効化した GLFW window でだけ提供される。
- GLFW の初期化、window、cursor、event processing は main thread 制約を持つ。
- Qt と GLFW の2つの event loop を同じ main thread で協調させる処理が増える。
- hidden GLFW window は focus を持たないため、Qt window の capture backend として成立しない。
- visible GLFW window を入力用にすると、Qt Widgets へ移行する目的と矛盾する。

GLFW は単独で window と描画を所有するアプリケーションには適するが、Qt Widgets の補助入力
ライブラリとしては所有権と focus の不一致が大きい。GLFW の license は不採用理由ではない。

## 6. 目標境界

```text
QtInputAdapter
  ├── key / button / focus
  │     └── QEvent
  └── relative motion
        └── RelativePointerBackend
              ├── WindowsRawInputBackend
              │     └── QAbstractNativeEventFilter + WM_INPUT
              ├── QtRelativePointerBackend
              │     └── Qt mouse event、補正後の可能性を明示
              └── future OS backend
                    ├── macOS native motion
                    ├── XInput2 raw motion
                    └── Wayland relative pointer
```

application 層には次のような framework 非依存値だけを渡す。

```text
RelativeMotion
  dx: float
  dy: float
  quality: RAW_UNACCELERATED | RELATIVE_ACCELERATED
```

`PhysicalInputState` は1評価周期内の `dx` と `dy` を加算する。異なる `quality` の値を同じ
capture epoch 内で混在させない。backend の切替時は capture を停止し、delta と
`YawPitchModel` を reset してから新しい epoch を開始する。

## 7. Windows Raw Input

### 7.1 ownership

- `WindowsRawInputBackend` は application 内で1個だけ生成する。
- Qt main window の native handle が確定してから mouse device を登録する。
- capture 開始時に foreground input として登録する。
- `RIDEV_INPUTSINK` は使わず、非 foreground window の入力を取得しない。
- `RIDEV_NOLEGACY` は使わず、Qt の通常 mouse event を抑止しない。
- capture 終了時に `RIDEV_REMOVE` で登録解除し、その際の target handle は null とする。

Windows は1 processにつき raw input device class の登録先 window を1つに制限する。このため、
dialog や preview widget が個別に登録してはならない。

### 7.2 event processing

1. `RegisterRawInputDevices` で mouse usage を Qt main window へ登録する。
2. native event filter で `windows_generic_MSG` の `WM_INPUT` を検出する。
3. `GetRawInputData` で `RAWINPUT` を読む。
4. relative mouse event の `lLastX` / `lLastY` を delta として蓄積する。
5. native message を Qt から奪わず、通常処理へ戻す。
6. 8ミリ秒 timer が蓄積値を1回だけ消費する。

1000 Hz 以上の mouse では、event loop の遅延時に複数イベントが滞留する可能性がある。
最初は `GetRawInputData` で各 `WM_INPUT` を処理し、計測で欠落または遅延が確認された場合に
`GetRawInputBuffer` を検討する。

### 7.3 failure behavior

- 登録失敗時は capture を開始せず、OS error code を秘密情報を含まない分類へ変換する。
- 読出し失敗時はその event を捨て、連続失敗なら capture を解除する。
- focus loss 後に届いた event は epoch を確認して捨てる。
- absolute mouse flag の入力を relative delta として解釈しない。
- mouse device ごとの値を統合する現行仕様とし、device 分離は後続候補にする。

## 8. macOS と Linux

### 8.1 macOS

Qt native event filter は `NSEvent` を受け取れる。`NSEvent.deltaX` / `deltaY` は移動差分を持つが、
Project_Demi が必要とする「OS 加速前」の値かは公式資料から確認できていない。最初の実装では
Qt backend として扱い、raw と表示しない。実機計測後に native backend へ昇格させる。

### 8.2 Linux/X11

GLFW は XInput2 を使って raw motion を取得するが、Project_Demi は GLFW を採用しない。
必要になった場合は、Qt の X11 native event 境界から XInput2 event を読む専用 backend を設ける。
XInput2 がない環境では補正後の相対値として扱う。

### 8.3 Linux/Wayland

Wayland の relative pointer protocol は画面端に制限されない差分と、利用可能な場合の未加速差分を
定義している。pointer constraints protocol は pointer lock と relative event の組合せを定義する。
ただし Qt が利用中の compositor と QPA plugin でこれらをどう公開するかは未検証である。

Wayland native protocol を PySide6 から直接所有する実装を先に作らず、Qt の pointer capture で
得られるイベントと capability を実測する。未加速値を確認できない場合は
`RELATIVE_ACCELERATED` として扱う。

## 9. UI 表示と設定

- status bar に `Raw`、`OS補正あり`、`利用不可` のいずれかを文字で示す。
- Windows で Raw Input の登録に失敗した場合、capture action を失敗として戻す。
- macOS / Linux の補正後 backend を raw input と表記しない。
- 感度設定は backend quality ごとに自動変換せず、ユーザーが設定した倍率を使う。
- device DPI が異なれば raw count あたりの物理移動量も異なるため、raw を絶対的な物理単位として
  扱わない。

## 10. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| todo | native event filterは対象外messageを消費せずQt処理へ返す | new | unit | Windows adapter |
| todo | capture開始はmain windowをmouse raw inputの唯一の受信先として登録する | new | unit | Win32 API fake |
| todo | `WM_INPUT` のrelative deltaは1評価周期内で加算され1回だけ消費される | new | unit | Win32構造体fixture |
| todo | absolute mouse inputはrelative deltaへ加算されない | edge | unit | Windows adapter |
| todo | focus lossとF12はraw input登録を解除し未消費deltaを消去する | regression | integration | capture epochも確認 |
| todo | capture外または古いepochのnative eventはcontroller frameへ反映されない | edge | integration | stale input防止 |
| todo | raw input登録失敗はcaptureを開始せず安全な警告を表示する | edge | integration | tracebackを表示しない |
| todo | fallback backendは補正後の値を`RAW_UNACCELERATED`と報告しない | new | unit | capability契約 |
| todo | Qtのbuttonとdialog操作はraw input登録中も通常どおり動作する | regression | integration | legacy eventを抑止しない |
| todo | Windows実機で画面端、1000 Hz mouse、focus loss、F12解除を確認する | new | manual | 数値と観測条件を記録 |
| deferred | macOSで通常eventと`NSEvent`差分の加速有無を比較する | characterization | manual | 対象環境が必要 |
| deferred | X11とWaylandでpointer lock、未加速delta、画面端を比較する | characterization | manual | compositorを記録 |

## 11. 未検証事項

- PySide6 の `QAbstractNativeEventFilter` から native pointer を安全に読む具体的な `ctypes` 定義
- Qt が foreground `WM_INPUT` を通常処理へ戻した後の cleanup 経路
- 1000 Hz 以上で `GetRawInputData` 単位の処理が十分か
- macOS の移動差分に含まれる加速と pointer association の挙動
- Qt Wayland plugin が relative pointer / pointer constraints を利用する条件
- raw count と既存感度初期値の体感差

## 12. 外部仕様の参照先

- [QAbstractNativeEventFilter](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QAbstractNativeEventFilter.html)
- [QAbstractEventDispatcher.installNativeEventFilter](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QAbstractEventDispatcher.html)
- [Windows Raw Input overview](https://learn.microsoft.com/en-us/windows/win32/inputdev/about-raw-input)
- [RegisterRawInputDevices](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerrawinputdevices)
- [WM_INPUT](https://learn.microsoft.com/en-us/windows/win32/inputdev/wm-input)
- [GLFW input guide](https://www.glfw.org/docs/latest/input)
- [GLFW thread safety](https://www.glfw.org/docs/latest/intro.html#thread_safety)
- [GLFW license](https://www.glfw.org/license.html)
- [Wayland relative pointer protocol](https://wayland.app/protocols/relative-pointer-unstable-v1)
- [Wayland pointer constraints protocol](https://wayland.app/protocols/pointer-constraints-unstable-v1)
