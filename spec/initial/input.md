# キーボード・マウス入力設計

## 1. 入力取得方式

0.1.0ではQt Widgetsの入力イベントを使用し、OS固有の入力はアダプターへ隔離する。

| 入力 | Qt / OS入力境界 |
|---|---|
| キー押下・解放 | `QKeyEvent` |
| マウス押下・解放 | `QMouseEvent` |
| マウス移動 | `QMouseEvent` またはOS固有の相対入力イベント |
| フォーカス変化 | `QEvent.FocusIn` / `QEvent.FocusOut` |
| ウィンドウ終了 | `QCloseEvent` |


マウス捕捉はframework非依存の `PointerCapturePort` を介して実装する。WindowsではQt native event filterとWin32 Raw Inputを使い、キーボードのグローバルフックは導入しない。

グローバルフックは導入しない。入力が対象機器へ送られる条件は、Project_Demiウィンドウがフォーカスを持ち、ユーザーが入力捕捉を開始していることとする。

## 2. 入力モード

```text
IDLE
  UI操作可能
  コントローラー入力はニュートラル

CAPTURED
  キー・マウスをマッピング
  排他マウス有効
  設定UIは閉じている

CONFIGURING
  モーダルへ入力
  コントローラー入力はニュートラル
  排他マウス無効

SUSPENDED
  フォーカスなし
  保持入力消去
  再フォーカスしてもIDLEへ戻るだけ

SHUTTING_DOWN
  新規入力を無視
  ニュートラル化と切断を実行
```

遷移:

```text
IDLE -- input start --> CAPTURED
CAPTURED -- F12 / toolbar --> IDLE
CAPTURED -- focus lost --> SUSPENDED
SUSPENDED -- focus gained --> IDLE
IDLE -- open dialog --> CONFIGURING
CONFIGURING -- close dialog --> IDLE
any -- close --> SHUTTING_DOWN
```

## 3. 入力の優先順位

同じイベントを複数用途へ流さない。

1. `F12` の捕捉解除
2. 開いているモーダルまたはキー取得欄
3. ローカル操作の完全一致ショートカット
4. `CAPTURED` 中の profile 設定済み IMU 診断入力
5. `CAPTURED` 中のコントローラーマッピング
6. 未使用イベント

`Ctrl+C` は `CAPTURED` 中だけ任意設定の捕捉切替として使える。文字入力欄や設定画面では通常の文字操作を妨げない。`F12` は常に捕捉解除を優先し、ユーザー割り当て不可とする。

## 4. 物理入力モデル

```python
@dataclass(frozen=True, slots=True)
class KeySource:
    symbol: str
    modifiers: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class MouseButtonSource:
    button: str


PhysicalSource = KeySource | MouseButtonSource
```

保存するキー名はQtの定数値そのものではなく、正規化した文字列とする。

例:

```text
KEY:F
KEY:SPACE
KEY:LEFT_SHIFT
KEY:UP
MOUSE:LEFT
MOUSE:MIDDLE
MOUSE:RIGHT
MOUSE:BUTTON_4
```

未知キーやOEMキーはプラットフォーム間で一致しない場合がある。UIは `platform_specific = true` を表示し、別OSで設定を読み込んだ際に未解決として扱う。

保持状態:

```python
@dataclass(slots=True)
class PhysicalInputState:
    held_keys: set[KeySource]
    held_mouse_buttons: set[MouseButtonSource]
    accumulated_dx: float
    accumulated_dy: float
    revision: int
```

- 押下は集合へ追加する。
- 解放は集合から除く。存在しなくてもエラーにしない。
- マウス差分は加算する。
- 8ミリ秒評価時に差分を取得して0へ戻す。
- `clear()` は保持状態と差分を初期化する。仮想姿勢は `YawPitchModel.reset()` で初期化する。

## 5. マッピングモデル

### 5.1 対象

```python
class MappingTargetKind(Enum):
    BUTTON = auto()
    LEFT_STICK_X = auto()
    LEFT_STICK_Y = auto()
    RIGHT_STICK_X = auto()
    RIGHT_STICK_Y = auto()
    LOCAL_ACTION = auto()
```

ボタン対象には `LogicalButton` を指定する。スティック対象には `direction` と `amount` を指定する。

### 5.2 ボタン入力の反転

ボタン割り当ては、対象固有の分岐ではなく `inverted` 属性を持つ。

```python
@dataclass(frozen=True, slots=True)
class ButtonBinding:
    source: PhysicalSource
    target: LogicalButton
    inverted: bool = False
```

割り当て単位の有効判定は次のとおり。

```python
binding_active = source_active ^ binding.inverted
```

