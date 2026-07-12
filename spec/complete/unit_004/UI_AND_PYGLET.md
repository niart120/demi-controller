# pyglet ウィンドウと可視化 仕様書

## 1. 概要

### 1.1 目的

unit_003 の純粋な入力評価境界を pyglet の主スレッドへ接続する。メインウィンドウ、入力イベントの正規化、入力捕捉の開始・解除、フォーカス喪失時の即時 neutral、ControllerFrame の可視化を実装する。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| roadmap | Unit 004 の成果、接続先、完了条件 | `spec/initial/roadmap.md` |
| UI design | ウィンドウ寸法、toolbar、ControllerView、status bar | `spec/initial/ui.md` |
| lifecycle | 捕捉開始・終了、フォーカス喪失、neutral | `spec/initial/lifecycle.md` |
| architecture | 主スレッド所有、入力 flow、pyglet clock | `spec/initial/architecture.md` |
| requirements | FR-005〜FR-009、NFR-001、NFR-005 | `spec/initial/requirements.md` |
| testing design | PygletInputBackend、UI Presenter、UI marker | `spec/initial/testing.md` |
| completed input | PhysicalInputState、InputPublisher、ControllerFrame | `spec/complete/unit_003/` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| application | IDLE で入力開始 | exclusive mouse を有効にし、epoch を進め、capture 中の初期 neutral frame を出す | 明示操作だけで開始する |
| pyglet window | key、mouse、relative motion event | `PhysicalInputState` が正規化された値へ更新される | callback で Bluetooth I/O や設定保存を行わない |
| pyglet window | F12 または deactivate | exclusive mouse を解除し、状態を clear して capture 外 neutral を出す | 自動再捕捉しない |
| ControllerView | `ControllerFrame` | ボタン、stick、IMU、capture を同じ frame から表示する | pyglet input state や swbt state を参照しない |
| toolbar / status bar | app / connection / capture state | 操作可能性、接続、捕捉、preview-only 警告を文字で表示する | 色だけに依存しない |
| pyglet clock | 8ms schedule callback | `InputPublisher.publish()` が定期評価される | 実時間 sleep を実装しない |

## 2. 対象範囲

- `pyglet>=2.1,<2.2` を runtime dependency として固定する。
- `AppState` と capture の主スレッド側状態遷移を定義する。
- 既定 960x640、最小 800x520、再描画可能な pyglet window factory を用意する。
- `PygletInputBackend` で key symbol、modifier、mouse button、relative `dx/dy` を domain source へ変換する。
- F12、focus lost、capture start/stop の安全な neutral sequence を実装する。
- `ControllerView`、toolbar、status bar の表示モデルと pyglet 描画境界を実装する。
- `pyglet.clock.schedule_interval(..., 0.008)` の入力評価接続と最大 60Hz の描画設定を用意する。
- frame sink は unit test の fake を使い、Bluetooth 実装へ依存しない。

## 3. 対象外

- asyncio 接続 runtime、専用 worker thread、latest-frame mailbox、250ms watchdog。
- swbt-python adapter、Bumble、Bluetooth、Switch 本体。
- 設定 modal、binding editor、connection dialog、color editor の編集操作。
- global hook、Raw Input、キーボード排他、OS 固有の未解決キー表示 UI。
- 実機送信、OS 別の高 DPI 差、長時間の 60Hz 性能測定。

## 4. 関連 docs

