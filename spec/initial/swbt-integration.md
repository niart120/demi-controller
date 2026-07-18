# swbt-python 統合設計

## 1. 対象契約

0.1.0は、issue #69の物理角速度APIとissue #70のG単位加速度APIを取り込んだswbt-python 0.2系を対象とする。正式リリース後に `pyproject.toml` の下限版をその版へ引き上げる。主に次の公開要素を使う。

```python
from swbt import (
    Button,
    ControllerColors,
    IMUFrame,
    InputState,
    ProController,
    Stick,
    list_adapters,
)
```

`swbt` の内部モジュール、非公開属性、HIDレポート構造へ依存しない。

Project_Demiが必要とする追加契約は次である。

```python
IMUFrame.gyro_rate(
    *,
    x_rad_s: float = 0.0,
    y_rad_s: float = 0.0,
    z_rad_s: float = 0.0,
) -> IMUFrame

imu.with_accel_g(
    *,
    x_g: float = 0.0,
    y_g: float = 0.0,
    z_g: float = 0.0,
) -> IMUFrame
```

検証・診断用の逆変換として `to_gyro_rate()` と `to_accel_g()` を利用できることを期待するが、通常送信経路は生成・差し替えAPIだけに依存する。呼び出し側から校正値を渡さず、swbt-pythonのコントローラープロファイルと仮想SPIが共有する固定校正を使用する。

## 2. 所有境界

`demi.controller.swbt_adapter.SwbtControllerAdapter` だけが上記型を扱う。アプリケーション層へ返すのはProject_Demi独自のイベントと値である。

```text
Project_Demi domain values
           │
           ▼
demi.controller.conversion
  canonical Pro Controller axes
           │
           ▼
swbt public values
           │
           ▼
SwbtControllerAdapter
```

### 2.1 IMU座標境界

ドメイン座標は +Xトリガー、+Y左、+Zボタン・スティック面外向きの右手系とする。0.1.0のPro Controllerではこの座標をそのままswbtへ渡す。

右Joy-Conのraw Y/ZはPro Controller・左Joy-Conと逆である。将来Joy-Conを対象へ加える場合、デバイス固有の軸反転はprofile-awareなアダプター境界で処理し、`RotationPoseModel` や `ControllerFrame` の意味を変更しない。

## 3. ライフサイクル

### 3.1 オープン

ワーカースレッド内で次を生成する。

```python
controller = ProController(
    adapter=adapter_id,
    key_store_path=bond_path,
    controller_colors=colors,
)
await controller.open()
```

実装時は公開されている非同期コンテキストまたは `open()/close()` 契約のうち、0.2系文書で推奨される方を使用する。どちらを選んでも、生成から破棄までを同一ワーカースレッドへ限定する。

### 3.2 接続

ユーザー操作を2経路に分ける。

#### 再接続

保存済みボンドが存在する場合:

```python
await controller.reconnect(timeout=timeout_seconds)
```

または0.2系の推奨APIに従い、ペアリングを許可しない `connect()` を使う。実装時に公開契約へ合わせ、アプリケーション側の `Reconnect` コマンド名は変えない。

#### 新規ペアリング

ユーザー確認後だけ:

```python
await controller.connect(
    timeout=timeout_seconds,
    allow_pairing=True,
)
```

アプリ起動時の自動再接続では `allow_pairing=True` を使わない。

### 3.3 接続直後

接続成功後、入力受付開始前に次を行う。

1. ボタン解放、スティック中央、ジャイロ0、加速度 `(0, 0, +1) G` のrest `InputState`を `apply()`
2. 接続状態を `CONNECTED` へ更新
3. UIへ接続イベントを通知
4. 最新フレームが捕捉中でなければrest状態を維持
5. ユーザーが明示的に捕捉を開始してから入力適用

### 3.4 切断

1. フレーム受付を停止
2. rest `InputState` の `apply()` を最善努力し、失敗時だけ `controller.neutral()` を最終フォールバックとして試す
3. コントローラーを閉じる
4. 内部参照を破棄
5. UIへ切断イベント
6. ボンドファイルは保持