- `inverted = false`: 物理入力を押している間、対象ボタンを押下する。
- `inverted = true`: 物理入力を押していない間、対象ボタンを押下する。
- 入力捕捉を開始した直後は、反転割り当ての対象が押下状態になり得る。
- 入力捕捉外では反転割り当てを評価せず、必ずニュートラルを生成する。
- スティック方向は反転属性を持たない。反対方向を割り当てることで表現する。
- 連射、パルス、トグルは0.1.0へ入れない。

### 5.3 複数入力

1つの対象へ複数ソースを割り当てられる。

```text
V     ─┐
SPACE ─┴──► B
```

ボタンは、各割り当てについて `source_active XOR inverted` を評価し、その結果が1つ以上真なら押下状態になる。個別イベントでビットを立てたり消したりしない。

## 6. スティック合成

方向キーを数値へ変換する。

```text
negative held = -amount
positive held = +amount
both or none = 0
```

例:

```python
x = float(right_held) - float(left_held)
y = float(up_held) - float(down_held)
```

斜め入力は初期設定では各軸 `±1.0` とする。円形制限を有効にする設定では、長さが1を超えた場合に正規化する。

```python
length = hypot(x, y)
if circular_limit and length > 1.0:
    x /= length
    y /= length
```

0.1.0既定値は、デジタル入力の各軸を最大値まで保つため `circular_limit = false` とする。

## 7. マウスからIMUへの変換

### 7.1 YawPitchModel

`YawPitchModel` はマウスの水平移動をワールド上方向まわりのyaw、垂直移動をpitchとして扱う。rollは蓄積しない。pitchは設定された上限内に制限する。

水平感度と垂直感度は、それぞれ独立した無次元倍率とする。`1.0` を標準値とし、一方を他方の比率として定義しない。実行時の角度と角速度はラジアンとラジアン毎秒へ統一する。

```python
@dataclass(frozen=True, slots=True)
class GyroSettings:
    enabled: bool = True
    horizontal_sensitivity: float = 1.0
    vertical_sensitivity: float = 1.0
    invert_y: bool = False
    pitch_limit_radians: float = 5.0 * pi / 12.0


BASE_YAW_RADIANS_PER_INPUT_UNIT = pi / 6000.0
BASE_PITCH_RADIANS_PER_INPUT_UNIT = pi / 6000.0
```

二つの基準値は初期版では同値だが、設定上の感度は独立して適用する。モデルは現在の `pitch_radians` だけを状態として保持する。`pitch_limit_degrees` は設定読み込み時に一度だけ `pitch_limit_radians` へ変換する。

### 7.2 コントローラー座標系

Project_Demiのドメイン層は、Pro Controllerおよび左Joy-Conと整合する次の右手座標系を使う。

```text
+X: トリガー方向
+Y: コントローラー左方向
+Z: ボタン・スティック面から外向き
```

水平なPro Controllerをボタン面が上になるように静置したとき、加速度センサーの静止値は概ね `(0, 0, +1) G` となる。これは下向きの重力ベクトルではなく、センサーが報告する比力の符号である。

既存資料では、右Joy-ConはIMU実装の向きによりraw Y/ZがPro Controller・左Joy-Conと逆になる。0.1.0はPro Controllerだけを対象とするため変換は恒等である。将来Joy-Conを追加するときは、profile-awareな接続アダプター境界で軸を正規化し、`YawPitchModel` にデバイス固有の符号分岐を入れない。

根拠:

- Linux `hid-nintendo`: Pro Controller・左Joy-Con共通の正方向と右Joy-Con Y/Z反転
- dekuNukem IMU notes: report上のaccel X/Y/Z順序とJoy-Con間の軸差
- dekuNukem SPI notes:平置き補正値でPro Controller・左Joy-ConのZが正、右Joy-ConのZが負

### 7.3 標準アルゴリズム

各評価周期で、前回評価からの実経過時間 `dt_seconds` と蓄積済みの `dx`、`dy` を使う。ジャイロのyaw投影には区間中央のpitch、フレーム時点の静的加速度には更新後のpitchを使う。

