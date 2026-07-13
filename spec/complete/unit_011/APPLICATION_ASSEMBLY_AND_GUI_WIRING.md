# アプリケーション組み立てと GUI 配線 仕様書

## 1. 概要

### 1.1 目的

CLI、設定、入力、ControllerRuntime、swbt adapter、pyglet UI の間に残っている本番配線を実装し、`demi`、`project-demi`、`python -m demi`、standalone artifact の引数なし起動で同じ操作可能な GUI を開始する。

Unit 004〜007 で実装済みの表示モデル、入力 pipeline、接続 runtime、設定編集を本番の構成 root から生成し、GUI 操作と runtime event に接続する。部品単体の存在ではなく、初回起動から終了までの一続きのアプリケーション動作を完了条件とする。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user request | GUI と各部品間の配線漏れ、起動経路の実装漏れを抽出し、新規 unit にまとめる | conversation |
| initial architecture | `app.py` を具象実装の構成 root とし、worker event を pyglet 主スレッドへ渡す | `spec/initial/architecture.md` |
| lifecycle | 設定読み込み、runtime 起動、window 作成、自動再接続、終了順序 | `spec/initial/lifecycle.md` |
| requirements | 引数なし CLI の GUI 起動、接続・入力・設定の GUI 操作、復旧通知 | `spec/initial/requirements.md` |
| completed Unit 004 | connection state の実データ、runtime event、接続ボタンを後続へ送った | `spec/complete/unit_004/UI_AND_PYGLET.md` |
| completed Unit 005 / 006 | main-thread event bridge、GUI からの pairing、path resolver の組み立てを後続へ送った | `spec/complete/unit_005/CONTROLLER_RUNTIME.md`, `spec/complete/unit_006/SWBT_ADAPTER.md` |
| completed Unit 007 | pyglet dialog renderer、adapter list、再接続 command の配線を後続へ送った | `spec/complete/unit_007/SETTINGS_MODAL.md` |
| completed Unit 010 | standalone launcher の GUI 組み立てと settings / connection button 配線を対象外にした | `spec/complete/unit_010/PACKAGING.md` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| user / CLI | 引数なしでいずれかの正規 entry point を実行する | 設定を読み、操作可能なメインウィンドウを表示する | `--version` は display や機材を要求しない |
| first-run user | 設定ファイル、adapter、bond がない | 既定設定で GUI を開き、プレビューと設定操作を利用できる | 起動だけで pairing しない |
| returning user | 保存済み設定と `reconnect_on_start=true` がある | 検出した保存済み adapter にだけ非同期で再接続する | 別 adapter への fallback と新規 pairing を禁止する |
| user / toolbar | 接続、切断、入力開始・停止、設定を操作する | 現在状態に対応する application action が実行され、表示へ反映される | worker I/O で pyglet 主スレッドを塞がない |
| user / settings modal | mapping、connection、colors を編集して保存または取消する | draft の検証・保存・runtime 反映を行い、失敗時は modal と draft を保持する | modal 中は controller input を送らない |
| runtime worker | connection、adapter、watchdog、error event を発行する | 主スレッドで application state、toolbar、status、dialog を更新する | worker から UI object を直接操作しない |
| user / window lifecycle | window を閉じる、Ctrl+Q、または起動途中で失敗する | neutral、runtime shutdown、thread join、window close を順序付きで試行する | bond 内容や秘密値をエラーへ出さない |

## 2. 対象範囲

