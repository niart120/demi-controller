# 設定設計

## 1. 保存先

`platformdirs.PlatformDirs(appname="Project_Demi", appauthor=False)` を使う。

論理配置:

```text
config_dir/
└── settings.toml

data_dir/
└── bonds/
    └── pro-controller/
        └── default.json

log_dir/
├── project-demi.log
└── project-demi.log.1
```

具体的なOSパスは `platformdirs` に任せ、コードや文書へ固定しない。

## 2. 設定スキーマ

ルートにスキーマ識別子と版を置く。

```toml
schema = "demi.settings/v1"
```

初期例:

```toml
schema = "demi.settings/v1"
active_profile = "default"

[window]
width = 960
height = 640
maximized = false

[ui]
language = "en"

[connection]
adapter_id = ""
controller = "pro_controller"
reconnect_on_start = false
diagnostic_level = "INFO"

[controller.colors]
body = "#323232"
buttons = "#0F0F0F"
left_grip = "#323232"
right_grip = "#323232"

[input]
evaluation_interval_ms = 8
circular_stick_limit = false

[input.mouse]
gyro_enabled = true
horizontal_sensitivity = 1.0
vertical_sensitivity = 1.0
invert_x = false
invert_y = false
pitch_limit_degrees = 75.0

[local_actions]
toggle_capture = ["CTRL+C"]
quit = ["CTRL+Q"]
connection = ["CTRL+RETURN", "CTRL+ENTER"]

[[profiles]]
id = "default"
name = "Default"
builtin = true

[[profiles.bindings]]
source = "KEY:F"
target = "BUTTON:A"

[[profiles.bindings]]
source = "KEY:V"
target = "BUTTON:B"

[[profiles.bindings]]
source = "KEY:SPACE"
target = "BUTTON:B"

[[profiles.bindings]]
source = "KEY:E"
target = "BUTTON:X"

[[profiles.bindings]]
source = "MOUSE:MIDDLE"
target = "BUTTON:Y"

[[profiles.bindings]]
source = "KEY:R"
target = "BUTTON:R"

[[profiles.bindings]]
source = "KEY:Q"
target = "BUTTON:L"

[[profiles.bindings]]
source = "MOUSE:LEFT"
target = "BUTTON:ZR"

[[profiles.bindings]]
source = "MOUSE:RIGHT"
target = "BUTTON:ZL"
inverted = false

[[profiles.bindings]]
source = "KEY:TAB"
target = "BUTTON:ZL"

[[profiles.bindings]]
source = "KEY:LEFT_SHIFT"
target = "BUTTON:ZL"

[[profiles.bindings]]
source = "KEY:Z"
target = "BUTTON:MINUS"

[[profiles.bindings]]
source = "KEY:X"
target = "BUTTON:PLUS"

[[profiles.bindings]]
source = "KEY:F1"
target = "BUTTON:HOME"

[[profiles.bindings]]
source = "KEY:T"
target = "BUTTON:RIGHT_STICK"

[[profiles.bindings]]
source = "KEY:G"
target = "BUTTON:LEFT_STICK"

[[profiles.bindings]]
source = "KEY:W"
target = "LEFT_STICK:UP"
amount = 1.0

[[profiles.bindings]]
source = "KEY:A"
target = "LEFT_STICK:LEFT"
amount = 1.0

[[profiles.bindings]]
source = "KEY:S"
target = "LEFT_STICK:DOWN"
amount = 1.0

[[profiles.bindings]]
source = "KEY:D"
target = "LEFT_STICK:RIGHT"
amount = 1.0

[[profiles.bindings]]
source = "KEY:UP"
target = "RIGHT_STICK:UP"
amount = 1.0

[[profiles.bindings]]
source = "KEY:LEFT"
target = "RIGHT_STICK:LEFT"
amount = 1.0

[[profiles.bindings]]
source = "KEY:DOWN"
target = "RIGHT_STICK:DOWN"
amount = 1.0

[[profiles.bindings]]
source = "KEY:RIGHT"
target = "RIGHT_STICK:RIGHT"
amount = 1.0

[[profiles.bindings]]
source = "KEY:1"
target = "BUTTON:DPAD_UP"

[[profiles.bindings]]
source = "KEY:2"
target = "BUTTON:DPAD_RIGHT"

[[profiles.bindings]]
source = "KEY:3"
target = "BUTTON:DPAD_DOWN"

[[profiles.bindings]]
source = "KEY:4"
target = "BUTTON:DPAD_LEFT"

[[profiles.bindings]]
source = "KEY:I"
target = "GYRO:Y_NEGATIVE"

[[profiles.bindings]]
source = "KEY:K"
target = "GYRO:Y_POSITIVE"

[[profiles.bindings]]
source = "KEY:J"
target = "GYRO:Z_POSITIVE"

[[profiles.bindings]]
source = "KEY:L"
target = "GYRO:Z_NEGATIVE"

[[profiles.bindings]]
source = "KEY:O"
target = "GYRO:X_NEGATIVE"

[[profiles.bindings]]
source = "KEY:P"
target = "IMU:NEUTRAL"
```