```python
yaw_delta_radians = (
    -dx
    * BASE_YAW_RADIANS_PER_INPUT_UNIT
    * horizontal_sensitivity
)

pitch_direction = -1.0 if invert_y else 1.0
requested_pitch_delta_radians = (
    dy
    * BASE_PITCH_RADIANS_PER_INPUT_UNIT
    * vertical_sensitivity
    * pitch_direction
)

previous_pitch_radians = pitch_radians
next_pitch_radians = clamp(
    previous_pitch_radians + requested_pitch_delta_radians,
    -pitch_limit_radians,
    pitch_limit_radians,
)
pitch_delta_radians = next_pitch_radians - previous_pitch_radians
middle_pitch_radians = (
    previous_pitch_radians + next_pitch_radians
) * 0.5

local_delta_x_radians = (
    -sin(middle_pitch_radians) * yaw_delta_radians
)
local_delta_y_radians = pitch_delta_radians
local_delta_z_radians = (
    cos(middle_pitch_radians) * yaw_delta_radians
)

gyro_rate = GyroRate(
    x_radians_per_second=local_delta_x_radians / dt_seconds,
    y_radians_per_second=local_delta_y_radians / dt_seconds,
    z_radians_per_second=local_delta_z_radians / dt_seconds,
)

accel_g = AccelG(
    x_g=-sin(next_pitch_radians),
    y_g=0.0,
    z_g=cos(next_pitch_radians),
)

pitch_radians = next_pitch_radians
```

yawはワールド上方向まわりの回転なので、静的加速度はyaw角に依存しない。`AccelG` のノルムは常に1とする。

`dt_seconds <= 0` の場合は内部状態を更新せず、ジャイロを0 rad/s、加速度を現在の `pitch_radians` に対応する1Gとする。pitch上限で外向きの垂直入力を受けた場合、`pitch_delta_radians` は0になるが、yawは通常どおり処理する。

0.1.0で生成しないもの:

- マウス移動に対応する並進加速度
- 回転中心からの距離に依存する遠心・接線加速度
- センサーノイズ、オフセット、温度ドリフト
- コントローラー外形の突起による平置き傾斜
- roll

### 7.4 swbt-pythonへの引き渡し