| boundary | 対象 |
|---|---|
| composition root | 設定、clock、window、publisher、coordinator、runtime、adapter、UI controller を一箇所で生成する |
| entry point | 引数なし CLI と PyInstaller launcher を GUI 起動へ接続し、version / unknown argument の既存契約を維持する |
| startup | 設定 load / recovery、runtime start、adapter discovery、条件付き saved reconnect、window 表示を接続する |
| 起動ログ | ログ保存先を解決して安全な起動・終了・致命的失敗を記録し、設定した診断水準を適用する |
| frame path | `InputPublisher` の同一 `ControllerFrame` を `ControllerRuntime.offer_frame()` と `ControllerView` へ流す |
| event path | worker-thread `RuntimeEvent` を thread-safe に pyglet 主スレッドへ渡し、接続状態、adapter 一覧、警告、error を application model へ反映する |
| main GUI | toolbar を操作可能な control とし、capture、connection、mapping、connection settings、colors の action を接続する |
| settings GUI | Unit 007 の draft/controller を pyglet modal renderer へ接続し、binding、mouse / gyro、connection、colors の編集、adapter 再検索、明示 pairing、save/cancel、color 再接続を runtime command へ変換する |
| live settings | 読み込んだ active profile、mouse、stick limit、local actions、window、colors を各部品へ渡し、保存成功後の設定を実行中の表示・入力・接続設定へ反映する |
| shutdown | capture neutralization、UI command 無効化、window state 保存、runtime shutdown / join、pyglet 終了を冪等に実行する |
| package smoke | display を使わない version smoke を維持し、注入可能な application runner で GUI 起動経路を機材なしに検証する |

## 3. 対象外

- Bluetooth dongle、Switch 本体、Bumble を使う pairing、再接続、入力の実機受入。
- Windows、macOS、Linux の実 display、OpenGL、DPI、font、排他 mouse の OS 別受入。
- `ControllerRuntime`、`SwbtControllerAdapter`、設定 schema、入力変換の既存アルゴリズム変更。配線で露出した不具合は回帰 test を追加して必要最小限に修正する。
- FR-015 全体の診断 snapshot と診断画面。Unit 011 ではローカルのローテーション付きログの初期化、診断水準、起動失敗と既存 `ControllerError` の安全な表示・記録までを扱う。
- profile import/export、Joy-Con、追加 input backend、Raw Input、OS sleep 通知。
- PyPI / TestPyPI 公開、version bump、release tag。

## 4. 関連 docs

