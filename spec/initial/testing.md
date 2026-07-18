# 試験設計

## 1. 層別方針

```text
unit
  高速、機材不要、OS依存を避ける

integration
  Qt / swbt境界の偽実装を使う
  スレッド、状態遷移、設定I/Oを確認

bumble
  専用USBアダプターが必要
  対象機器は不要な範囲

hardware
  専用USBアダプターと対象機器が必要
```

通常CIでは `unit` と `integration` を実行し、`bumble` と `hardware` は明示実行だけにする。

## 2. pytestマーカー

```toml
[tool.pytest.ini_options]
addopts = "-ra --strict-config --strict-markers"
testpaths = ["tests"]
markers = [
  "bumble: requires a dedicated USB Bluetooth dongle opened through Bumble",
  "hardware: requires a target NX-family console and Bluetooth HID behavior",
  "ui: exercises Qt Widgets and may require a display server",
]
```

## 3. 単体試験

### 3.1 物理入力状態

- 押下を集合へ追加
- 重複押下が1件のまま
- 未保持キー解放が無害
- マウス差分の加算
- 差分の1回消費
- clearで全状態が消える

### 3.2 ボタンマッピング

- 1ソース1対象
- 複数ソース1対象
- 一方のソースだけ解放
- 重複binding
- 無効なtarget
- `inverted = false/true` の有効判定
- 通常割り当てと反転割り当てのOR集約
- 反転割り当てを任意の物理入力・論理ボタンへ適用
- 捕捉外では常にニュートラル

### 3.3 スティック

- 正負各方向
- 同時反対方向
- 斜め
- amount境界
- 円形制限有無
- 浮動小数点誤差を許容した境界

### 3.4 IMU

- dx=0, dy=0でジャイロ0、加速度 `(0, 0, +1) G`
- yawとpitchのジャイロ符号
- 水平反転がyawだけ、垂直反転がpitchだけへ作用する
- 水平反転と垂直反転をともに無効にしたマウス上下がI/Kと同じ符号になる
- 感度 `1.0` が標準変換量になる
- 水平感度の変更がyawだけへ作用する
- 垂直感度の変更がpitchだけへ作用する
- `pitch_limit_degrees` が設定境界でラジアンへ変換される
- pitchの±上限
- pitch上限でもyawが継続する
- マウスと診断キーのpitch角変位を加算した後に共通上限を適用し、上限では実効ジャイロYも停止する
- 上限から中央方向へ直ちに戻れる
- 区間中央pitchによるジャイロX/Z軸投影
- マウスyawと診断キーyawが同じX/Z軸投影を使う
- 更新後pitchによる `AccelG(-sin(pitch), 0, cos(pitch))`
- `AccelG` のノルムが許容誤差内で1
- yawだけを変えても `AccelG` が変化しない
- 実経過時間による角速度変換
- `dt <= 0` で姿勢を更新せず、ジャイロ0と現在姿勢の1G
- reset後のpitch=0、加速度 `(0, 0, +1) G`
- 1周期内差分合計
- 一定速度のマウス差分を不規則な評価周期へ分割しても、初期過渡後の速度と総変位を維持する
- 疎な同方向マウス差分を固定周期と不規則周期で再標本化し、移動中の非0、停止後の0、総変位を維持する
- マウス方向反転を0の評価を挟まず出力し、累積変位を実入力の範囲内に保つ
- マウス再標本化のresetでX/Yの速度履歴と未出力変位を破棄する
- Windows Raw Inputから偽gamepadまで、低速入力と同時刻catch-upのジャイロ列を維持する
- 疎なRaw Inputと診断キーを同時入力し、総yaw、共通pitch上限、3 IMU slotを維持する
- profileで変更したsourceから診断ジャイロ4方向を評価し、マウスジャイロ設定に依存しない `1.0 rad/s` の回転要求を生成する
- 同一軸の正負診断targetを同時保持した場合の相殺
- 診断targetと同じsourceのボタンまたはスティックbindingを評価しない
- マウス由来と診断target由来のyaw / pitch角変位を軸ごとに加算してから姿勢を更新する
- Y 軸診断targetの固定角速度を実経過時間で統一pitchへ積分し、評価周期の分割によらず同じ静的1Gを生成する
- Y 軸診断targetの解放後は姿勢を維持し、Z 軸診断targetだけでは静的加速度を変更しない
- 捕捉解除と捕捉 epoch 変更で診断target由来の姿勢を水平へ戻す
- `ACCEL:ZERO` 保持中だけ最終フレームを完全な0Gとし、内部pitchを維持したまま解放後に静的1Gへ戻る
- キー解放、捕捉解除、捕捉 epoch 変更で診断入力が残留しない

