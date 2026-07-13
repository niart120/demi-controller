# ControllerRuntime の中断可能な終了処理 仕様書

## 1. 概要

### 1.1 目的

接続、ペアリング、色変更による再接続などの adapter I/O が進行中でも、`ControllerRuntime.close()` がその処理の設定 timeout を待たずに worker を停止できるようにする。

終了要求を通常 command の後ろで待たせず、進行中の処理の中断、adapter の後処理、`RuntimeStopped` の通知、event loop の終了、thread join までを一つの終了契約として扱う。worker thread の daemon 属性やプロセス終了を正常な後処理の代替にしない。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| GitHub Issue #13 | 接続・ペアリング中でも `ControllerRuntime` を確実に停止し、遅延 event と worker thread の残留を防ぐ | `https://github.com/niart120/demi-controller/issues/13` |
| lifecycle | 終了要求時の neutral、`Shutdown`、adapter close、`RuntimeStopped`、thread join の順序 | `spec/initial/lifecycle.md` |
| architecture | `ControllerPort.close()` と ordered command / latest-frame の worker 境界 | `spec/initial/architecture.md` |
| swbt integration | `ControllerCommand`、`RuntimeEvent`、rest state、adapter 所有権 | `spec/initial/swbt-integration.md` |
| completed Unit 005 | runtime の dedicated thread、asyncio loop、冪等な close、後処理の基礎契約 | `spec/complete/unit_005/CONTROLLER_RUNTIME.md` |
| completed Unit 011 / Issue #12 | application shutdown から runtime close / join を呼ぶ本番配線 | `spec/complete/unit_011/APPLICATION_ASSEMBLY_AND_GUI_WIRING.md` |
| implementation before Unit 012 | command を直列に `await` した後で次の command を読むため、長時間処理中は `Shutdown` を取得できなかった | `src/demi/controller/runtime.py` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| application shutdown | 保存済み接続が timeout 待ちの間に `close()` を呼ぶ | 接続処理を中断し、adapter の後処理と thread join を完了して戻る | 接続 command の timeout 満了を待たない |
| application shutdown | 新規ペアリングが待機中に `close()` を呼ぶ | ペアリングを中断し、通常の pairing error を UI へ通知せず停止する | 部分的な bond の扱いは adapter 契約を変更しない |
| settings shutdown | 色変更による再接続中に `close()` を呼ぶ | 再接続を中断し、後続の `CONNECTED` / `READY` を発行せず停止する | capture を再開しない |
| input / command producer | shutdown 開始後に frame または command を送る | adapter へ適用されず、呼び出し側が拒否を観測できる | queue や mailbox に終了後の仕事を残さない |
| repeated caller | 同じ runtime に `close()` を複数回呼ぶ | 最初の呼び出しと同じ停止完了を待ち、停止済みなら何もしない | adapter 後処理と `RuntimeStopped` は一度だけ |
| runtime cleanup | rest、disconnect、close の一部が失敗する | 残りの後処理、停止通知、thread 終了を続行する | 後処理失敗は cancellation と区別する |

## 2. 対象範囲

- `ControllerRuntime` の停止開始状態と、複数 thread からの `close()` を冪等に扱う同期境界
- command queue の順番に依存せず、worker event loop へ終了要求を通知する経路
- `connect_saved()`、`start_pairing()`、`recreate_with_colors()` を含む進行中 adapter operation の task 管理と cancellation 回収
- shutdown 開始後の command 受付拒否、frame 受付拒否、adapter 適用抑止
- cancellation と接続失敗を分離し、shutdown による `ControllerError`、`CONNECTED`、`READY` の遅延通知を抑止する処理
- rest state、disconnect、adapter close を順番に最善努力で実行する処理
- adapter 後処理後の `RuntimeStopped` 一回通知、event loop 終了、thread join
- worker thread の daemon 属性に依存しない明示的な生存期間
- fake adapter を使った unit test と runtime / application shutdown の integration test

## 3. 対象外

- pyglet の描画、widget、focus、modal の操作性
- GUI toolkit の選定または置き換え
- PyInstaller、standalone artifact、console / windowed 設定
- Bluetooth または Switch 実機での接続品質、接続時間、ペアリング成功率
- `ControllerAdapter` または swbt-python の公開 API 変更
- 接続、ペアリング、色変更そのものの成功時仕様
- application shutdown における設定保存順序の変更
- 強制的な thread kill やプロセス強制終了の導入

## 4. 関連 docs