- `spec/initial/architecture.md`
- `spec/initial/configuration.md`
- `spec/initial/input.md`
- `spec/initial/lifecycle.md`
- `spec/initial/requirements.md`
- `spec/initial/testing.md`
- `spec/initial/ui.md`
- `spec/complete/unit_004/UI_AND_PYGLET.md`
- `spec/complete/unit_005/CONTROLLER_RUNTIME.md`
- `spec/complete/unit_006/SWBT_ADAPTER.md`
- `spec/complete/unit_007/SETTINGS_MODAL.md`
- `spec/complete/unit_010/PACKAGING.md`
- `AGENTS.md`
- `SKILLS.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| 正規 entry point から起動する | 引数なしの `demi`、`project-demi`、`python -m demi`、standalone | 共通 application runner が設定を読み、runtime と GUI を開始し、終了 status を返す | `--version` は application runner を生成しない |
| 初回設定で起動する | settings file なし | `AppSettings.default()` を使って window を表示し、接続なしのプレビューと設定操作を有効にする | adapter なしを致命的エラーにしない |
| 復旧設定で起動する | repository が `RECOVERED` を返す | 既定設定で起動し、backup file 名だけを含む通知を UI に一度表示する | TOML 本文や bond 情報を表示しない |
| 読み込んだ設定を適用する | 有効な settings | window 寸法・最大化、active profile、mouse、stick limit、local actions、colors、評価間隔、connection selection を対応する部品へ渡す | hard-coded default へ戻さない |
| runtime を開始する | 設定読み込み成功 | `SwbtControllerAdapter` factory と main-thread event bridge を持つ runtime を start し、非同期 adapter discovery を要求する | UI thread で swbt I/O を実行しない |
| 起動時に保存済み接続を試す | reconnect enabled、保存 ID が列挙結果に存在 | 設定した bond path、timeout、colors で `ConnectSaved` を一度発行する | adapter 不在時は警告して READY を維持する。pairing と fallback はしない |
| frame を共有する | 8ms input evaluation | 生成した同一 frame を runtime の latest slot へ offer し、ControllerView の表示元にもする | 接続なしでも view は更新する |
| runtime event を UI へ渡す | worker が `RuntimeEvent` を emit | thread-safe queue / dispatcher を経由し、pyglet 主スレッドで状態を更新する | worker thread から window、widget、OpenGL を触らない |
| toolbar action を実行する | 現在の app / connection / dialog state と click または keyboard action | enabled な capture、connect/disconnect、settings action だけを coordinator / runtime / modal controller へ渡す | disconnect は capture を neutralize してから発行する。bracket 付き label の表示だけで完了にしない |
| 接続設定を操作する | connection modal、再検索、保存済み接続、明示 pairing | adapter list を更新し、保存済み接続は `ConnectSaved`、確認後の pairing は `StartPairing` を発行する | 0件時は接続を無効化する |
| 設定を保存する | 有効な modal draft | repository save 成功後に current settings と関連表示・入力設定を更新する | save 失敗時は draft と modal を保持する |
| mouse / gyro 設定を編集する | mapping modal で gyro enabled、水平・垂直感度、Y 反転、pitch 上限を変更する | draft の `MouseSettings` を検証し、保存後の publisher へ反映する | 水平・垂直感度を連動させない |
| colors を再接続で反映する | 接続中に colors を保存し、ユーザーが再接続を選ぶ | neutral、`RecreateWithColors`、rest state の runtime 経路を使い、capture は自動再開しない | 「後で」では接続を変更しない |
| modal 中の入力を隔離する | modal visible、文字・キー取得中 | controller mapping を更新せず、Tab、Enter / Space、Esc と編集対象入力を UI が処理する | F12 の安全解除は維持する |
| watchdog / error を反映する | `WatchdogNeutralized` または `ControllerError` | capture を解除して neutral view と warning / safe summary を表示し、再操作可能な状態へ戻す | 後続の READY event で未確認 error を即時消去しない。traceback と下位例外名を UI へ出さない |
| 正常終了する | close event、Ctrl+Q、重複終了要求 | schedule 停止、capture neutral、有効な window 寸法・最大化状態の保存、runtime close / thread join、window close を順序付きかつ一度だけ実行する | `RuntimeStopped` を受けても二重 close しない |
| 起動失敗を処理する | settings read、window、runtime start の致命的失敗 | 開始済み資源を best effort で閉じ、端末と log に安全な原因を残して非ゼロ終了する | `--version` failure と混同しない |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| passed | 引数なし CLI は注入した application runner を一度呼び、その終了 status を返す | new | unit | `tests/unit/test_cli.py` で `--version` と unknown argument の非生成も確認 |
| passed | `demi` と `python -m demi` は同じ GUI application runner を選ぶ | regression | package | console script、module entry、PyInstaller launcher の共通 runner と standalone `--version` smoke を確認 |
| passed | settings file がない起動は既定設定で runtime と window を開始し、adapter なしでも GUI を表示する | new | integration | `tests/integration/lifecycle/test_application_lifecycle.py` の fake assembly |
| passed | recovered settings の起動は backup file 名だけの通知を一度表示する | regression | integration | lifecycle、settings modal、pyglet status bar の一回表示 test で確認 |
| passed | 読み込んだ window、profile、mouse、stick limit、local actions、colors、evaluation interval、connection 値が構成済み部品へ渡る | new | integration | default 値以外の lifecycle fixture を使用 |
| passed | publisher が生成した frame は runtime と ControllerView の双方で同じ値として観測される | new | integration | `test_application_draws_the_exact_frame_offered_to_the_runtime` が同一 frame instance を確認 |
| passed | worker event は main-thread dispatcher が drain するまで UI state を変更しない | new | integration | `tests/unit/ui/test_event_bridge.py` と application session test |
| passed | adapter discovery event は connection modal の候補を更新し、0件では接続操作を無効にする | new | integration | presentation、toolbar、connection modal の test で確認 |
| passed | 起動時再接続は検出済みの保存 adapter にだけ `ConnectSaved` を一度発行する | new | integration | discovery 後の READY event、adapter 不在、disabled、pairing 非発行を session test で確認 |
| passed | toolbar の入力 action は IDLE / CAPTURED を切り替え、focus 喪失または modal 中は開始できない | regression | integration | toolbar、pyglet application、focus loss を扱う pyglet backend の fake event test |
| passed | toolbar の connection action は未設定で modal、READY で saved connect、CONNECTED で disconnect を発行する | new | integration | application session test で busy 時の重複も確認 |
| passed | mapping、connection、colors の control は modal draft を編集し、save / cancel を実行できる | new | integration | modal renderer と pyglet application の fake event test |
| passed | mapping modal の mouse / gyro control は各値を独立して編集し、保存後の frame 生成へ反映する | new | integration | settings editor と live publisher reconfigure test |
| passed | modal の文字入力と key capture は controller mapping へ流れず、Esc / F12 の予約操作を守る | edge | integration | modal keyboard isolation と text-edit test |
| passed | 新規 pairing は確認完了後だけ選択 adapter と bond path を持つ `StartPairing` を発行する | new | integration | pairing confirmation と runtime lifecycle test |
| passed | settings save 成功は実行中の入力・表示設定を更新し、save 失敗は draft と modal を保持する | new | integration | settings modal integration と application session test |
| passed | 接続中の colors save は「後で」と `RecreateWithColors` を選択でき、capture を自動再開しない | new | integration | color reconnect の pyglet application test |
| passed | `ConnectionChanged`、`ControllerError`、`WatchdogNeutralized` は toolbar、status、capture state へ安全に反映される | new | integration | presentation と application session test |
| passed | Ctrl+Q と window close は window state 保存、neutral、runtime shutdown、thread join を順序付きで一度だけ実行する | new | integration | shutdown coordinator、pyglet application、lifecycle test |
| passed | startup failure は開始済み資源を閉じ、安全な stderr と非ゼロ status を返す | edge | integration | lifecycle の failure fixture で秘密値非出力を確認 |
| passed | 起動ログはローカルの保存先、設定した診断水準、ローテーションを使い、秘密値を記録しない | new | unit | 一時パスを使う logging test と safe category logging test |
| passed | display module の遅延 import と standalone `--version` smoke を維持する | regression | package | unit test、Windows standalone build、`packaging/smoke.py` で確認 |

## 7. 設計メモ

### 7.1 実装前の監査結果（baseline）

次は 2026-07-13 の source と test を検索して確認した事実である。

| boundary | 実装済み | 未接続または未実装の根拠 |
|---|---|---|
| CLI | `demi.cli:main`、`python -m demi`、console script、PyInstaller launcher が同じ関数を使う | 引数なし `main()` は `Project_Demi` を stdout へ書いて終了し、GUI runner を呼ばない |
| window application | `create_window()` と `PygletApplication.run()` がある | production source に両者の呼び出し元も `PygletApplication` の生成箇所もない |
| settings | path resolver、repository、load result、modal controller がある | production source に `resolve_paths()` / `SettingsRepository(...)` / `SettingsModalController(...)` の生成箇所がない |
| 設定値の反映 | window、input interval、mouse、local actions、colors を codec で保存できる | production source に読み込んだ値の consumer がなく、`PygletApplication` は 8ms、window / view は既定値のまま生成される |
| 設定編集 | binding、connection、colors の immutable draft 更新がある | UI 設計にある gyro enabled、水平・垂直感度、Y 反転、pitch 上限の draft 更新操作がない |
| input to runtime | `InputPublisher` は `FrameSink`、`ControllerRuntime` は `offer_frame()` を持つ | runtime を publisher sink として構成する production code がない |
| controller runtime | command、event、runtime、swbt adapter がある | production source に runtime / swbt adapter の生成と command 発行元がない |
| worker event | `RuntimeEventSink` Protocol と worker-thread emit がある | concrete event sink と pyglet main-thread dispatcher がない |
| connection display | toolbar / status は `ConnectionState` を表示できる | `PygletApplication` は constructor の固定値を保持し、runtime event から更新する API / consumer がない |
| dialog state | settings editor、dialog manager、view model がある | pyglet modal renderer、操作 control、adapter list consumer、save result consumer がない |
| toolbar | label と enabled model がある | bracket 付き text を描画するだけで、button widget、hit test、action handler がない |
| local actions | settings に Ctrl+C / Ctrl+Q / F12 がある | backend が処理するのは F12 だけで、toggle / quit の dispatch がない |
| shutdown | runtime と pyglet application に個別の close / stop がある | window close は input schedule と capture だけを停止し、runtime shutdown / join を呼ばない |
| ウィンドウ状態の永続化 | `WindowSettings` と TOML codec が width、height、maximized を保持する | production source に起動時適用と終了時保存の経路がない |
| logging | `DiagnosticLevel` と log directory resolver がある | production source に logging bootstrap、file handler、diagnostic level の consumer がない |
| completed specs | Unit 004〜007 は各配線を「後続」で扱うと記録した | Unit 008〜010 は新しい GUI wiring または application assembly を対象外とし、`spec/wip` に引受 unit がない |

### 7.2 目標フロー

```text
CLI / packaging launcher
  -> application composition root
      -> SettingsRepository.load()
      -> ControllerRuntime(SwbtControllerAdapter, RuntimeEventBridge).start()
      -> InputPublisher(sink=ControllerRuntime)
      -> CaptureCoordinator + PygletInputBackend
      -> Toolbar / dialogs / ControllerView / StatusBar
      -> PygletApplication.run()

