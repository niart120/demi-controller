# 命名規約

## 1. 公開名称

| 用途 | 名称 |
|---|---|
| 製品表示 | `Project_Demi` |
| リポジトリ | `Project_Demi` |
| Python配布 | `project-demi` |
| import | `demi` |
| CLI | `project-demi` |
| Windows実行ファイル | `Project_Demi.exe` |
| ログ名 | `project-demi.log` |
| 設定スキーマ | `demi.settings/v1` |

READMEの見出しは `Project_Demi`、文章中は「Project_Demi」または「Demi」とする。Python識別子に `ProjectDemi` を重複して付けない。

## 2. モジュール名

- 小文字の単数形を基本にする。
- `utils.py`、`common.py`、`misc.py` を作らない。
- 責務が増えたら名前で分割する。
- OS固有処理は `platform` または具象バックエンド名へ置く。
- 外部ライブラリ名を境界クラスへ含める。

良い例:

```text
demi.input.qt_adapter
demi.controller.swbt_adapter
demi.config.repository
demi.ui.controller_preview
```

避ける例:

```text
demi.utils
demi.manager
demi.common
demi.controller_helper
```

## 3. クラス名

| 種類 | 接尾辞 |
|---|---|
| 外部境界 | `Adapter` |
| アプリケーションポート | `Port` |
| 永続化 | `Repository` |
| UI表示変換 | `Presenter` |
| 状態値 | 内容を表す名。`Data` を付けない |
| コマンド | 動詞句 |
| イベント | 過去形または状態変化 |
| エラー分類 | `ErrorCategory` |
| 具象例外 | `Error` |

例:

```python
SwbtControllerAdapter
ControllerPort
SettingsRepository
ApplicationPresenter
ConnectSaved
AdaptersDiscovered
ConnectionChanged
ControllerErrorCategory
ConfigurationError
```

`Manager` と `Handler` は責務が曖昧になりやすいため原則使わない。Qtのイベントハンドラーとして意味が限定される場合だけ `Handler` を認める。

## 4. 状態名

状態は形容詞または過去分詞に揃える。

```text
IDLE
CAPTURED
CONFIGURING
SUSPENDED
CONNECTING
CONNECTED
DISCONNECTING
SHUTTING_DOWN
```

`IS_CONNECTED` のような真偽値風列挙名は使わない。

## 5. 入力名

### 物理入力

```text
KEY:F
KEY:LEFT_SHIFT
MOUSE:LEFT
MOUSE:BUTTON_4
```

### 論理ボタン

```text
A
B
X
Y
L
R
ZL
ZR
PLUS
MINUS
HOME
CAPTURE
LEFT_STICK
RIGHT_STICK
DPAD_UP
DPAD_DOWN
DPAD_LEFT
DPAD_RIGHT
```

### スティック対象

```text
LEFT_STICK:UP
LEFT_STICK:DOWN
LEFT_STICK:LEFT
LEFT_STICK:RIGHT
RIGHT_STICK:UP
RIGHT_STICK:DOWN
RIGHT_STICK:LEFT
RIGHT_STICK:RIGHT
```

UI表示では日本語へ変換してよいが、設定値は英大文字の正規名とする。

## 6. コントローラー用語

- Project_Demi内部では `ControllerFrame` を使う。
- `Command` という名前を入力状態へ使わない。接続操作コマンドと混同するためである。
- `InputState` はswbt型と衝突するため、ドメインでは使わない。
- `Gamepad` と `Controller` を混在させず、Project_Demi側は `Controller` に揃える。
- マウスから仮想姿勢とIMU値を生成するクラスは `YawPitchModel` とする。実装ファイル名は `yaw_pitch_model.py` とする。
- 角速度のドメイン値は `GyroRate`、G単位加速度のドメイン値は `AccelG` とする。
- `AccelG` は静止時の比力を含む加速度センサー値であり、下向き重力ベクトルを意味する `GravityVector` は使わない。
- `GyroRate` と `AccelG` をまとめるだけの `MotionSample` は追加せず、`ControllerFrame` に直接保持する。
- raw変換用クラスをProject_Demi内へ設けない。
- NX互換、Pro Controller相当という表現を使い、公式承認を示唆しない。

## 7. 設定キー

TOMLは `snake_case` とする。

```toml
reconnect_on_start = false
timeout_seconds = 30.0
left_grip = "#323232"
```

物理量を直接表す値は単位を名前へ含める。

```text
timeout_seconds
evaluation_interval_ms
monotonic_ns
pitch_limit_radians
pitch_limit_degrees
x_radians_per_second
y_g
```

無次元倍率には単位を付けない。`horizontal_sensitivity` と `vertical_sensitivity` はそれぞれ独立した線形倍率で、`1.0` を標準値とする。`timeout = 30` のように物理量の単位が不明な名前は作らない。

## 8. 試験名

```python
def test_opposing_left_stick_keys_cancel_each_other() -> None: ...
def test_focus_loss_publishes_neutral_frame() -> None: ...
def test_watchdog_ignores_idle_frames() -> None: ...
```

実装メソッド名を繰り返すより、観測される挙動を書く。

## 9. コミット

Conventional Commits:

```text
feat(input): add Qt relative mouse backend
fix(runtime): neutralize after capture watchdog timeout
docs(spec): define controller color reconnect flow
test(mapping): cover duplicate sources for one button
chore(deps): lock swbt-python 0.2.0
```

## 10. 非提携注記

公開READMEと配布物のAbout画面に次の趣旨を含める。

```text
Project_Demiは対象機器および関連商標の権利者から
承認、後援、提携を受けたものではありません。
```

公式ロゴ、公式製品写真、公式UI素材を同梱しない。
