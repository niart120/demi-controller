# CI 応答性 probe のタイマー精度 仕様書

## 1. 概要

### 1.1 目的

`NFR-001` の「接続、列挙、切断でQtのGUIスレッドを100ミリ秒以上連続して塞がない」という契約を維持したまま、macOS CI の応答性 probe で100ミリ秒を超えた経路を時刻付きで特定する。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| 応答性要件 | 接続、列挙、切断でGUIスレッドを100ミリ秒以上連続して塞がない | `spec/initial/requirements.md` |
| CI 観測 | macOS / Python 3.12 の integration test で、10ミリ秒 timer の最大間隔が109.6msと115.0msになり失敗した | GitHub Actions run 29423489228 / 29421807099 |
| 観測器の実装 | 応答性 probe は10ミリ秒の `QTimer` を既定の timer type のまま起動する | `tests/integration/ui/test_application_lifecycle.py` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| CI maintainer | macOS上で遅延runtimeの応答性 probe を実行する | 100ミリ秒の応答性契約を同じ閾値で検査する | 観測用timerの精度だけを変更する |
| maintainer | 精密timer化後のCI結果を確認する | 失敗時にworker、bridge、GUIのどの境界で待機したかを取得する | runtime fake、bridge、production UIを同時に変更しない |

## 2. 対象範囲

- `test_qt_event_loop_stays_responsive_during_slow_runtime_operations` の観測用 `QTimer` を `Qt.TimerType.PreciseTimer` に設定する。
- 同テストでworker開始・起床・イベント送出、GUI timer tick・接続要求・window refreshの単調時刻を記録する。
- 既存の10ミリ秒 interval、100ミリ秒の最大間隔判定、接続状態遷移の確認を維持する。
- 対象テスト、静的検査、macOS CI の結果を記録する。

## 3. 対象外

- 100ミリ秒の応答性要件またはテスト閾値の緩和。
- `SlowRuntime` の短命workerを持続workerへ置き換える変更。
- `QtRuntimeEventBridge`、`QtApplicationEventRouter`、`ControllerRuntime`、CI matrixの変更。
- 実Bluetooth接続中の応答性測定。

## 4. 関連 docs

- `spec/initial/requirements.md`
- `spec/initial/testing.md`
- `spec/initial/lifecycle.md`
- `spec/complete/unit_017/QT_RUNTIME_AND_LIFECYCLE_INTEGRATION.md`
- `spec/complete/unit_018/QT_QUALITY_AND_OS_ACCEPTANCE.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| precise response probe | 遅延runtimeの接続、切断をQt event loopで処理する | 観測timerが `PreciseTimer` として起動する | 10ミリ秒 intervalを維持する |
| unchanged responsiveness contract | 隣接した観測tickを比較する | 最大間隔は100ミリ秒未満でなければ失敗する | 閾値を変更しない |
| staged diagnosis | macOS CI がなお失敗する | assertion messageにworker、GUI操作、refreshの時刻順を出力する | この段では原因を断定しない |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| partial | 応答性 probe は精密timerを使いつつ、既存の100ミリ秒契約と接続・切断シーケンスを維持する | regression | integration | Windows offscreenで20回連続成功。macOS 3.12では2回成功後、`PreciseTimer`設定済みで187.0msに再発したため、timer種別だけでは不十分 |
| todo | macOS CIの失敗時にworker送出、GUI操作、refreshの時刻順を出力する | diagnostic regression | integration | productionの実行経路は変えず、assertion messageだけに観測結果を載せる |

## 7. 設計メモ

Qtの既定 `CoarseTimer` は観測器のtimer typeであり、本番のworker-to-GUI配送の速度を直接改善しない。実際に `PreciseTimer` 設定済みで187.0msの失敗が再発したため、timer種別を原因とは断定できない。次段はproductionの挙動を変えず、workerとGUI境界の時刻を失敗ログに出して待機箇所を特定する。

| Test Desiderata | 判断 | 根拠 |
|---|---|---|
| precise | 維持 | 最大100ミリ秒というNFR-001の判定を残す |
| deterministic | 未達 | 精密timer化後もmacOS 3.12で187.0msを検出。次段は失敗時の時刻列を取得する |
| representative | 未解決 | `SlowRuntime` の短命workerはproductionの持続workerと一致しない。第1段では同時に変えない |
| fast | 維持 | 対象テストはWindows offscreenで約0.3秒、20回反復も短時間で完了する |

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `tests/integration/ui/test_application_lifecycle.py` | modify | 応答性 probe の観測timerを精密timerへ設定する |
| `spec/wip/unit_021/CI_RESPONSE_TIMER_PRECISION.md` | new | 対象範囲、TDD状態、検証、次段の条件を記録する |

## 9. 検証

| command | result | notes |
|---|---|---|
| GitHub Actions run 29423489228 / 29421807099 | failed | macOS / Python 3.12だけで既定timerの100ミリ秒判定が失敗した |
| `uv run pytest tests/integration/ui/test_application_lifecycle.py::test_qt_event_loop_stays_responsive_during_slow_runtime_operations -q -p no:cacheprovider` | passed | `QT_QPA_PLATFORM=offscreen` でPowerShellから20回反復し、Windowsで各回0.32〜0.38秒 |
| `uv sync --dev` / `uv lock --check` / `uv run ruff format --check .` / `uv run ruff check .` / `uv run ty check --no-progress` | passed | 77 packages、127 files、全静的検査が通過 |
| `uv run pytest tests/unit` / `$env:QT_QPA_PLATFORM='offscreen'; uv run pytest tests/integration` | passed | unit 197 passed、integration 67 passed |
| `uv build` / `git diff --check` | passed | sdistとwheelを生成、whitespace errorなし |
| GitHub Actions run 29425872544 の macOS / Python 3.12 | failed | 精密timer化後の1回目と2回目は成功、3回目は最大187.0msで失敗 |

## 10. 先送り事項

- 時刻列でworker起床、bridge配送、GUI refreshのどこに待機があるかを確認してから、runtime fake、bridge、GUIのいずれを変えるかを選ぶ。
- 実Bluetooth接続中の100ミリ秒応答性はhardware acceptanceで扱う。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を更新した
- [x] 検証結果または未実行理由を更新した
- [x] package / release / public API に触れないことを確認した