worker RuntimeEvent
  -> thread-safe RuntimeEventBridge
  -> pyglet main thread
  -> application state / toolbar / status / dialog

GUI action
  -> application coordinator
  -> ControllerRuntime.post(command) or SettingsModalController
```

### 7.3 所有権

- 構成 root だけが具象 repository、runtime、adapter、window、renderer を生成する。
- `demi.application` と `demi.ui` は concrete controller event 型へ依存せず、構成 root が runtime event を application-level action / presentation へ変換する。
- pyglet window、widget、OpenGL resource は主スレッドだけが操作する。
- runtime worker は swbt adapter を所有し、UI へ返すのは `RuntimeEvent` だけとする。
- current `AppSettings` と connection / dialog presentation state は application 層が所有し、UI model や worker が独自に複製した正本を持たない。
- input frame は一度生成し、runtime 送信用と preview 表示用に別形式へ再計算しない。

### 7.4 実装順

1. CLI と構成 root の注入可能な起動契約を red / green にする。
2. settings、runtime、publisher、window の startup / shutdown を fake 境界で接続する。
3. runtime event bridge と connection presentation を接続する。
4. toolbar action と settings modal renderer を接続する。
5. auto reconnect、pairing、color reconnect、watchdog / error の edge を追加する。
6. package / full gate と display を使う手動 smoke を分けて記録する。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/app.py` | new | application composition root、startup / shutdown |
| `src/demi/cli.py` | modify | 引数なし GUI runner、version / error status |
| `src/demi/application/presentation.py` | new | main-thread connection / adapter / warning presentation state |
| `src/demi/application/shutdown.py` | new | neutral、settings save、runtime close を順序付ける shutdown coordinator |
| `src/demi/application/coordinator.py` | modify | shutdown transition と neutral frame の冪等性 |
| `src/demi/application/dialogs.py` | modify | pairing confirmation への modal 遷移 |
| `src/demi/application/settings_editor.py` | modify | mouse / gyro draft 編集 |
| `src/demi/controller/runtime.py` | modify | discovery failure 後に再操作可能な READY 状態へ戻す |
| `src/demi/ui/event_bridge.py` | new | worker event の thread-safe main-thread dispatch |
| `src/demi/ui/window.py` | modify | live state、toolbar / modal action、ordered shutdown の接続 |
| `src/demi/ui/toolbar.py` | modify | 操作可能な toolbar control 境界 |
| `src/demi/ui/dialogs.py` | modify | mapping、connection、colors、pairing confirmation の pyglet renderer |
| `src/demi/ui/controller_view.py` | modify | 保存済み colors の live 反映 |
| `src/demi/ui/status_bar.py` | modify | adapter availability と接続状態の表示 |
| `src/demi/input/publisher.py` | modify | 保存済み input settings の live 反映契約が必要な場合に更新 |
| `packaging/launcher.py` | verify (no change) | canonical CLI 経由の GUI 起動を維持 |
| `tests/unit/test_cli.py` | modify | runner dispatch と headless option behavior |
| `tests/unit/application/test_app.py` | new | composition root、session action、reconnect、safe logging |
| `tests/unit/application/test_logging.py` | new | rotating log と診断水準の再設定 |
| `tests/unit/application/test_presentation.py` | new | error / adapter / color reconnect presentation |
| `tests/unit/application/test_shutdown.py` | new | ordered shutdown と冪等性 |
| `tests/unit/ui/` | modify / new | toolbar / dialog action と event bridge |
| `tests/integration/lifecycle/test_application_lifecycle.py` | new | production 相当の fake assembly、startup / shutdown |
| `tests/integration/ui/test_settings_modal.py` | verify (no change) | settings / runtime / GUI 配線の既存回帰を実行 |
| `tests/unit/test_packaging.py` | verify (no change) | launcher と canonical GUI entry contract を実行 |
| `README.md` | modify | source 実行と GUI 起動の利用者向け手順 |