例外が発生しても手順3以降へ進む。

## 4. アダプター列挙

`list_adapters()` はUI主スレッドではなくワーカーで呼ぶ。列挙結果を次の値へ変換する。

```python
@dataclass(frozen=True, slots=True)
class AdapterDescriptor:
    id: str
    display_name: str
    transport: str
    metadata: tuple[tuple[str, str], ...]
```

UIは `id` を設定へ保存し、表示名をユーザーへ示す。保存済みIDが見つからない場合は「未検出」とし、一覧先頭へ自動変更しない。

## 5. ControllerFrame変換

```python
BUTTON_MAP: dict[LogicalButton, Button] = {
    LogicalButton.A: Button.A,
    LogicalButton.B: Button.B,
    LogicalButton.X: Button.X,
    LogicalButton.Y: Button.Y,
    LogicalButton.L: Button.L,
    LogicalButton.R: Button.R,
    LogicalButton.ZL: Button.ZL,
    LogicalButton.ZR: Button.ZR,
    LogicalButton.PLUS: Button.PLUS,
    LogicalButton.MINUS: Button.MINUS,
    LogicalButton.HOME: Button.HOME,
    LogicalButton.CAPTURE: Button.CAPTURE,
    LogicalButton.LEFT_STICK: Button.LEFT_STICK,
    LogicalButton.RIGHT_STICK: Button.RIGHT_STICK,
    LogicalButton.DPAD_UP: Button.DPAD_UP,
    LogicalButton.DPAD_DOWN: Button.DPAD_DOWN,
    LogicalButton.DPAD_LEFT: Button.DPAD_LEFT,
    LogicalButton.DPAD_RIGHT: Button.DPAD_RIGHT,
}
```

スティック:

```python
left = Stick.normalized(
    x=frame.left_stick.x,
    y=frame.left_stick.y,
)
right = Stick.normalized(
    x=frame.right_stick.x,
    y=frame.right_stick.y,
)
```

IMU:

```python
imu = IMUFrame.gyro_rate(
    x_rad_s=frame.gyro_rate.x_radians_per_second,
    y_rad_s=frame.gyro_rate.y_radians_per_second,
    z_rad_s=frame.gyro_rate.z_radians_per_second,
).with_accel_g(
    x_g=frame.accel_g.x_g,
    y_g=frame.accel_g.y_g,
    z_g=frame.accel_g.z_g,
)

state = InputState(
    buttons=frozenset(BUTTON_MAP[b] for b in frame.buttons),
    left_stick=left,
    right_stick=right,
    imu_frames=(imu, imu, imu),
)
```

定常rest状態も同じ変換経路を使い、`GyroRate(0, 0, 0)` と `AccelG(0, 0, 1)` を明示する。現行swbt-pythonのゼロ加速度ニュートラルを通常の静止状態として利用しない。

変換結果は `await controller.apply(state)` で一括反映する。ボタン、スティック、IMUを別々の呼び出しで更新しない。

## 6. フレーム併合

`ControllerRuntime.offer_frame()` は最新フレームだけを保持する。

処理規則:

- `sequence` が現在値以下なら破棄
- `capture_epoch` が現在の捕捉セッションと異なれば破棄
- 接続していなければ送信しないが、最新値は状態表示用に保持
- 接続中かつ新しい値なら `apply()`
- 同一の入力内容であれば `apply()` を省略可能
- `capture_active=True` のフレーム受信時刻を監視に記録
- 捕捉解除フレームは内容が同じに見えても必ず1回処理する

比較から `sequence` と `monotonic_ns` を除き、ボタン、スティック、角速度、加速度、捕捉状態を比較する。

## 7. 入力停止監視

目的は、Qt GUIスレッド停止時に最後の押下状態を送り続けないことである。

```text
monitor interval: 50 ms
timeout: 250 ms
active only when:
  connection == CONNECTED
  latest_frame.capture_active == True
```

タイムアウト時:

