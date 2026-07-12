# 接続ランタイム 仕様書

## 1. 概要

### 1.1 目的

pyglet 主スレッドから接続処理を分離し、専用 thread 上の asyncio event loop で controller adapter を所有する。順序が必要な command は queue、入力 frame は最新 1 slot、worker 停止は 250ms watchdog で扱う。unit_006 の swbt-python adapter が接続できる Protocol と、機材なしで動く fake adapter をここで固定する。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| roadmap | Unit 005 の成果と完了条件 | `spec/initial/roadmap.md` |
| architecture | thread 所有、asyncio queue、latest frame slot、event bridge | `spec/initial/architecture.md` |
| lifecycle | 起動、接続、切断、停止監視、終了順序 | `spec/initial/lifecycle.md` |
| swbt integration | command、RuntimeEvent、frame merge、watchdog | `spec/initial/swbt-integration.md` |
| requirements | NFR-001、NFR-002、NFR-005、AC-01〜AC-03 | `spec/initial/requirements.md` |
| testing design | FakeControllerPort、worker、frame discard、watchdog | `spec/initial/testing.md` |
| completed UI | CaptureCoordinator、ControllerFrame、ConnectionState | `spec/complete/unit_004/` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| UI main thread | `start()`、`post(command)`、`offer_frame(frame)`、`close()` | worker へ安全に渡り、main thread を block する接続処理を持たない | frame は全件 queue しない |
| runtime worker | ordered command | adapter 操作を順序どおり実行し、RuntimeEvent を event sink へ出す | adapter は worker thread だけが所有する |
| frame producer | sequence、capture epoch、capture_active | 新しい現行 session の frame だけを adapter へ apply する | stale sequence/epoch は破棄 |
| watchdog | connected、captured、最後の frame 受信時刻 | 250ms 以上停止すると rest を 1 回 apply し、通知する | 50ms 間隔、同じ停止中に反復しない |
| shutdown | close / Shutdown command | rest、adapter close、loop stop、thread join、RuntimeStopped の順で終わる | `os._exit` を使わない |

## 2. 対象範囲

- `ControllerCommand` の immutable command dataclass 群を定義する。
- `RuntimeEvent`、`ControllerErrorCategory`、adapter descriptor、接続状態 snapshot を定義する。
- `ControllerAdapter` Protocol と機材不要の `FakeSwbtAdapter` test double を定義する。
- `LatestFrameMailbox` を lock 保護し、sequence/epoch の stale frame を拒否する。
- `ControllerRuntime` の専用 thread、asyncio loop、command queue、frame event、start/close を実装する。
- 接続中だけ frame を adapter へ一括 apply し、未接続時は最新 frame を状態表示用に保持する。
- capture 外 frame は同一内容でも neutral transition として 1 回 apply する。
- 50ms worker watchdog と 250ms threshold、neutral apply、`WatchdogNeutralized` を実装する。
- event sink を注入し、UI event bridge や swbt-python を import しない。

## 3. 対象外

- swbt-python の実 package dependency、公開 API の実引数調査、Bumble、Bluetooth、Switch 本体。
- `InputState` / `Stick` / `IMUFrame` への実変換。Unit 006 の adapter/conversion 責務とする。
- pyglet event bridge への thread-safe post の具象実装。event sink Protocol までとする。
- adapter 列挙の OS / USB 実装。fake adapter の descriptor と command ordering のみ扱う。
- pairing UI、connection dialog、設定保存、GUI の接続ボタン。
- 実時間依存の長時間性能測定。threshold 判定は FakeClock で行う。

## 4. 関連 docs

