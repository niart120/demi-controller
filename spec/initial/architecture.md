# アーキテクチャ

## 1. 依存方向

依存方向は外側から内側へ限定する。

```text
demi.ui ───────────────┐
demi.input ────────────┼──► demi.application ───► demi.domain
demi.controller ───────┘             │
      │                               ▼
      └── swbt adapter          ports / protocols
```

実際のimport規則は次のとおり。

```text
demi.domain
  imports: Python標準ライブラリのみ

demi.application
  imports: demi.domain, Python標準ライブラリ

demi.input
  imports: demi.domain, demi.application
  qt_adapter.pyだけがPySide6入力型をimport可能。OS固有APIはdemi.platform配下へ隔離する

demi.controller
  imports: demi.domain, demi.application
  swbt_adapter.pyのみswbtをimport可能

demi.ui
  imports: demi.domain, demi.application
  PySide6 / Qt Widgetsのwidget型はui配下だけで扱う

demi.config
  imports: demi.domain, Python標準ライブラリ, platformdirs, tomli_w
```

`demi.domain` から外部ライブラリへ向かう依存は禁止する。

## 2. ソース構成

```text
src/
└── demi/
    ├── __init__.py
    ├── __main__.py
    ├── app.py
    ├── application/
    │   ├── coordinator.py
    │   ├── commands.py
    │   ├── events.py
    │   ├── presenter.py
    │   └── ports.py
    ├── domain/
    │   ├── controller.py
    │   ├── physical_input.py
    │   ├── mapping.py
    │   ├── connection.py
    │   ├── settings.py
    │   └── errors.py
    ├── input/
    │   ├── backend.py
    │   ├── qt_adapter.py
    │   ├── relative_pointer.py
    │   ├── state_tracker.py
    │   ├── mapper.py
    │   ├── yaw_pitch_model.py
    │   └── publisher.py
    ├── platform/
    │   └── windows_raw_input.py
    ├── controller/
    │   ├── runtime.py
    │   ├── mailbox.py
    │   ├── swbt_adapter.py
    │   ├── conversion.py
    │   └── diagnostics.py
    ├── config/
    │   ├── paths.py
    │   ├── repository.py
    │   ├── codec.py
    │   ├── validation.py
    │   └── migrations.py
    ├── ui/
    │   ├── application.py
    │   ├── main_window.py
    │   ├── controller_preview.py
    │   ├── event_bridge.py
    │   ├── toolbar.py
    │   ├── status_bar.py
    │   └── dialogs/
    │       ├── mapping.py
    │       ├── connection.py
    │       └── colors.py
    └── assets/
        ├── fonts/
        ├── icons/
        └── controller/
```

フォントファイルを同梱する場合はライセンスを明示する。初期実装ではOS標準フォントを優先し、配布物を増やさない。

試験構成:

```text
tests/
├── unit/
│   ├── domain/
│   ├── input/
│   ├── config/
│   └── application/
├── integration/
│   ├── controller/
│   ├── ui/
│   └── lifecycle/
├── hardware/
│   └── test_pro_controller.py
├── fixtures/
│   ├── settings/
│   └── mappings/
└── fakes/
    ├── controller_port.py
    ├── clock.py
    └── input_backend.py
```

## 3. 主要なドメイン型

外部ライブラリ型を使わず、次の値を定義する。

```python
from dataclasses import dataclass
from enum import Enum, auto


class LogicalButton(Enum):
    A = auto()
    B = auto()
    X = auto()
    Y = auto()
    L = auto()
    R = auto()
    ZL = auto()
    ZR = auto()
    PLUS = auto()
    MINUS = auto()
    HOME = auto()
    CAPTURE = auto()
    LEFT_STICK = auto()
    RIGHT_STICK = auto()
    DPAD_UP = auto()
    DPAD_DOWN = auto()
    DPAD_LEFT = auto()
    DPAD_RIGHT = auto()


@dataclass(frozen=True, slots=True)
class StickVector:
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class GyroRate:
    x_radians_per_second: float
    y_radians_per_second: float
    z_radians_per_second: float


@dataclass(frozen=True, slots=True)
class AccelG:
    x_g: float
    y_g: float
    z_g: float


@dataclass(frozen=True, slots=True)
class ControllerFrame:
    sequence: int
    capture_epoch: int
    monotonic_ns: int
    buttons: frozenset[LogicalButton]
    left_stick: StickVector
    right_stick: StickVector
    gyro_rate: GyroRate
    accel_g: AccelG
    capture_active: bool
```

`StickVector` は `-1.0..1.0` をドメイン範囲とし、境界で `swbt.Stick.normalized()` へ変換する。`GyroRate` は有限なラジアン毎秒、`AccelG` は有限なG単位の加速度を保持し、swbtのraw表現をドメイン層へ持ち込まない。`AccelG` は下向き重力ベクトルではなく、加速度センサーが静止時に報告する比力を表す。

`capture_active` と `capture_epoch` はコントローラー入力ではなく、ワーカーの停止監視と遅延フレーム破棄に使う。

## 4. アプリケーションポート

### 4.1 ControllerPort

```python
from typing import Protocol


class ControllerPort(Protocol):
    def start(self) -> None: ...
    def post(self, command: "ControllerCommand") -> None: ...
    def offer_frame(self, frame: ControllerFrame) -> None: ...
    def close(self) -> None: ...
```