- `spec/initial/roadmap.md`
- `spec/initial/ui.md`
- `spec/initial/lifecycle.md`
- `spec/initial/architecture.md`
- `spec/initial/requirements.md`
- `spec/initial/testing.md`
- `spec/complete/unit_003/INPUT_PIPELINE.md`
- `AGENTS.md`
- `SKILLS.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| window を作成する | 既定 settings | 960x640、最小 800x520、resize 可の window spec を得る | 実 window の生成は factory 境界に閉じ込める |
| capture を開始する | IDLE、focus 中、modal なし | state を CAPTURED、epoch を +1、exclusive mouse on、capture-active neutral を offer する | publisher の初回 dt は 0 |
| capture を停止する | CAPTURED、toolbar または F12 | state を IDLE、epoch を +1、exclusive mouse off、state clear、capture-inactive neutral を offer する | 二重停止は安全な no-op |
| focus を失う | CAPTURED から deactivate | state を SUSPENDED、exclusive mouse off、state clear、neutral を offer する | activate は IDLE へ戻すだけ |
| exclusive mouse に失敗する | capture 開始時の `OSError` / `RuntimeError` | CAPTURED へ遷移せず入力を送らない | 状態を IDLE に戻す |
| key event を正規化する | pyglet symbol、modifier bit、press/release | `KeySource` として保持し、重複押下を増殖させない | F12 は mapping へ流さない |
| mouse event を正規化する | left/middle/right/追加 button、press/release、dx/dy | `MouseButtonSource` と relative motion へ反映する | capture 外は無視する |
| ControllerView を更新する | `ControllerFrame` | pressed button、stick knob、gyro、accel、capture overlay の表示モデルを更新する | 更新元は frame だけ |
| toolbar/status を更新する | app state、connection state、adapter label、warning | 操作ラベル、enabled、接続表示、preview-only 文言を決定する | 未接続 capture は送信なし警告を表示 |
| pyglet clock を接続する | publisher、window | 8ms 評価 callback を登録し、描画 callback は UI を再描画する | sleep / 独自 event loop は持たない |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-done | pyglet dependency と window spec が 960x640、最小 800x520、resize 可を表現する | new / edge | unit | 1 test green。実 display を要求しない spec test と pyglet window factory 境界を追加 |
| refactor-done | AppState と CaptureCoordinator が capture start/stop、epoch、neutral、exclusive mouse 失敗を扱う | new / edge | unit | 2 tests green。FakeWindowPort と InputPublisher sink で開始・停止・失敗を確認 |
| refactor-done | PygletInputBackend が key、modifier、mouse、relative motion を domain state へ変換する | new / edge | unit | 3 tests green。pyglet event handler を直接呼び、display を要求しない。modifier source の Binding も許可 |
| refactor-skipped | F12 と deactivate が capture を解除し、activate が自動再捕捉しない | new / regression | unit | 2 tests green。capture 外 event の無視を含め、item 3 の backend/coordinator 実装で固定 |
| refactor-done | ControllerView が ControllerFrame だけから pressed/control/IMU の表示モデルを更新する | new / edge | unit | 2 tests green。stick、button、gyro、accel、capture を frame だけから更新し、pyglet Batch 描画境界を追加 |
| refactor-done | toolbar が connection/app state からラベルと enabled を決める | new / edge | unit | 2 tests green。接続中、captured、focus loss、modal 相当の無効状態を確認 |
| refactor-done | status bar が adapter、connection、capture、8ms、preview warning を組み立てる | new / edge | unit | 2 tests green。未接続 capture の preview-only 警告を固定 |
| refactor-done | PygletApplication が backend、view、toolbar、status、8ms clock を接続する | new / integration | unit | 1 test green。FakeWindow と FakeClock で handler wiring、8ms schedule、表示開始、coordinator latest frame を確認 |
| refactor-done | UI package の全 gate と display-free import/window/package smoke が通る | characterization | package | 92 unit tests、lock、format、lint、ty、display-free import、非表示 window、ControllerView draw、build、wheel contents を確認。Windows headless は EGL 不在で not applicable |

## 7. 設計メモ

- pyglet の具象 `Window` は `ui.window` に閉じ込め、入力 backend と view は Protocol / 表示モデルを介して試験する。
- input/UI module は import 時に display-dependent な pyglet module を読み込まず、実 window/draw/event 境界で遅延 import する。backend の key/mouse constants は注入できる。
- `CaptureCoordinator` が `AppState` と `capture_epoch` の唯一の所有者となる。toolbar や backend が直接 state を変更しない。
- `PygletInputBackend` は callback で `PhysicalInputState` を更新するだけで、frame publish は clock callback の `InputPublisher` に任せる。
- F12 は capture 状態に関係なく予約操作として扱い、capture 中なら解除し、mapping へ渡さない。
- `ControllerView` は ControllerFrame を保持し、静的図形と動的値を分離する。実描画は pyglet Batch を使い、pure な表示状態は display 不要で試験する。
- connection state は unit_005 の runtime 実装前なので、unit_004 では表示用 enum と fake 状態に限定する。
- pyglet 2.1 の `Window.set_exclusive_mouse()`、window event handler、`clock.schedule_interval()`、shapes/batch の公開 API を使用する。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `pyproject.toml` | modify | pyglet runtime dependency |
| `uv.lock` | modify | pyglet dependency lock |
| `src/demi/application/__init__.py` | new | application package |
| `src/demi/application/state.py` | new | AppState、ConnectionState、capture state |
| `src/demi/application/coordinator.py` | new | capture lifecycle、epoch、neutral、window port |
| `src/demi/input/pyglet_backend.py` | new | pyglet event normalization |
| `src/demi/ui/__init__.py` | new | UI package |
| `src/demi/ui/window.py` | new | window spec、pyglet clock/event wiring |
| `src/demi/ui/controller_view.py` | new | ControllerFrame display model and drawing boundary |
| `src/demi/ui/toolbar.py` | new | toolbar display model |
| `src/demi/ui/status_bar.py` | new | status bar display model |
| `tests/unit/application/` | new | state transition and coordinator behavior |
| `tests/unit/input/test_pyglet_backend.py` | new | event normalization and priority |
| `tests/unit/ui/` | new | window/view/toolbar/status behavior |
| `tests/unit/test_pyglet_import_boundary.py` | new | display-free import regression |
| `spec/complete/unit_004/UI_AND_PYGLET.md` | new / modify | TDD 状態、検証、完了記録 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/unit` | not run | unit_004 implementation 前の baseline は unit_003 merge 時点で 75 passed |
| `uv add pyglet>=2.1,<2.2` | passed | `pyglet==2.1.15` を追加し `uv.lock` を更新 |
| `uv run pytest tests/unit/ui/test_window.py` | passed | 1 passed |
| `uv run ruff format --check src/demi/ui/window.py tests/unit/ui/test_window.py` | passed | 2 files already formatted |
| `uv run ruff check src/demi/ui/window.py tests/unit/ui/test_window.py` | passed | All checks passed |
| `uv run ty check --no-progress` | passed | All checks passed |
| `uv sync --dev` | passed | 43 packages resolved、38 packages checked |
| `uv lock --check` | passed | 43 packages |
| `uv run ruff format --check .` | passed | 48 files already formatted |
| `uv run ruff check .` | passed | All checks passed |
| `uv run ty check --no-progress` | passed | All checks passed |
| `uv run pytest tests/unit` | passed | 91 passed |
| `uv run pytest tests/unit/test_pyglet_import_boundary.py` | passed | 1 passed。input/UI module import 時に display-dependent pyglet modules を読み込まない |
| `uv run pytest tests/unit` | passed | 92 passed |
| `uv run ruff format --check .` | passed | 49 files already formatted |
| `uv run ruff check .` | passed | All checks passed |
| `uv run ty check --no-progress` | passed | All checks passed |
| display-free import smoke via `uv run python -c` | passed | `pyglet.window`、`pyglet.graphics`、`pyglet.text` を読み込まず application modules を import |
| window factory smoke via `uv run python -c` | passed | 非表示 960x640 window を作成し、close まで完了 |
| ControllerView draw smoke via `uv run python -c` | passed | 非表示 OpenGL context 上で Batch 描画と close を確認 |
| headless window smoke via `uv run python -c` | not applicable | Windows の pyglet headless path は EGL library 不在で `Library "EGL" not found`。通常の非表示 window smoke は passed |
| `uv build` | passed | `demi_controller-0.1.0.tar.gz` と `demi_controller-0.1.0-py3-none-any.whl` を生成。sandbox の PyPI 接続制限のため外部アクセス許可で実行 |
| package smoke via `uv run python -c` | passed | wheel に UI、PygletInputBackend、window modules が含まれることを確認 |
| `uv run pytest tests/integration` | not applicable | `tests/integration` tree は未作成。fake/UI boundary は unit で確認 |
| `git diff --check` | passed | whitespace error なし |
| GitHub Actions PR #4 initial run | failed | Python 3.12 / 3.13 とも Linux display unavailable。`pyglet.window` import 時の `NoSuchDisplayException` |
| type-boundary review | passed | pyglet window、clock、event handler を Protocol で境界化。`ty` 通過、production の `Any` / `type: ignore` なし。外部 descriptor の writable color だけ局所 `cast` |
| docstring review | passed | application、input backend、window、view、toolbar、status の public API 契約を確認 |
| docs-quality review | passed | scope、non-goals、TDD status、実行結果、not applicable、先送り事項、仮テキスト残りを確認 |
| agentic-self-review | passed | `spec/initial`、diff、TDD commit、static/package gate、残リスクを照合 |
| `uv run pytest tests/unit/ui/test_pyglet_application.py` | passed | 1 passed |
| `uv run ruff format --check src/demi/ui/window.py tests/unit/ui/test_pyglet_application.py` | passed | 2 files already formatted |
| `uv run ruff check src/demi/ui/window.py tests/unit/ui/test_pyglet_application.py` | passed | All checks passed |
| `uv run ty check --no-progress` | passed | All checks passed |
| `uv run pytest tests/unit/ui/test_status_bar.py` | passed | 2 passed |
| `uv run ruff format --check src/demi/ui/status_bar.py tests/unit/ui/test_status_bar.py` | passed | 2 files already formatted |
| `uv run ruff check src/demi/ui/status_bar.py tests/unit/ui/test_status_bar.py` | passed | All checks passed |
| `uv run ty check --no-progress` | passed | All checks passed |
| `uv run pytest tests/unit/ui/test_toolbar.py` | passed | 2 passed |
| `uv run ruff format --check src/demi/ui/toolbar.py tests/unit/ui/test_toolbar.py` | passed | 2 files already formatted |
| `uv run ruff check src/demi/ui/toolbar.py tests/unit/ui/test_toolbar.py` | passed | All checks passed |
| `uv run ty check --no-progress` | passed | All checks passed |
| `uv run pytest tests/unit/ui/test_controller_view.py` | passed | 2 passed |
| `uv run ruff format --check src/demi/ui/controller_view.py tests/unit/ui/test_controller_view.py` | passed | 2 files already formatted |
| `uv run ruff check src/demi/ui/controller_view.py tests/unit/ui/test_controller_view.py` | passed | All checks passed |
| `uv run ty check --no-progress` | passed | All checks passed |
| `uv run pytest tests/unit/input/test_pyglet_backend.py` | passed | 5 passed |
| `uv run ruff format --check src/demi/input/pyglet_backend.py tests/unit/input/test_pyglet_backend.py` | passed | 2 files already formatted |
| `uv run ruff check src/demi/input/pyglet_backend.py tests/unit/input/test_pyglet_backend.py` | passed | All checks passed |
| `uv run ty check --no-progress` | passed | All checks passed |
| `uv run pytest tests/unit/input/test_pyglet_backend.py` | passed | 3 passed |
| `uv run pytest tests/unit/domain/test_mapping.py` | passed | 6 passed |
| `uv run ruff format --check src/demi/input/pyglet_backend.py src/demi/domain/mapping.py tests/unit/input/test_pyglet_backend.py tests/unit/domain/test_mapping.py` | passed | 4 files already formatted |
| `uv run ruff check src/demi/input/pyglet_backend.py src/demi/domain/mapping.py tests/unit/input/test_pyglet_backend.py tests/unit/domain/test_mapping.py` | passed | All checks passed |
| `uv run ty check --no-progress` | passed | All checks passed |
| `uv run pytest tests/unit/application/test_coordinator.py` | passed | 2 passed |
| `uv run ruff format --check src/demi/application tests/unit/application` | passed | 4 files already formatted |
| `uv run ruff check src/demi/application tests/unit/application` | passed | All checks passed |
| `uv run ty check --no-progress` | passed | All checks passed |
| `uv lock --check` | not run | dependency 変更後に実行する |
| `uv build` | not run | dependency 変更後に実行する |
| `uv run pytest tests/integration` | not applicable | `tests/integration` tree は未作成。headless/fake UI は unit で扱う |

## 10. 先送り事項

- 実 display を使う OS 別 window / 高 DPI / 60Hz 長時間測定は Unit 008/009 の UI 試験へ送る。
- connection state の実データ、runtime event、接続・切断ボタンの実動作は Unit 005/006 へ送る。
- mapping / connection / color modal の編集操作は Unit 007 へ送る。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を作成した
- [x] 検証結果または未実行理由を実装後に更新した
- [x] package / release / public API に触れる場合の gate を記録した
- [x] 完了時に `spec/complete/unit_004` へ移動した