組み込みプロファイルはアプリ内の正本から生成し、ユーザー設定には編集後の完全なbinding配列を保存する。0.1.0では差分保存を採用しない。旧版の組み込み Default profile に診断targetが不足する場合、読み込み時に不足行だけをメモリ上で末尾へ補い、既存bindingと変更済みsourceを保持する。補完結果は `MIGRATED` とし、次回の明示保存で設定ファイルへ反映する。

`local_actions.connection` は主キーボードとテンキーの Ctrl+Enter を表す。項目追加前の `demi.settings/v1` では欠落を許可し、`["CTRL+RETURN", "CTRL+ENTER"]` をメモリ上の既定値とする。次回の明示保存では項目を出力する。

`horizontal_sensitivity` と `vertical_sensitivity` は独立した無次元倍率であり、`1.0` を標準値とする。一方を他方の比率として扱わない。マウス差分は `MouseRotationMapper` でラジアンへ変換し、`RotationPoseModel` はラジアン、ラジアン毎秒、Gだけを扱う。静的加速度は通常経路で仮想姿勢から常時生成する。

`inverted` は省略時 `false` とする。0.1.0ではボタンターゲットだけに指定できる。スティック方向または診断targetへ指定された場合は設定エラーとする。反転割り当ての有効判定は `source_active XOR inverted` とする。

キー割り当て画面は `KEY:F` や `MOUSE:MIDDLE` などのcanonical sourceを設定へ保存し、表では `F` や利用者向けのマウスボタン名を表示する。表示言語の変更で保存値を変えない。同じsourceを別targetへ割り当てる場合は変更先と既存targetを示して確認し、置換を選んだ場合だけ既存行を未割り当てへ戻す。`KEY:F5` はマウス入力切替用のため保存できず、`KEY:F4`、`KEY:F12`、`KEY:ESCAPE` は保存できる。

診断targetは `GYRO:X_POSITIVE`、`GYRO:X_NEGATIVE`、`GYRO:Y_NEGATIVE`、`GYRO:Y_POSITIVE`、`GYRO:Z_POSITIVE`、`GYRO:Z_NEGATIVE`、`IMU:NEUTRAL` とする。既定sourceは U/O/K/J/L/P だが、通常のbinding行として保存し、キー割り当て画面で変更できる。診断targetの `amount` は `1.0` 固定、`inverted` は `false` 固定とする。同じsourceがボタンまたはスティックにも割り当てられた場合は診断targetを優先する。

## 3. 型と制約

| 設定 | 制約 |
|---|---|
| window.width | 800..7680 |
| window.height | 520..4320 |
| connection.adapter_id | 0..256文字 |
| diagnostic_level | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| 色 | `#[0-9A-Fa-f]{6}` |
| ui.language | `en` または `ja`。項目がない schema v1 は `en` として読む |
| evaluation_interval_ms | 4..32。0.1.0 UIでは8固定 |
| horizontal_sensitivity | 0.1..10.0。独立した無次元倍率 |
| vertical_sensitivity | 0.1..10.0。独立した無次元倍率 |
| invert_x / invert_y | 真偽値。初回設定はともに `false` |
| pitch_limit_degrees | 1.0..89.0 |
| stick amount | 0.0..1.0 |
| binding.inverted | 真偽値。ボタンターゲットだけで使用可能 |
| diagnostic amount | `1.0` 固定 |

