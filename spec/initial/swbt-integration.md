# swbt-python 統合設計

## 1. 対象契約

0.1.0は `swbt-python>=0.5.1,<0.6.0` を対象とする。Project_Demiは周期送信型を使わず、
入力レポートをBumbleの送信キューへ受理させるまでawaitできるDirect公開型だけに依存する。
HCIの送信完了や対象機器への反映は、このawaitの完了条件に含めない。主に次の公開要素を使う。

```python
from swbt import (
    Button,
    ControllerColors,
    IMUFrame,
    InputState,
    DirectProController,
    DirectSwitchGamepad,
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
controller = DirectProController(
    adapter=adapter_id,
    profile_path=bond_path,
    controller_colors=colors,
)
await controller.open()
```

生成から破棄までを同一ワーカースレッドへ限定する。`report_period_us` は渡さない。

### 3.2 接続

ユーザー操作を2経路に分ける。

#### 再接続

保存済みswbtプロファイルが存在する場合:

```python
await controller.reconnect(timeout=timeout_seconds)
```

アプリケーション側の `ConnectSaved` コマンド名と `bond_path` fieldは、Project_Demiが所有する
固定接続プロファイル境界として維持する。swbt公開APIへ渡すときだけ `profile_path` に写像する。
`timeout_seconds` は利用者設定ではなく、Project_Demi内部の30秒を渡す。

#### 新規ペアリング

ユーザー確認後、固定接続プロファイルが存在しない場合は新しいプロファイルを作成する。

```python
controller = await DirectProController.create_profile(
    adapter=adapter_id,
    profile_path=bond_path,
    local_address=None,
    pair_timeout=timeout_seconds,
    controller_colors=colors,
)
```

`create_profile()` の戻り値は初回ペアリング済みである。Project_Demiは同じcontrollerに
`open()`や`connect()`を重ねて呼ばない。`local_address=None`により、アダプターが起動後に
報告する現在のBluetoothアドレスを使い、Project_DemiからCSRの揮発領域を書き換えない。

初回ペアリングの失敗後にプロファイルが残っている場合は、同じ固定パスから再試行できる。

```python
controller = DirectProController(
    adapter=adapter_id,
    profile_path=bond_path,
    controller_colors=colors,
)
await controller.open()
await controller.connect(
    timeout=timeout_seconds,
    allow_pairing=True,
)
```

既存プロファイルに保存済みペアリング情報があれば再接続を優先し、なければペアリングする。
swbt 0.4のkey-store JSONや壊れたプロファイルは、`open()`時の検証エラーとして扱う。
アプリ起動時の自動再接続では `create_profile()` を使わない。

### 3.3 接続直後

swbt-python 0.5.1 の `create_profile()`、`connect()`、`reconnect()` は、HID link 接続だけでは
復帰せず、初期subcommand応答とplayer割り当てが完了したprotocol-ready状態まで待つ。
Project_Demiは、この公開APIが正常復帰した後、入力受付開始前に次を行う。

1. ボタン解放、スティック中央、ジャイロ0、加速度 `(0, 0, +1) G` のrest `InputState`を `send()` し、Bumbleの送信キュー受理を待つ
2. 接続状態を `CONNECTED` へ更新
3. UIへ接続イベントを通知
4. 最新フレームが捕捉中でなければrest状態を維持
5. ユーザーが明示的に捕捉を開始してから入力適用

`CONNECTED`通知と通常フレーム送信はprotocol-ready後に限る。Project_Demi側でHID channel
openを接続完了として再判定したり、固定時間の待機を追加したりしない。

### 3.4 切断

1. フレーム受付を停止
2. rest送信成功時は `close(neutral=False)`、rest送信失敗時だけ `close(neutral=True)` を最善努力で試す
3. コントローラーを閉じる
4. 内部参照を破棄
5. UIへ切断イベント
6. swbtプロファイルは保持

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

変換結果は `await controller.send(state)` で一括送信し、完了を待つ。ボタン、スティック、IMUを別々の呼び出しで更新しない。

## 6. フレーム併合

`ControllerRuntime.offer_frame()` は表示用の最新フレームと送信用の定数サイズ集約を分けて保持する。

処理規則:

- `sequence` が現在値以下なら破棄
- 古い `capture_epoch` は破棄し、新しいepochは未送信集約を破棄して開始
- 接続していなければ送信しないが、最新値は状態表示用に保持
- 接続中は評価frameごとに完全な `InputState` を `send()` する
- send中に届いた複数frameは、最新のボタン・スティック・加速度と、各軸の `Σ(gyro_rate × sample_duration)` を次の1送信へ集約する
- 集約後のgyro rateは累積角変位を累積時間で割って再構成する。ボタン遷移は保存せず最新状態を使う
- `capture_active=True` のフレーム受信時刻を監視に記録
- 捕捉解除フレームは内容が同じに見えても必ず1回処理する

安全境界（watchdog、切断、終了、再生成、送信失敗）では未送信集約を破棄し、理由を診断ログへ記録する。

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

1. workerの逐次処理でrest `InputState` を `send()`
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

色は `DirectProController` 生成時の引数であるため、接続中の変更ではrest送信成功後に再生成して反映する。UIプレビューは即時更新する。

## 9. 保存プロファイル

保存先:

```text
<data_dir>/bonds/pro-controller/<slot>.json
```

規則:

- スロット名は `[a-z0-9][a-z0-9_-]{0,31}` に制限
- パストラバーサルを拒否
- Pro Controllerと将来のJoy-Conで同じファイルを共有しない
- Bluetoothアドレスの選択方法とペアリングキーを含むswbt 0.5プロファイルとして扱う
- 内容をProject_Demiが解釈、編集、整形しない
- ログへ内容を出さない
- 削除はユーザーの明示操作と確認が必要
- 可能なOSではユーザーだけが読める権限へ設定する
- swbt 0.4の`key_store_path`が保存したJSONとは互換性がない。0.5への更新後は未使用スロットを
  選ぶか、旧ファイルを明示削除してから再ペアリングする。自動移行や自動上書きは行わない

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
- `PAIRING_PROFILE_EXISTS`
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