`post()` は接続、切断、列挙など順序を失ってはいけない操作に使う。`offer_frame()` は最新値優先で、未処理フレームを全件保持しない。

### 4.2 SettingsRepository

```python
class SettingsRepository(Protocol):
    def load(self) -> "LoadSettingsResult": ...
    def save(self, settings: "AppSettings") -> None: ...
```

読み込み結果は「正常」「初回」「移行済み」「破損から復旧」を区別する。

### 4.3 Clock

```python
class Clock(Protocol):
    def monotonic_ns(self) -> int: ...
```

入力停止監視や接続タイムアウトの試験で実時間待ちを避ける。

## 5. スレッド構成

### 5.1 主スレッド

主スレッドが所有するもの:

- `QApplication` と `QMainWindow`
- Qt Widgets部品と `ControllerPreviewWidget`
- Qt入力アダプター

- `PhysicalInputState`
- `InputMapper`
- `ControllerPreviewWidget`
- `ApplicationPresenter`

主スレッド以外からこれらを操作しない。

### 5.2 接続ワーカースレッド

ワーカースレッドが所有するもの:

- 専用 `asyncio` イベントループ
- `swbt.ProController`
- 接続・切断タスク
- 入力状態の適用
- 接続停止監視
- swbt診断値の抽出

`swbt.ProController` はワーカースレッド内で生成し、同じスレッド内で閉じる。別スレッドへ参照を返さない。

### 5.3 主スレッドからワーカー

順序付きコマンドは `asyncio.Queue` へ渡す。

```text
main thread
  ControllerRuntime.post(command)
    └── loop.call_soon_threadsafe(command_queue.put_nowait, command)
```

終了要求は順序付きコマンドの後ろへ積まない。`ControllerRuntime.close()` が停止開始を同期的に確定し、`loop.call_soon_threadsafe(shutdown_event.set)` でワーカーを起こす。ワーカーは進行中の adapter operation task を cancel して回収してから、rest、disconnect、close へ進む。停止開始後の `post()` は `RuntimeError`、`offer_frame()` は `False` で拒否する。

入力フレームはロック保護した1スロットへ置く。

```text
latest_frame = newest frame only
generation   = incrementing integer
frame_event  = asyncio.Event
```

新しいフレームで古い未処理フレームを置換する。キューを無制限に積むと、遅延後に古い入力を再生してしまうためである。

### 5.4 ワーカーから主スレッド

ワーカーは `RuntimeEvent` を生成し、Qtのqueued signalまたはスレッドセーフなapplication portへ投稿する。UIは `event_bridge.py` でGUIスレッドへ受け渡す。

```text
ControllerRuntimeEvent
  ├── AdapterListUpdated
  ├── ConnectionStateChanged
  ├── ControllerStatusUpdated
  ├── WatchdogNeutralized
  └── ControllerFaulted
```

ワーカーからUI部品を直接呼び出さない。

## 6. 実行周期

| 処理 | 周期・契機 |
|---|---|
| OSイベント処理 | Qt event loop |
| 入力状態評価 | 8ミリ秒 |
| 画面描画 | 最大60Hz |
| 接続状態表示 | 変化時 |
| 診断スナップショット | 接続中1秒ごと |
| 入力停止監視 | 50ミリ秒確認、250ミリ秒閾値 |
| 設定保存 | 確定操作時。連続色編集は300ミリ秒遅延保存 |

入力評価はQtのタイマーを使い、GUIイベントの処理を阻害しない。独自のevent loopを実装しない。

## 7. 入力フロー

```text
QKeyEvent / QMouseEvent / focus event ──► QtInputAdapter ─────────┐
OS relative pointer event ─────────────► RelativePointerBackend ─┤
           │
           ▼
PhysicalInputState
  held_keys
  held_mouse_buttons
  accumulated_dx/dy
           │ 8ms target
           ▼
InputMapper + YawPitchModel
  GyroRate + AccelG
           │
           ├── ControllerFrame ──► ControllerPreviewWidget
           │
           └── ControllerPort.offer_frame()
```

イベントコールバックは状態更新だけを行う。Bluetooth I/O、設定保存、重い計算を行わない。

## 8. 接続フロー

```text
UI command
  │
  ▼
ApplicationCoordinator
  │ validates transition
  ▼
ControllerRuntime.post()
  │
  ▼
SwbtAdapter
  │
  ├── list_adapters()
  ├── ProController(...)
  ├── connect()/reconnect()
  ├── apply(InputState)
  ├── apply(rest InputState)
  └── close()
```

`swbt` の例外は `ControllerFault` へ変換する。UIは例外クラス名に依存しない。

## 9. エラー境界

### 回復可能

- アダプター未検出
- 接続タイムアウト
- 保存済みボンドによる再接続失敗
- 設定値不正
- フォーカス喪失
- 一時的なUI停止監視

UIへ通知し、ニュートラルを保証して操作可能状態へ戻す。

### 致命的

- OpenGLコンテキスト生成不能
- ワーカースレッド起動不能
- 設定保存先を確保できず、代替も使えない
- 内部不変条件違反

可能な範囲でニュートラルと切断を実行し、ログを残して終了する。

## 10. 循環依存防止

- UIイベントは `application.events` で定義する。
- 接続コマンドは `application.commands` で定義する。
- ドメイン型をUI用に拡張しない。
- UI表示用文字列はPresenterで生成する。
- `app.py` だけが具象実装を組み立てる。