- `spec/initial/roadmap.md`
- `spec/initial/architecture.md`
- `spec/initial/lifecycle.md`
- `spec/initial/swbt-integration.md`
- `spec/initial/requirements.md`
- `spec/initial/testing.md`
- `spec/complete/unit_004/UI_AND_PYGLET.md`
- `AGENTS.md`
- `SKILLS.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| command を受け付ける | `DiscoverAdapters`、connect、disconnect、status、shutdown | immutable command が順序を保って worker で処理される | `post()` は queue を無制限に増やす frame 経路ではない |
| runtime を開始する | clean な runtime | dedicated thread と asyncio loop を作り、READY event を出す | adapter factory は worker 内で呼ぶ |
| runtime を停止する | `close()` または `Shutdown` | rest、adapter close、loop stop、thread join、RuntimeStopped を完了する | close は冪等 |
| frame を保持する | sequence、epoch、内容 | 最新かつ現行 session の 1 frame だけを slot に保持する | sequence 以下、古い epoch は拒否 |
| frame を適用する | connected + accepted frame | adapter の一括 apply が最大 1 回実行される | 未接続なら apply せず latest は保持 |
| capture を解除する | `capture_active=False` frame | 内容が同じでも rest frame を 1 回 apply する | 次の active frame は新 epoch が必要 |
| command failure を分類する | adapter timeout / exception | retryable、category、diagnostic id 付き `ControllerError` を出す | stack trace は event に入れない |
| watchdog を監視する | connected、active、最後の受信時刻 | 200ms未満は何もせず、250ms以上で rest と event を 1 回出す | 50ms tick、同じ epoch で再発火しない |
| watchdog 後の frame を扱う | 同じ epoch / 新しい epoch | 同じ epoch の active frame は再送せず、新 epoch で明示再捕捉する | 自動再開しない |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-done | ControllerCommand、RuntimeEvent、error category、adapter descriptor が immutable typed value として表現される | new / edge | unit | 2 tests green。command ordering と public event payload の境界を固定 |
| todo | LatestFrameMailbox が sequence/epoch を判定し、最新 1 slot を thread-safe に保持する | new / edge | unit | stale sequence、stale epoch、future epoch、同一内容の capture release を確認 |
| todo | Watchdog が FakeClock で 200ms 未満を無視し、250ms 以上を一度だけ発火する | new / edge | unit | interval 50ms、epoch reset、connected/captured 条件を確認 |
| todo | ControllerRuntime が dedicated thread、asyncio loop、start/close、RuntimeStopped を扱う | new / regression | unit | 実 thread は短時間、join 後に alive/task 残りを確認 |
| todo | command queue が Discover/Connect/Disconnect/Status を順序どおり fake adapter へ渡す | new / integration | unit | adapter factory と event sink を注入し、worker thread 所有を確認 |
| todo | accepted frame が connected adapter へ一括 apply され、未接続では apply されない | new / integration | unit | latest frame slot、duplicate sequence、capture release を含む |
| todo | stale capture epoch/sequence が破棄され、watchdog 後の同 epoch active frame が再開しない | new / regression / edge | unit | 新 epoch の明示 frame だけ再開を許可 |
| todo | runtime の全 gate、thread cleanup、package smoke が通る | characterization | package | lock、format、lint、ty、unit、build、wheel contents を含める |

## 7. 設計メモ

- `ControllerRuntime` は `ControllerPort` Protocol を満たし、main thread からは `post` / `offer_frame` のみを呼ぶ。
- `post()` は worker loop の `asyncio.Queue` へ `call_soon_threadsafe` で投入する。`offer_frame()` は lock 保護 mailbox を更新し、frame event を set する。
- adapter は runtime worker thread 内で生成・接続・切断・破棄する。main thread に adapter object を返さない。
- `LatestFrameMailbox` は現在 epoch と最後の sequence を持つ。future epoch を新 session として受け入れるのは UI の明示 capture epoch 更新を frame が伝えるためで、過去 epoch は必ず拒否する。
- adapter には `apply_frame(ControllerFrame)` を渡す。Unit 006 がこの境界で swbt の `InputState` へ変換し、Unit 005 は Project_Demi domain frame のまま fake へ渡す。
- `FrameWatchdog` は clock を注入し、last received time と tripped epoch を保持する。timeout 後は同じ epoch の active frame を adapter へ再送しない。
- event sink の呼び出し元は worker thread である。pyglet main thread への dispatch は Unit 004 の event bridge または後続 coordinator が所有する。
- shutdown は command queue の順序を守り、close 呼び出しが worker を直接 kill しない。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/controller/__init__.py` | new | controller runtime package |
| `src/demi/controller/commands.py` | new | immutable command values |
| `src/demi/controller/events.py` | new | RuntimeEvent、error category、descriptor |
| `src/demi/controller/adapter.py` | new | ControllerAdapter Protocol |
| `src/demi/controller/mailbox.py` | new | latest frame slot、sequence/epoch 判定 |
| `src/demi/controller/watchdog.py` | new | FakeClock 対応 watchdog |
| `src/demi/controller/runtime.py` | new | worker thread、asyncio loop、queue、apply |
| `tests/unit/controller/` | new | command/event/mailbox/watchdog behavior |
| `tests/integration/controller/` | new | fake adapter と runtime thread boundary |
| `spec/complete/unit_005/CONTROLLER_RUNTIME.md` | new / modify | TDD 状態、検証、完了記録 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/unit` | not run | unit_005 implementation 前の baseline は unit_004 merge 時点で 92 passed |
| `uv run pytest tests/unit/controller/test_contracts.py` | passed | 2 passed |
| `uv run ruff format --check src/demi/controller tests/unit/controller` | passed | 4 files already formatted |
| `uv run ruff check src/demi/controller tests/unit/controller` | passed | All checks passed |
| `uv run ty check --no-progress` | passed | All checks passed |
| `uv lock --check` | not run | package metadata は変更しない予定だが final gate で確認する |
| `uv build` | not run | final package gate で確認する |
| `uv run pytest tests/integration` | not run | fake runtime integration tree を作成後に実行する |

## 10. 先送り事項

- swbt-python の実公開 API による adapter/conversion は Unit 006 へ送る。
- UI event bridge の pyglet main-thread dispatch は後続 coordinator integration で扱う。
- 実 Bluetooth の接続、pairing、watchdog は Unit 008 の hardware test まで未検証とする。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を作成した
- [ ] 検証結果または未実行理由を実装後に更新した
- [ ] package / release / public API に触れる場合の gate を記録した