実装時に責務を確認し、不要な候補ファイルは作らない。構成 root の依存を避けるために domain / controller の既存型を UI 用へ変更しない。

## 9. 検証

| command | result | notes |
|---|---|---|
| `rg -n "T[O]DO|T[B]D|x[x]x|前[回]|今[回]|一[旦]|上[述]|適[宜]|必要に応じ[て]" README.md spec/complete/unit_011` | passed | 該当なし |
| `uv sync --dev` | passed | 71 packages を確認 |
| `uv lock --check` | passed | lockfile に差分なし |
| `uv run ruff format --check .` | passed | 90 files already formatted |
| `uv run ruff check .` | passed | All checks passed |
| `uv run ty check --no-progress` | passed | All checks passed |
| `uv run pytest tests/unit` | passed | 188 passed |
| `uv run pytest tests/integration` | passed | 15 passed |
| `uv build` | blocked | sandbox が build backend の外部取得を拒否したため exit 1。ネットワーク以外の原因ではない |
| `uv build --offline` | passed | ローカル cache の build backend で sdist と wheel を生成 |
| `uv run python packaging/build.py` | passed | Windows standalone `dist/standalone/demi.exe` を生成。PyInstaller の Linux / 任意機能向け収集警告は exit 0 で、Windows artifact の version smoke は通過 |
| `uv run python packaging/smoke.py` | passed | `demi.exe: version 0.1.0` |
| `uv run demi --version`、`uv run project-demi --version`、`uv run python -m demi --version` | passed | すべて `0.1.0` |
| GUI startup / close smoke | not run | 非対話環境では実 display を開いて手動で終了できない。fake window を使う lifecycle / close test で代替し、OS 実表示は未検証 |
| `git diff --check` | passed | whitespace error なし。Git の LF / CRLF 変換予告のみ出力 |