未知の列挙値はエラーとする。数値を黙って範囲内へ修正せず、読み込み結果へ警告を含めて安全な既定値へ置換する。

## 4. 読み込み

```text
file missing
  -> defaults
  -> FIRST_RUN

valid current schema
  -> decode
  -> validate
  -> LOADED

valid current schema with incomplete built-in Default diagnostics
  -> decode
  -> append missing diagnostics in memory
  -> preserve stored file until explicit save
  -> MIGRATED

valid old schema
  -> decode old
  -> migrate in memory
  -> validate
  -> atomic save
  -> MIGRATED

invalid syntax or semantic error
  -> copy to settings.toml.broken-YYYYMMDD-HHMMSS
  -> defaults
  -> RECOVERED
```

破損ファイルを削除しない。退避コピーが失敗した場合も元ファイルを上書きしない。

現行schema v1で `input.mouse.invert_x` だけが欠落している設定は、`false` を補完して読み込む。保存済みの `invert_y` は明示値を保持し、初回既定値の `false` で上書きしない。保存時は `invert_x` を常に出力する。

## 5. 保存

原子的保存:

1. 同じ設定ディレクトリへ一時ファイルを作る。
2. UTF-8、LFでTOMLを書き込む。
3. `flush()` と可能な範囲で `fsync()` を行う。
4. `os.replace()` で置換する。
5. 一時ファイルを残さない。

色選択中はdraftとUIプレビューだけを即時更新し、設定ファイルへは「保存」押下時だけ書く。「取消」では複数色を変更済みでもdraftを破棄し、保存済みの4色をプレビューへ戻す。色見本には現在のcanonical `#RRGGBB` 値を保持するが、画面上へ常設表示しない。

## 6. 設定責務

```text
codec.py
  TOML <-> raw dict

migrations.py
  schema versions

validation.py
  raw/value validation

repository.py
  path, read, backup, atomic write

domain.settings
  immutable validated settings
```

`tomli_w` は書き込みだけに使う。読み込みはPython 3.12標準の `tomllib` を使う。

## 7. 移行

各移行は1版ずつ進める。

```python
MIGRATIONS = {
    "demi.settings/v1": migrate_v1_to_v2,
}
```

将来のv2を読むv1アプリは、上書きせず「この設定は新しい版で作成された」と表示する。未知の新版を既定値で保存し直してはならない。

## 8. 接続プロファイルと設定の分離

`settings.toml` には接続プロファイルの内容と保存先を入れない。Pro Controllerの接続プロファイルはアプリケーションが所有する固定パスへ保存する。

```text
settings.toml
  connection.adapter_id = "..."

resolved internally:
  <data_dir>/bonds/pro-controller/default.json
```

接続と新規ペアリングで使うtimeoutは30秒の内部値とし、利用者設定へ公開しない。`bond_slot`と`timeout_seconds`を含む既存のschema v1は両keyを無視して読み込み、再保存時に除去する。設定のエクスポート機能を将来追加しても、接続プロファイルは既定で含めない。

## 9. ログ

標準:

```text
maxBytes = 1 MiB
backupCount = 3
encoding = UTF-8
```

DEBUGでも次をマスクする。

- ボンド本文
- Bluetoothキー
- 完全な生HIDレポート
- OSユーザー名を含む絶対パス。必要時はホーム部分を `~` へ置換

## 10. 設定試験

- 初回起動
- 正常読み込み
- 不正TOML
- 色桁不足
- 無効なキー名
- 重複profile ID
- 旧schema v1の `bond_slot` / `timeout_seconds` を無視し、再保存時に除去すること
- 固定接続プロファイルパス
- 将来版schema
- v1からv2への移行fixture
- 書き込み途中例外で元ファイルが残ること
- Windows/macOS/Linuxのパス解決
