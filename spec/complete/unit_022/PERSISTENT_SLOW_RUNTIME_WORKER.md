# 応答性 test fake の持続 worker 仕様書

## 1. 概要

### 1.1 目的

CI の応答性 probe で、GUI スレッドが command ごとに新しい worker を起動しないよう、`SlowRuntime` を起動時に1本だけ作る持続 worker と command queue に変更する。100ミリ秒の応答性契約は維持する。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user request | 閾値を緩める前に遅延そのものを減らす方法を先に検討する | 対話 2026-07-15 |
| 観測 | `PreciseTimer` 設定後も macOS / Python 3.12 で最大187.0ミリ秒を検出した | GitHub Actions run 29425872544 |
| production / test fake の差 | `ControllerRuntime` は起動時に dedicated worker と queue を作るが、`SlowRuntime` は command ごとに `Thread` を起動する | `src/demi/controller/runtime.py` / `tests/integration/ui/test_application_lifecycle.py` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| integration test | adapter列挙、接続、切断のcommandを順に送る | 1本の worker が順序を保って遅延結果を送出する | GUI スレッドは command を queue に入れるだけにする |
| CI maintainer | macOSで応答性 probe を実行する | 100ミリ秒の判定を同じまま再検証できる | 閾値と本番 runtime は変更しない |

## 2. 対象範囲

- `SlowRuntime` を、`start()` で1本の worker を開始し、`post()` で command queue へ送る test fake にする。
- worker は adapter列挙、接続、切断を投入順に処理し、既存の30ミリ秒遅延と production の `RuntimeEventSink` 配送を維持する。
- shutdown 時に queue を停止し、worker が終了していることを対象 test で確認する。
- 既存の10ミリ秒 interval と100ミリ秒の最大間隔判定を維持する。

## 3. 対象外

- 100ミリ秒の応答性要件またはテスト閾値の緩和。
- `ControllerRuntime`、`QtRuntimeEventBridge`、`QtApplicationEventRouter`、`MainWindow` の変更。
- 実Bluetooth接続、adapter実装、CI matrixの変更。
- unit_021 の失敗時時刻列を用いた原因断定。

## 4. 関連 docs

- `spec/initial/requirements.md`
- `spec/initial/testing.md`
- `spec/wip/unit_021/CI_RESPONSE_TIMER_PRECISION.md`
- `src/demi/controller/runtime.py`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| persistent worker startup | application が runtime を開始する | `SlowRuntime` は worker を1本だけ開始する | command前に起動する |
| ordered delayed commands | discover、connect、disconnect を順にpostする | worker が各commandを30ミリ秒遅延後に順序どおりのeventへ変換する | `RuntimeEventSink` は既存のproduction bridge |
| nonblocking GUI post | GUIで `session.connection_action()` を実行する | `post()` は thread を起動せず command をqueueへ入れる | worker数は1のまま |
| shutdown | windowを閉じる | workerを停止してjoinし、残存workerを残さない | 既存のshutdown順序を維持する |
| unchanged responsiveness contract | 隣接した観測tickを比較する | 最大間隔は100ミリ秒未満でなければ失敗する | 閾値を変更しない |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| green | 応答性 probe は3 command を処理しても worker を1本だけ使い、shutdown後にそのworkerを終了する | regression | integration | redで短命workerが3本になることを確認し、greenで1本かつ停止済みを確認 |
| green | 持続 worker 化後も接続・切断シーケンスと100ミリ秒判定を維持する | regression | integration | Windows offscreenで対象 test を20回連続実行して成功 |
| green | macOS / Python 3.12 CI が持続 worker 化後の応答性 probe を通過する | regression | integration | GitHub Actions run 29428003192 の初回と4回のjob再実行で連続成功 |

## 7. 設計メモ

これは production の遅延を直接測定した結論ではない。`SlowRuntime` の短命workerは、本番 `ControllerRuntime` の dedicated worker と queue に一致しないという事実に基づく、test fake の代表性とGUI側の起動負荷を改善する仮説である。macOS / Python 3.12 で5回連続成功したため、この限定したCI条件では仮説を支持する。再発時は unit_021 の時刻列を使う。

| Test Desiderata | 判断 | 根拠 |
|---|---|---|
| precise | 維持 | 最大100ミリ秒の判定を残す |
| deterministic | 改善を試行 | commandごとの thread 起動を排除する |
| representative | 改善を試行 | 本番と同じ起動時worker / queue の形に近づける |
| fast | 維持 | 既存の30ミリ秒遅延と1秒のfail-safeを維持する |

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `tests/integration/ui/test_application_lifecycle.py` | modify | `SlowRuntime` の持続 worker と worker数の回帰確認 |
| `spec/complete/unit_022/PERSISTENT_SLOW_RUNTIME_WORKER.md` | new | 対象範囲、TDD状態、検証、先送り事項 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/integration/ui/test_application_lifecycle.py::test_qt_event_loop_stays_responsive_during_slow_runtime_operations -q -p no:cacheprovider` | passed | `QT_QPA_PLATFORM=offscreen` でredを確認後、greenを20回連続確認 |
| `uv run ruff format --check tests/integration/ui/test_application_lifecycle.py` / `uv run ruff check tests/integration/ui/test_application_lifecycle.py` / `uv run ty check --no-progress` | passed | 対象fileのformat/lintと全体型検査が通過 |
| `uv run pytest tests/unit` / `$env:QT_QPA_PLATFORM='offscreen'; uv run pytest tests/integration` | passed | unit 197 passed、integration 67 passed |
| `uv build` / `git diff --check` | passed | sdistとwheelを生成、whitespace errorなし |
| GitHub Actions run 29428003192 の macOS / Python 3.12 | passed | 初回と4回のjob再実行が連続成功し、合計5回で100ミリ秒判定を通過 |

## 10. 先送り事項

- none

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を更新した
- [x] 検証結果または未実行理由を更新した
- [x] package / release / public API に触れないことを確認した