## 10. 先送り事項

| 観測 | 先送り理由 | 後続の置き場 |
|---|---|---|
| FR-015 の定期診断 snapshot と詳細表示は未実装 | application wiring と独立した診断項目・表示境界が必要 | 新規 diagnostics unit |
| 実 display の OS 差、DPI、font、排他 mouse は未確認 | CI の source-level test では実デスクトップ挙動を証明できない | `spec/complete/unit_009/OS_PORTABILITY.md` の未検証事項を入力にした OS acceptance unit |
| standalone の GUI 起動と resource 完備は未確認 | 現在の package smoke は `--version` だけを確認する | Unit 011 実装後の packaging acceptance unit |
| 実 adapter / target device を使う一連の GUI acceptance は未実行 | 機材とユーザー操作が必要 | `spec/hardware-test-log.md` を使う hardware acceptance |

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を作成した
- [x] CLI から GUI の本番起動経路を実装した
- [x] settings、input、runtime、UI の production assembly を実装した
- [x] worker event と GUI action を主スレッド境界で接続した
- [x] toolbar と settings modal を操作可能な GUI として接続した
- [x] startup reconnect と ordered shutdown の edge を確認した
- [x] 検証結果または未実行理由を実装後に更新した
- [x] package / public entry point に関する gate を完了した
- [x] `spec/complete/unit_011` へ移動した
