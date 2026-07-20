# Direct入力フレーム送信 仕様書

## 1. 概要

### 1.1 目的

Project_Demi が入力reportの送信契機を所有するため、swbt-pythonの周期送信型から `DirectProController` へ移行する。接続中に送信が入力評価より遅い場合も、ボタン・スティック・加速度は最新状態を使い、ジャイロの3軸角変位は集約前後で保存する。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| GitHub Issue #44 | Direct送信、送信完了、ライフサイクル、配送境界の要求 | `https://github.com/niart120/demi-controller/issues/44` |
| upstream Issue #77 | `DirectProController.send(state)` の公開契約 | `https://github.com/niart120/swbt-python/issues/77` |
| 承認済み設計方針 | 上限なしの定数サイズ集約、診断記録、send時間切れなし | この作業対話 |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| InputPublisher | workerが前frameを送信中に複数frameを生成する | 次の送信は最新のボタン・スティック・加速度と、保存された3軸角変位を持つ | GUIスレッドを待たせない |
| ControllerRuntime | 接続成功 | 初期rest frameの送信成功後だけ `CONNECTED` を通知する | 接続初期0G診断例外を維持する |
| ControllerRuntime | send失敗、watchdog、切断、終了、色再生成 | restとcloseのneutral reportを重複させず、安全な状態へ戻る | 失敗したframeを暗黙再送しない |
| 実機操作者 | マウスでカメラを操作する | Direct送信の実機結果を記録し、送信時系列または操作感の未解決事項を後続Issueへ分離する | Bluetooth互換性は保証しない |

## 2. 対象範囲

- `swbt-python>=0.4.0,<0.5.0` と `DirectProController` への依存更新。
- `apply_frame()` から、送信完了を表す `send_frame()` への境界変更。
- 評価時間を持つ `ControllerFrame` と、最新状態・角変位集約を分けた配送境界。
- 接続初期、watchdog、切断、shutdown、色再生成のrest/close規則。
- 集約数、時間、sequence範囲、安全境界による破棄の診断記録。
- unit、integration、package、実機確認。

## 3. 対象外

- マウス感度、再標本化、`RotationPoseModel` の計算式、3 IMU slot生成方式の変更。
- raw mouse eventをworkerへ直接渡す入力経路への変更。
- Joy-Con Direct型、macro、replay、sequence runner、Bluetooth互換性の保証。
- 集約時間・評価数に基づく切断、警告UI、Project_Demi側のsend時間切れ。

## 4. 関連 docs