- `spec/initial/lifecycle.md`
- `spec/initial/architecture.md`
- `spec/initial/swbt-integration.md`
- `spec/initial/testing.md`
- `spec/complete/unit_005/CONTROLLER_RUNTIME.md`
- `spec/complete/unit_011/APPLICATION_ASSEMBLY_AND_GUI_WIRING.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| 接続中に停止する | `connect_saved()` が未完了の状態で別 thread から `close()` | 進行中処理を cancel して回収し、指定された接続 timeout の満了前に後処理と join を完了する | fake adapter の受理通知を待ってから停止を開始する |
| ペアリング中に停止する | `start_pairing()` が未完了の状態で `close()` | pairing task を cancel して回収し、`PAIRING_TIMEOUT` や `UNEXPECTED` を発行せず停止する | cancellation は shutdown 制御であり接続失敗ではない |
| 色再接続中に停止する | `recreate_with_colors()` が未完了の状態で `close()` | 再接続 task を cancel して回収し、`CONNECTION_LOST`、`CONNECTED`、`READY` を発行せず停止する | shutdown 開始前に発行済みの event は取り消さない |
| 新しい仕事を拒否する | shutdown 開始後に `post()` または `offer_frame()` | `post()` は `RuntimeError`、`offer_frame()` は `False` を返し、adapter 呼び出し回数を増やさない | 停止完了後も同じ契約とする |
| 進行中の frame 適用を止める | `apply_frame()` 待機中に shutdown | frame operation を cancel して回収し、mailbox の後続 frame を適用しない | rest state は終了処理として別に試行する |
| 順序付きで後処理する | shutdown が adapter を所有している | rest state、disconnect、close の順に各処理を一度ずつ試行する | 未接続時は適用不能な rest / disconnect を省略できる |
| 後処理失敗後も停止する | rest、disconnect、close のいずれかが例外を送出 | 失敗を記録し、実行可能な残りの段階、`RuntimeStopped`、event loop 終了、join へ進む | cancellation だけでは `ControllerError` を発行しない |
| 停止を一度だけ通知する | 正常終了、operation cancellation、後処理失敗 | adapter 後処理が終わった後に `RuntimeStopped` を一度だけ発行する | 通知後に `ConnectionChanged(CONNECTED/READY)` を発行しない |
| close を冪等にする | 同時または逐次の複数 `close()`、停止済み runtime の `close()` | adapter 後処理を重複させず、各呼び出しが停止済み状態を観測して戻る | `close()` が戻った時点で `is_alive` は `False` |
| 非 daemon thread を終了する | `start()` 後に通常の終了経路を実行 | worker thread は daemon 属性に依存せず、明示停止と join で終了する | thread を外部から強制終了しない |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-skipped | 待機中の `connect_saved()` を `close()` が中断し、120 秒の command timeout を待たず 1 秒以内に `is_alive == False` で戻る | regression | unit | 5 秒後の `RuntimeError` を red で確認後、専用 shutdown event と task cancellation で green |
| refactor-skipped | 待機中の `start_pairing()` を停止しても pairing / unexpected の `ControllerError` を発行しない | regression | unit | 共通 operation cancellation 実装後に追加し、初回 green。`RuntimeStopped` 1 件、`ControllerError` 0 件 |
| refactor-skipped | 待機中の `recreate_with_colors()` を停止した後に `CONNECTED` / `READY` が追加発行されない | regression | unit | 共通 operation cancellation 実装後に追加し、初回 green。停止開始後の event suffix を確認 |
| refactor-skipped | shutdown 開始後の `post()` と `offer_frame()` が拒否され、adapter へ command / frame が渡らない | edge | unit | 停止処理中と停止完了後を Event で分け、両方で初回 green |
| refactor-skipped | 待機中の `apply_frame()` を停止し、後続 mailbox frame を適用しない | edge | unit | active frame の cancellation と後続 sequence の非適用を確認。終了用 rest は別に許可 |
| refactor-skipped | rest、disconnect、close を順序付きで試行し、各段階の失敗後も残りの後処理と thread 終了へ進む | regression | unit | 3 失敗位置を parameterize し、全ケース初回 green |
| refactor-skipped | cancellation と後処理を終えた後に `RuntimeStopped` を一度だけ発行する | regression | unit | pairing cancellation、各 cleanup failure、重複 close で通知数 1 件を確認 |
| refactor-skipped | 同時および逐次の `close()` が冪等で、全呼び出しの完了後に `is_alive == False` となる | edge | unit | 4 thread の同時 close と停止後 close が初回 green。adapter close 1 回 |
| refactor-skipped | worker thread が non-daemon であり、application shutdown 経路から接続待機を中断して join できる | regression | integration | 実 runtime と `ApplicationShutdownCoordinator` の統合 test が初回 green |

1 秒は fake adapter を使う回帰テストの待機上限であり、Bluetooth 機材に対する性能保証ではない。テストは operation 開始を Event で同期し、接続 timeout を短く書き換えて見かけ上通す方法を使わない。

## 7. 設計メモ

### 7.1 着手時に確認した事実

- 着手時の `close()` は `Shutdown` を command queue へ追加し、worker thread を最大 5 秒 join していた。
- 着手時の worker は command を取得後、対応する adapter coroutine を完了まで `await` してから次の command を取得していた。
- 接続設定の timeout は最大 120 秒であり、command 処理中の `Shutdown` は join 上限内に取得されない場合がある。
- 着手時の worker thread は `daemon=True` だった。
- `_shutdown_adapter()` は rest state、disconnect、close を個別に最善努力し、最後に `RuntimeStopped` を発行する。

### 7.2 採用する設計方針

- runtime は「稼働中」「停止開始済み」「停止完了」を thread-safe に判定し、停止開始を一度だけ確定する。
- shutdown 通知は ordered command queue の消費を待たず、`call_soon_threadsafe()` で worker event loop を起こせる専用経路を持つ。
- worker は通常の adapter I/O を明示的な operation task として追跡する。shutdown を受けた場合は task を cancel し、`CancelledError` を回収してから後処理へ進む。
- operation task の具体的な helper 名や保持フィールド名は固定しない。テストは task の内部構造ではなく、中断、event、adapter 呼び出し、thread 生存状態を観測する。
- shutdown 開始フラグは producer 側の受付判定と worker 側の adapter 適用直前判定の両方で使い、受付との競合で遅れて投入された仕事も適用しない。
- worker thread は通常 thread とし、`close()` の明示停止と join を正常終了の唯一の経路にする。

### 7.3 未検証事項

- `SwbtControllerAdapter` 配下の各 await が asyncio cancellation をどの時点で受け取るかは未検証である。本 unit の自動テストは fake adapter で runtime 契約を固定し、実機での cancellation 特性は対象外とする。
- cancellation 後に swbt-python が部分的な bond file を残すかは未検証である。本 unit では bond file の形式、削除、修復契約を変更しない。
- cleanup coroutine 自体が cancellation に応答しない場合の強制停止手段は定義しない。既存 adapter 契約どおり各 coroutine が event loop へ制御を返すことを前提とし、thread kill は導入しない。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `spec/complete/unit_012/CONTROLLER_RUNTIME_CANCELLABLE_SHUTDOWN.md` | new | Issue #13 の作業境界、終了契約、TDD Test List、検証結果 |
| `spec/initial/architecture.md` | modify | ordered command と queue 外 shutdown signal の worker 境界 |
| `spec/initial/lifecycle.md` | modify | operation cancellation、後処理、non-daemon thread join の終了順序 |
| `src/demi/controller/runtime.py` | modify | shutdown 状態、operation cancellation、受付拒否、non-daemon thread、join 完了 |
| `tests/unit/controller/test_runtime.py` | modify | adapter operation 待機中の cancellation、後処理、event、冪等性の回帰試験 |
| `tests/integration/controller/test_runtime_shutdown.py` | new | application shutdown から待機中 runtime を停止する結合試験 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/unit/controller/test_runtime.py::test_close_cancels_a_waiting_saved_connection_without_waiting_for_timeout -q` | red then passed | red は 5 秒 join 後の `RuntimeError`。green は 1 passed in 0.05s |
| `uv run pytest tests/unit/controller tests/integration/controller -q` | passed | 42 passed in 0.33s |
| `uv sync --dev` | passed | 74 packages resolved、71 packages checked |
| `uv lock --check` | passed | 74 packages resolved |
| `uv run ruff format --check .` | passed | 91 files already formatted |
| `uv run ruff check .` | passed | no findings |
| `uv run ty check --no-progress` | passed | no findings |
| `uv run pytest -o cache_dir=.tmp/pytest-cache-unit --basetemp=.tmp/pytest-unit-012 tests/unit` | passed | 197 passed in 0.36s。既定 cache / `%TEMP%` の環境権限を避けるため workspace 内の一時領域を指定 |
| `uv run pytest -o cache_dir=.tmp/pytest-cache-integration --basetemp=.tmp/pytest-integration-unit-012 tests/integration` | passed | 16 passed in 0.28s |
| `uv build` | passed | `demi_controller-0.1.0.tar.gz` と `demi_controller-0.1.0-py3-none-any.whl` を生成 |
| `git diff --check` | passed | whitespace error なし。Windows の LF / CRLF 変換予告のみ |

## 10. 先送り事項

- none

## 11. チェックリスト

- [x] Issue #13、関連する初期仕様、既存 runtime、既存 test を確認した
- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を観測可能な振る舞いで作成した
- [x] TDD Test List の各項目を green にし、refactor 要否を確認した
- [x] 標準 gate と対象 integration test の結果を記録した
- [x] runtime 公開メソッドの docstring を停止契約と整合させ、package metadata 非変更でも package gate を実行した
- [x] 実装完了後に `spec/complete/unit_012` へ移動した