1. rest `InputState` を `apply()`
2. `watchdog_tripped = True`
3. 同じ停止中に繰り返しログを出さない
4. `WatchdogNeutralized` をUIへ通知
5. 次のフレームを受けても自動的に捕捉再開せず、アプリケーション側がIDLEへ戻す

## 8. ControllerColors

設定値:

```python
@dataclass(frozen=True, slots=True)
class ControllerColorSettings:
    body: int
    buttons: int
    left_grip: int
    right_grip: int
```

各値は `0x000000..0xFFFFFF` とする。`#RRGGBB` 文字列から整数への変換は設定層で行い、境界で次へ変換する。

```python
colors = ControllerColors(
    body=settings.body,
    buttons=settings.buttons,
    left_grip=settings.left_grip,
    right_grip=settings.right_grip,
)
```

色は `ProController` 生成時の引数であるため、接続中の変更は次回再生成時に反映する。UIプレビューは即時更新する。

## 9. ボンド情報

保存先:

```text
<data_dir>/bonds/pro-controller/<slot>.json
```

規則:

- スロット名は `[a-z0-9][a-z0-9_-]{0,31}` に制限
- パストラバーサルを拒否
- Pro Controllerと将来のJoy-Conで同じファイルを共有しない
- 内容をProject_Demiが解釈、編集、整形しない
- ログへ内容を出さない
- 削除はユーザーの明示操作と確認が必要
- 可能なOSではユーザーだけが読める権限へ設定する

## 10. コマンド

```python
ControllerCommand = (
    DiscoverAdapters
    | ConnectSaved
    | StartPairing
    | Disconnect
    | RecreateWithColors
    | RequestStatus
    | Shutdown
)
```

各コマンドは不変データクラスとする。

```python
@dataclass(frozen=True, slots=True)
class ConnectSaved:
    adapter_id: str
    bond_path: Path
    timeout_seconds: float
    colors: ControllerColorSettings
```

`Path` をスレッド境界へ渡してよいが、最終的な許可済みディレクトリ内かを送信前に設定層で検証する。

## 11. イベント

```python
RuntimeEvent = (
    AdaptersDiscovered
    | ConnectionChanged
    | PairingProgress
    | StatusSnapshot
    | WatchdogNeutralized
    | ControllerError
    | RuntimeStopped
)
```

エラー:

```python
@dataclass(frozen=True, slots=True)
class ControllerError:
    category: ControllerErrorCategory
    summary: str
    retryable: bool
    diagnostic_id: str
```

UIへPythonスタックトレースを直接表示しない。スタックトレースはログへ、ユーザー画面には分類済み要約と診断IDを出す。

分類例:

- `ADAPTER_NOT_FOUND`
- `ADAPTER_OPEN_FAILED`
- `BOND_NOT_FOUND`
- `PAIRING_TIMEOUT`
- `RECONNECT_FAILED`
- `CONNECTION_LOST`
- `INVALID_INPUT`
- `SHUTDOWN_FAILED`
- `UNEXPECTED`

## 12. 診断

`swbt` の公開 `status()` または `snapshot()` が利用できる範囲で、次をProject_Demi用スナップショットへ変換する。

- ライフサイクル状態
- 接続状態
- 選択アダプター
- 最終成功時刻
- 最終エラー分類
- 送信フレーム番号
- 停止監視状態

内部HIDレポート、秘密鍵、ボンド本文を診断へ含めない。

## 13. ハードウェア前提

- PC内蔵Bluetoothと共有しない専用USB Bluetoothアダプターを使う。
- Windowsでは対象アダプターにBumbleから使えるドライバー設定が必要である。
- ドライバー変更はProject_Demi自身では行わない。
- アダプター抜去、OSスリープ、対象機器側切断は接続喪失として扱う。
- 実機互換性はOS、ドングル、ドライバー、対象機器ファームウェアごとに記録する。

## 14. 非採用

- COMポート
- `raspberrypi.local` へのTCP送信
- swbt内部レポートループへの直接アクセス
- HIDレポートの手動構築
- 接続オブジェクトの主スレッド利用
