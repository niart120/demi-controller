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

[connection]
adapter_id = ""
controller = "pro_controller"
bond_slot = "default"
timeout_seconds = 30.0
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
invert_y = false
pitch_limit_degrees = 75.0

[local_actions]
toggle_capture = ["CTRL+C"]
quit = ["CTRL+Q"]
release_capture = ["F12"]

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
source = "KEY:ESCAPE"
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
target = "ACCEL:ZERO"
```

組み込みプロファイルはアプリ内の正本から生成し、ユーザー設定には編集後の完全なbinding配列を保存する。0.1.0では差分保存を採用しない。旧版の組み込み Default profile に診断targetが不足する場合、読み込み時に不足行だけをメモリ上で末尾へ補い、既存bindingと変更済みsourceを保持する。補完結果は `MIGRATED` とし、次回の明示保存で設定ファイルへ反映する。

`horizontal_sensitivity` と `vertical_sensitivity` は独立した無次元倍率であり、`1.0` を標準値とする。一方を他方の比率として扱わない。角度は設定境界でラジアンへ変換し、`YawPitchModel` 内ではラジアン、ラジアン毎秒、Gだけを使う。静的加速度は通常経路で仮想姿勢から常時生成するため、有効化や尺度を変更する設定は設けない。完全な0Gはprofileの診断targetで一時的に上書きする。

`inverted` は省略時 `false` とする。0.1.0ではボタンターゲットだけに指定できる。スティック方向または診断targetへ指定された場合は設定エラーとする。反転割り当ての有効判定は `source_active XOR inverted` とする。

診断targetは `GYRO:Y_NEGATIVE`、`GYRO:Y_POSITIVE`、`GYRO:Z_POSITIVE`、`GYRO:Z_NEGATIVE`、`ACCEL:ZERO` とする。既定sourceは I/K/J/L/O だが、通常のbinding行として保存し、キー割り当て画面で変更できる。診断targetの `amount` は `1.0` 固定、`inverted` は `false` 固定とする。同じsourceがボタンまたはスティックにも割り当てられた場合は診断targetを優先する。

## 3. 型と制約

| 設定 | 制約 |
|---|---|
| window.width | 800..7680 |
| window.height | 520..4320 |
| connection.adapter_id | 0..256文字 |
| bond_slot | `[a-z0-9][a-z0-9_-]{0,31}` |
| timeout_seconds | 1.0..120.0 |
| diagnostic_level | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| 色 | `#[0-9A-Fa-f]{6}` |
| evaluation_interval_ms | 4..32。0.1.0 UIでは8固定 |
| horizontal_sensitivity | 0.1..10.0。独立した無次元倍率 |
| vertical_sensitivity | 0.1..10.0。独立した無次元倍率 |
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

## 5. 保存

原子的保存:

1. 同じ設定ディレクトリへ一時ファイルを作る。
2. UTF-8、LFでTOMLを書き込む。
3. `flush()` と可能な範囲で `fsync()` を行う。
4. `os.replace()` で置換する。
5. 一時ファイルを残さない。

連続する色スライダー操作は、UIプレビューだけ即時更新し、最後の変更から300ミリ秒後または「保存」押下時に書く。

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

## 8. ボンドと設定の分離

`settings.toml` にはボンドファイルの内容を入れず、スロット名だけを入れる。

```text
settings.toml
  bond_slot = "default"

resolved internally:
  <data_dir>/bonds/pro-controller/default.json
```

設定のエクスポート機能を将来追加しても、ボンド情報は既定で含めない。

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
- パストラバーサルを含むbond slot
- 将来版schema
- v1からv2への移行fixture
- 書き込み途中例外で元ファイルが残ること
- Windows/macOS/Linuxのパス解決