### 3.5 設定

- 初期値
- 正常TOML往復
- 破損退避
- 原子的置換失敗
- 色変換
- bond slot検証
- 未知schema
- 移行
- 旧Default profileの既存bindingを保持した診断target補完と `MIGRATED`
- 診断targetのTOML往復、`amount = 1.0` 固定、反転拒否
- 接続ローカル操作の Ctrl+Return / Ctrl+Enter 往復と、項目追加前のv1設定に対する既定値補完
- 現行schema v1の `invert_x` 欠落を `false` で補完し、保存済みの `invert_y` 明示値を保持する
- binding競合

### 3.6 状態遷移

- 全許可遷移
- 禁止遷移
- 二重接続
- 捕捉開始前提
- フォーカス喪失
- 設定モーダル
- 終了の冪等性

## 4. 統合試験

### 4.1 FakeControllerPort

記録内容:

```python
@dataclass
class FakeControllerPort:
    commands: list[ControllerCommand]
    frames: list[ControllerFrame]
    emitted_events: list[RuntimeEvent]
```

次を注入できる。

- 接続成功
- 接続タイムアウト
- 接続喪失
- 切断失敗
- 停止監視
- 色再生成失敗
- アダプター0件または複数件

### 4.2 ワーカースレッド

実 `asyncio` ループと偽SwbtAdapterで確認する。

- start/close
- 順序付きコマンド
- 最新フレームだけを適用
- 古いsequenceを破棄
- capture epoch不一致を破棄
- 250ミリ秒監視
- UIイベントの主スレッド投稿
- シャットダウン時にタスクが残らない

時間は短い実待ちではなくFakeClockを使う。イベントループ同期だけ必要な箇所に限定して小さな待機を使う。

### 4.3 UI Presenter

Qtの描画実装そのものより、表示モデルとwidget stateを確認する。

- ConnectionStateからボタンラベル
- CaptureStateから枠表示
- ControllerFrameから各コントロール表示
- 色変更プレビュー
- エラー分類からユーザー向け文
- モーダル排他
- キー割り当てダイアログでマウスジャイロの有効、水平・垂直感度、水平・垂直反転、pitch上限を現在値から編集する
- マウスジャイロ設定の保存がrepository、session、実行中のPublisherへ反映され、取消では編集前の値を維持する
- 捕捉中の Ctrl+Return / Ctrl+Enter が保持入力を解除せず、状態依存の接続actionを1回発行

### 4.4 Qt入力アダプター

表示サーバー不要の範囲ではQt eventを直接注入する。

- Qt keyの正規化
- modifiers
- mouse button
- dx/dy
- deactivate
- F12優先
- Ctrl+ReturnとCtrl+Enterを区別したshortcut配送

実ウィンドウ試験は `ui` マーカーへ分離する。

### 4.5 UI言語

- 設定項目がないschema v1では英語を補完し、`en`と`ja`をTOML往復する。
- 英語と日本語の代表Widgetで、アプリ固有文言とQt標準ボタンが同じ言語になることを確認する。
- app catalogまたはQt catalogがない場合、translatorを部分適用せず英語へ戻ることを確認する。
- 翻訳後もbinding、diagnostic level、TOML keyがcanonical値を維持することを確認する。
- sdistとwheelに`.ts`と`.qm`が入り、展開したwheelから`QTranslator`で読み込めることを確認する。

## 5. 契約試験

`SwbtControllerAdapter` の変換契約を、実Bluetoothなしで確認する。