`YawPitchModel` は `GyroRate` と `AccelG` を生成し、符号付き16ビットraw値への変換は行わない。raw表現は `demi.controller.swbt_adapter` で、swbt-pythonの公開APIへ委譲する。

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
```

このAPIはswbt-python issue #69と#70で定義する契約を前提とする。Project_Demiはジャイロ・加速度の校正値、SPIアドレス、`0.070 dps/raw`、`1 / 4096 G/raw`などの換算値をローカルに複製しない。APIが未提供の版に対する独自フォールバックも設けない。

0.1.0では生成した1サンプルを `swbt.InputState` の3つのIMUフレームへ複製する。

### 7.5 ニュートラルIMU

Project_Demiの定常ニュートラルは次である。

```python
gyro_rate = GyroRate(0.0, 0.0, 0.0)
accel_g = AccelG(0.0, 0.0, 1.0)
```

接続直後、捕捉解除、フォーカス喪失、停止監視、切断前には、このIMUを含む完全な `InputState` を `apply()` する。現行swbt-pythonの `IMUFrame.neutral()` / `InputState.neutral()` は加速度も0にするため、定常的な静止状態の生成には使わない。`controller.neutral()` は明示フレーム送信に失敗した場合や終了時の最終フォールバックに限定する。

| 項目 | 規則 |
|---|---|
| マウス入力 | PointerCapturePortが提供する相対差分 |
| 評価目標 | 8ms |
| 時間 | 単調増加時計で測定した実経過時間 |
| ドメイン座標 | +Xトリガー、+Y左、+Zボタン面外向き、右手系 |
| 内部角度 | ラジアン |
| 内部角速度 | ラジアン毎秒 |
| 内部加速度 | G |
| pitch範囲 | `-pitch_limit_radians..+pitch_limit_radians` |
| raw変換 | swbt-pythonの `gyro_rate()` / `with_accel_g()` に委譲 |
| 範囲超過 | swbt-python公開APIの契約に従い、失敗時は物理ニュートラルを適用して接続エラーとして扱う |
| 調整項目 | 独立した水平感度、垂直感度、Y反転、pitch上限 |
| 加速度設定 | 通常モデルの設定は追加しない。`ACCEL:ZERO` 診断targetの保持中だけ最終フレームを0Gへ上書き |

マウス差分は1評価周期内で加算し、1回だけ消費する。差分がない周期では角速度を0にするが、静的加速度は維持する。モデルの選定理由と代替案は `appendix/aim-model.md` に記載する。

### 7.6 設定可能な IMU 診断入力

入力捕捉中は、profileに保存された次の診断targetを評価する。

| target | 既定キー | 出力 |
|---|---|---|
| `GYRO:Y_NEGATIVE` | I | Y 軸 `-1.0 rad/s` |
| `GYRO:Y_POSITIVE` | K | Y 軸 `+1.0 rad/s` |
| `GYRO:Z_POSITIVE` | J | Z 軸 `+1.0 rad/s` |
| `GYRO:Z_NEGATIVE` | L | Z 軸 `-1.0 rad/s` |
| `ACCEL:ZERO` | O | 加速度 `(0, 0, 0) G` |

診断targetのsourceはキー割り当て画面で変更できる。ジャイロ診断は `amount = 1.0` 固定とし、同じ軸の反対方向を同時に保持した場合は、その軸を `0.0 rad/s` とする。マウス入力がある場合は、`YawPitchModel` が生成した角速度へ軸ごとに加算する。`gyro_enabled = false` はマウス由来の角速度だけを無効にし、ジャイロ診断には適用しない。

`ACCEL:ZERO` のsourceを保持している間は、`YawPitchModel` の内部pitchを更新したまま、最終 `ControllerFrame.accel_g` だけを完全な0Gへ置換する。解放後は内部pitchを初期化せず、現在姿勢に対応する静的1Gへ戻す。これは対象側の挙動を比較する診断例外であり、通常の静止状態には使わない。

未接続中に入力捕捉を開始して `ACCEL:ZERO` のsourceを保持し、その状態で接続すると、接続成功直後の初期フレームもボタン、スティック、ジャイロをニュートラルにしたまま加速度だけを0Gとする。切断、捕捉解除、watchdog、終了時は診断状態にかかわらず `(0, 0, +1) G` の安全ニュートラルを使う。

診断targetは通常のボタンまたはスティックtargetより優先する。同じsourceの通常bindingは評価せず、競合はキー割り当て画面へ表示する。捕捉外、フォーカス喪失、捕捉 epoch 変更では保持状態を消去し、診断入力を残留させない。アローキーの右スティック割り当ては変更しない。

## 8. 組み込みプロファイルと入力反転

### 8.1 Default

| PC入力 | 対象 |
|---|---|
| F | A |
| V、Space | B |
| E | X |
| 中央マウス | Y |
| R | R |
| Q | L |
| 左マウス | ZR |
| 右マウス | ZL |
| Tab、左Shift | ZL |
| Z | Minus |
| X | Plus |
| Esc | Home |
| T | 右スティック押下 |
| G | 左スティック押下 |
| W/A/S/D | 左スティック 上/左/下/右 |
| 矢印キー | 右スティック |
| 1/2/3/4 | 十字キー 上/右/下/左 |
| I/K | 診断ジャイロ Y軸 -/+ |
| J/L | 診断ジャイロ Z軸 +/- |
| O | 診断加速度 0G |
| Ctrl+C | 入力捕捉切替 |
| Ctrl+Q | 終了 |
| F12 | 捕捉解除、変更不可 |

既定のボタン割り当てはすべて `inverted = false` とする。

### 8.2 反転割り当て

反転は任意のボタン割り当てに設定できる。たとえば右マウスでZLを反転する場合は次の設定になる。

```toml
[[profiles.bindings]]
source = "MOUSE:RIGHT"
target = "BUTTON:ZL"
inverted = true
```

この場合、入力捕捉中は右マウスを押していない間だけZLが有効になり、押している間は無効になる。右マウスやZLに専用処理は設けない。同じ仕組みを任意のキー、マウスボタン、コントローラーボタンへ適用する。

## 9. キー取得UI

キー割り当て欄を押すと `KEY_CAPTURE` 状態へ入る。

```text
1. 既存入力をニュートラル化
2. 排他マウスを解除
3. 「キーまたはマウスボタンを入力」と表示
4. 次の押下を候補として表示
5. 競合検査
6. 適用または取消
```

修飾キー単独も割り当てられる。修飾キーを含む組み合わせはローカル操作に限定し、コントローラーボタンの初期GUIでは単一キーだけを扱う。これにより、押下順序による曖昧さを減らす。

## 10. フォーカス喪失

`on_deactivate` では同一フレーム内に次を行う。

1. 排他マウスを解除する。
2. `PhysicalInputState.clear()` を呼ぶ。
3. `YawPitchModel.reset()` を呼ぶ。
4. ニュートラルな `ControllerFrame` を生成する。
5. ワーカーへ `offer_frame()` する。
6. UI状態を `SUSPENDED` にする。

フォーカス復帰時は `IDLE` へ戻すだけで、自動捕捉しない。

## 11. 入力受入試験

- W押下、D押下、W解放、D解放で `(0,1) -> (1,1) -> (1,0) -> (0,0)` になる。
- AとDの同時押下でX軸が0になる。
- Fと別のA割り当てキーを同時に押し、一方だけ解放してもAが残る。
- 1周期内に `dx=2, 3, -1` が来た場合、4として1回だけ消費する。
- 捕捉解除後の最初のフレームは完全なニュートラルである。
- 任意のボタン割り当てで `inverted = true` が `source_active XOR true` として評価される。
- 反転割り当てがあっても、捕捉解除後のフレームは完全なニュートラルである。
- OEMキー設定を別OSで読み込むと未解決として表示し、勝手に別キーへ置換しない。