- `spec/initial/architecture.md`
- `spec/initial/swbt-integration.md`
- `spec/initial/lifecycle.md`
- `spec/initial/input.md`
- `spec/initial/testing.md`
- `spec/initial/risks.md`
- `spec/complete/unit_006/SWBT_ADAPTER.md`
- `spec/complete/unit_024/SMOOTH_MOUSE_GYRO.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| Direct依存境界 | adapterを生成する | `DirectProController` を生成し、`report_period_us` を渡さない | swbtの公開root exportだけを使う |
| frame評価時間 | InputPublisherがframeを作る | 角速度を求めた実際の評価時間を `sample_duration_ns` に持たせる | 初回・epoch境界の0時間は許可する |
| 通常送信 | workerが追従する | 評価frameごとに完全`InputState`を1回`send()`し、完了後に次へ進む | 内容同値による省略はしない |
| 送信中の集約 | 複数frameが同一送信中に届く | 最新のbuttons/sticks/accelと、`Σ(gyro_rate × sample_duration)` を次の送信対象にする | button edgeは保持しない |
| 集約不変条件 | 正の評価時間を持つ複数frame | 集約後の `gyro_rate × coalesced_duration` が軸ごとの合計に一致する | 浮動小数点比較は許容差を使う |
| 集約量 | producerがsend能力を継続して上回る | pendingは定数サイズのまま集約を継続し、集約数・時間・sequence範囲を診断へ記録する | 上限、警告、切断を設けない |
| epoch安全境界 | 新しいcapture epoch、watchdog、切断、終了 | 以前のpending角変位を送らず、破棄数と理由を診断へ記録する | 既に開始したsendは取り消さない。ただしshutdownは取消可能 |
| 初期rest | connect/reconnect成功 | rest frameの`send_frame()`成功後だけ`CONNECTED` | 失敗時は接続成功として公開しない |
| 送信失敗 | `send_frame()`が失敗 | 後続frameを送らず、暗黙再送なしで既存分類のerror/recoveryへ進む | in-flight集約値を戻さない |
| watchdog | 250msで捕捉frameが途絶える | rest送信成功後だけ`WatchdogNeutralized`を通知する | 失敗は`CONNECTION_LOST`として回復する |
| 終了規則 | disconnect/shutdown/color recreate | rest送信成功後は`close(neutral=False)`、rest送信失敗時だけ`close(neutral=True)`を試す | 元の失敗分類を置換しない |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| done | runtime dependencyがswbt-python 0.4系で、Direct公開型をroot importできる | new | package | `uv lock --check` と公開root importを確認した |
| done | 通常adapter factoryがDirectProControllerを生成し、report periodを渡さない | new | unit | 周期送信constructor経路を削除した |
| done | InputPublisherが評価に使った時間を非負のsample durationとしてframeへ記録する | new | unit | catch-up時の設定周期を含む |
| done | 集約境界が最新の持続状態と3軸角変位を保持し、単一frameでは元のrateを再現する | new | unit | display latestとpendingを分離する |
| done | 複数評価を集約しても軸ごとの角変位が保存される | new | unit | 不規則間隔と方向反転を含む |
| done | 同一集約窓のbutton edgeは保持せず、最新stateを送信する | new | unit | 最新frameの持続状態を使う |
| done | stale sequenceを拒否し、新epochと安全境界がpendingを破棄して理由を記録する | edge | unit | in-flight sendは再送しない |
| done | 集約量が増えても定数サイズを保ち、診断最大値を更新する | new | unit | 集約区間と安全境界をDEBUG記録する |
| done | ControllerFrame1件が完全InputState1件へ変換され、send完了までadapter呼び出しが完了しない | new | unit | fake Direct gamepadを使う |
| done | 接続初期restの成功後だけCONNECTEDとなり、send失敗ではREADYへ回復する | regression | integration | 0G診断例外を維持する |
| done | send中の複数評価が次の1送信へ集約され、送信列に重複や暗黙再送がない | new | integration | blockable fake adapterを使う |
| done | send失敗後は後続frameを送らず、既存の安全な回復を行う | regression | integration | error分類を確認する |
| done | watchdog、disconnect、shutdown、色再生成でrestとclose neutralを重複送信しない | regression | integration | rest失敗時だけneutral=true |
| done | Direct移行後もworker shutdownが5秒以内に終了し、送信taskを残さない | regression | integration | active send取消を含む |
| done | Direct送信の操作結果をSwitch実機で記録する | new | hardware | pairing、接続、切断、F→Aの送信経路を記録した。ジャイロのカクつきは #45 で追跡する |

## 7. 設計メモ

`ControllerFrame` は表示と送信候補の両方に使う。表示用latestは各評価で置換するが、送信用pendingは完全frameをFIFO化しない。workerが1件を送信している間だけ、次のpendingへ最新の持続状態と角変位の和を集約する。

`sample_duration_ns` は `monotonic_ns` の差分から再計算しない。InputPublisherが同時刻catch-upで設定周期を使うため、角速度計算に使った時間そのものを保存する必要がある。

自動試験ではProject_Demi内の3軸角変位を保証する。標準IMU reportへProject_Demiの評価時間を渡す公開swbt APIはないため、Switch側で同じ角変位として解釈されることは実機試験で確認する。実機確認は自動試験の代替ではない。

pendingのメモリ量はframe数に比例しない。累積角変位、累積時間、最新state、統計だけを保持する。集約数・時間を理由に接続を切らず、DEBUGの集約区間記録と終了時INFO集計で送信能力不足を観測する。

runtimeがProject_Demi rest frameの送信成否を判断し、adapterは指定された`neutral`値でswbtのcloseを呼ぶ。色再生成はrest送信成功後だけ実行する。send失敗では追加frameを送らず、closeのneutral fallbackだけを最善努力で行う。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `pyproject.toml`, `uv.lock` | modify | swbt-python 0.4系へ更新 |
| `src/demi/domain/controller.py` | modify | sample duration契約 |
| `src/demi/input/publisher.py` | modify | 実評価時間をframeへ記録 |
| `src/demi/controller/mailbox.py` | modify | latestと角変位集約のthread-safe境界 |
| `src/demi/controller/{adapter,swbt_adapter,runtime}.py` | modify | Direct送信、worker順序、lifecycle |
| `src/demi/app.py` | modify | report period配線削除 |
| `tests/unit/controller/*`, `tests/unit/input/test_publisher.py` | modify | unit契約 |
| `tests/integration/controller/*` | modify | runtimeとlifecycle契約 |
| `spec/initial/*.md`, `spec/hardware-test-log.md` | modify | 現行契約と実機結果 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/unit/controller/test_swbt_dependency.py -q` | passed | 1 passed。Direct公開型と0.4系を確認 |
| `uv run pytest tests/unit/controller/test_swbt_adapter.py -q` | passed | 4 passed。Direct送信とconstructor境界を確認 |
| `uv run pytest tests/unit/controller/test_swbt_errors.py tests/unit/controller/test_runtime.py tests/unit/application/test_app.py -q` | passed | 41 passed。Direct送信名への移行後の分類とruntimeを確認 |
| `uv run pytest tests/unit/input/test_publisher.py -q` | passed | 28 passed。実評価時間、epoch境界、catch-upを確認 |
| `uv run pytest tests/unit/domain -q` | passed | 34 passed。frame metadataの非負検証を確認 |
| `uv run pytest tests/unit/controller/test_mailbox.py -q` | passed | 5 passed。最新state、角変位集約、安全境界破棄を確認 |
| `uv run pytest tests/integration/controller/test_runtime_commands.py tests/integration/controller/test_runtime_shutdown.py tests/integration/controller/test_swbt_lifecycle.py -q` | passed | 9 passed。Direct送信名への移行後の接続・終了を確認 |
| `uv run pytest tests/integration/ui/test_windows_raw_input_capture.py -q` | passed | 6 passed。入力captureからDirect送信変換を確認 |
| `uv lock --check` | passed | swbt-python 0.4.0を固定 |
| `uv run ruff format --check .` | passed | 146 files formatted |
| `uv run ruff check .` | passed | lint passed |
| `uv run ty check --no-progress` | passed | type check passed |
| `uv run pytest tests/unit -q -p no:cacheprovider --basetemp=tmp/pytest-unit-unit039-final` | passed | 294 passed |
| `$env:PYTHONUTF8='1'; uv run pytest tests/integration -q -p no:cacheprovider --basetemp=tmp/pytest-integration-unit039-final-network` | passed | 123 passed。package試験のbuildはネットワーク許可環境で実行 |
| `uv build` | passed | sdistとwheelを生成 |
| `git diff --check` | passed | final gate |
| docs quality review | passed | unit_039の完了移動、#45参照、未検証事項、仮テキストと空白エラーを確認 |
| Switch 2実機試験 | completed with follow-up | pairing、接続、切断、F→Aの送信経路を記録した。ジャイロのカクつきは未解決であり、#45 で時系列表現と実機操作感を追跡する。詳細は`spec/hardware-test-log.md` |

## 10. 先送り事項

- F→A: DEBUGログで、ポインター未捕捉時を含むF→Aの`send()`完了を記録した。`Start mouse`の有無でSwitch側の認識が異なる初回観測は残るが、#44 のDirect送信境界に未処理の実装項目はない。
- ジャイロ: Switch 2でカクつきを観測した。送信完了が評価周期を超えると複数frameが1件へ集約され、集約時間は公開`InputState`へ渡らない。因果関係、3 IMU slotの時系列表現、送信時間の計測は未検証である。
- 後続: [#45](https://github.com/niart120/demi-controller/issues/45) が、ジャイロのカクつきとDirect送信時のIMU時系列を追跡する。#45 は送信モデル変更またはswbt-python API拡張を決定する前に、計測と再現試験を行う。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を作成した
- [x] 全TDD itemをgreenまたは明示的にdeferredへ更新した
- [x] 初期仕様とpublic API docstringを更新した
- [x] package / release / public API のgateを記録した
- [x] 専用USB BluetoothドングルとSwitch実機の結果を記録した
- [x] #44 の実機結果を記録し、未解決のジャイロ操作感を #45 へ分離した
- [x] 検証結果または未実行理由を記録した