- 全LogicalButtonが対応するswbt.Buttonへ変換される
- StickVector `-1, 0, 1` が有効範囲になる
- `GyroRate` が `IMUFrame.gyro_rate()` へrad/sのまま渡される
- `AccelG` が `with_accel_g()` へGのまま渡され、ジャイロを保持した同一フレームになる
- 生成IMUフレームが3スロットへ複製される
- 定常rest状態はジャイロ0、加速度 `(0, 0, +1) G` であり、診断外では0Gを送らない
- 捕捉中0Gの最新フレームがある接続では、初期フレームの操作値をニュートラル、加速度を0Gとする
- 切断とwatchdogの安全ニュートラルは、接続初期0G診断後も `(0, 0, +1) G` を維持する
- 完全なInputStateを1回のapplyへ渡す
- ControllerColorsの4色
- swbt例外がControllerErrorCategoryへ変換される

swbtの内部実装をmockしすぎず、公開型の生成と検証は実物を使う。

Project_Demi配下に `0.070`、`816`、`936`、`4000 / 65535`、`1 / 4096` によるIMU raw換算が存在しないことも静的検査またはレビューで確認する。

## 6. 実機試験

### 6.1 記録必須項目

- 実施日時とタイムゾーン
- Project_Demiコミット
- Python版
- swbt-python版
- Bumble版
- PySide6版、Qt版
- OSと版
- USB Bluetoothアダプター
- USB VID/PID
- ドライバー
- アダプターID
- 対象機器とファームウェア
- ボンド新規または再利用
- 試験結果
- 既知の異常

### 6.2 Pro Controller基本

- 新規ペアリング
- 保存済みボンド再接続
- 切断と再接続
- A/B/X/Y
- L/R/ZL/ZR
- Plus/Minus/Home/Capture
- 十字キー
- 左右スティック全方向
- スティック押下
- ジャイロ3軸
- ニュートラル
- 色情報
- アダプター抜去
- 対象機器側切断

### 6.3 安全性

- キー保持中のF12
- キー保持中のフォーカス喪失
- マウス移動中の設定画面
- UIワーカー停止を模した停止監視
- 接続中のアプリ終了
- 色変更再接続
- 接続失敗後の終了

## 7. 性能試験

診断ビルドで次を収集する。

- 入力評価間隔の平均、95、99パーセンタイル
- Qt描画時間
- offer_frameからapply開始までの遅延
- 未処理フレームの置換回数
- 監視誤発火回数
- 常駐メモリ
- アイドルCPU
- 捕捉中CPU

初期目標:

| 指標 | 目標 |
|---|---|
| 入力評価95% | 16ms以下 |
| フレームキュー | 最大1 |
| UI停止監視 | 250ms以上で発火、200ms未満で発火しない |
| アイドルCPU | 対象環境で継続観測し、異常な1コア占有がない |
| メモリ | 長時間操作で単調増加しない |

CPUとメモリの絶対上限はパッケージ化後の実測で設定する。

## 8. 品質ゲート

```bash
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
uv run pytest tests/unit
uv run pytest tests/integration
```

全機材不要試験:

```bash
uv run pytest -m "not hardware and not bumble"
```

カバレッジは数値だけを目的にしないが、次の中心モジュールは分岐を含め90%以上を目標とする。

- `demi.domain`
- `demi.input.mapper`
- `demi.input.mouse_rotation_mapper`
- `demi.input.rotation_intent`
- `demi.input.rotation_pose_model`
- `demi.config`
- `demi.application.coordinator`

## 9. 回帰fixture

既定プロファイルと反転入力の操作列をfixture化する。

```text
press W
press D
release W
release D

press F
press alternate-A
release F
release alternate-A

mouse dx/dy sequence
normal button binding: released -> pressed -> released
inverted button binding: pressed -> released -> pressed
capture release with inverted binding -> neutral
```

fixtureには入力列、設定、期待する `ControllerFrame` だけを記録し、外部実装のコードへ依存させない。

## 10. CI

- Python 3.12と3.13
- Windows、macOS、Linux
- unit/integrationをOS行列で実行
- UI試験は仮想表示またはOSランナーで安定する範囲だけ
- ハードウェア試験はセルフホストまたは手動
- ロックファイル差分を検査
- リリース候補ではOS別パッケージ起動試験を行う
