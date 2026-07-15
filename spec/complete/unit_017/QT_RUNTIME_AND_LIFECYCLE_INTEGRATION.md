# Qt runtime と lifecycle 統合 仕様書

## 1. 概要

### 1.1 目的

UI 再設計 milestone 5 として、`ControllerRuntime` worker、application state、Qt main window、入力timer、dialog、終了処理をproduction composition rootで接続する。workerが発行したadapter、connection、pairing、watchdog、error eventはQt queued signalを経由し、GUI主スレッド上でだけapplication stateとwidgetを更新する。

起動時のsettings load、runtime start、adapter discovery、条件付きsaved reconnect、window表示、通常終了、起動失敗、未処理例外をPySide6構成で復旧する。runtime停止後はQt timer、queued receiver、dialog callbackがapplication stateやwidgetを変更しない。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| milestone | milestone 5のqueued signal、runtime event、startup、ownership、応答性、停止条件 | `spec/ui-redesign/MILESTONES.md` |
| target UI | worker→queued signal→GUI thread→session→window refreshの目標構造 | `spec/ui-redesign/PYSIDE6_UI_DESIGN.md` |
| initial contracts | runtime ownership、startup / shutdown、reconnect、watchdog、exception | `spec/initial/architecture.md`, `spec/initial/lifecycle.md`, `spec/initial/swbt-integration.md` |
| completed behavior | production assembly、session action、safe logging、cancellable runtime shutdown | `spec/complete/unit_011/APPLICATION_ASSEMBLY_AND_GUI_WIRING.md`, `spec/complete/unit_012/CONTROLLER_RUNTIME_CANCELLABLE_SHUTDOWN.md` |
| prerequisites | Qt shell、input / preview、standard controls / dialogs | `spec/complete/unit_014/`, `spec/complete/unit_015/`, `spec/wip/unit_016/` |

milestone 0とunit_013〜016の完了を着手条件とする。本unitはproduction compositionとlifecycleを所有し、3 OS最終acceptanceと文書同期はunit_018へ渡す。

仕様執筆時点では上記の実装前提は未完了である。着手時に更新後の初期仕様と unit_013〜016 の完了記録を確認する。

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| runtime worker | adapter / connection / pairing / watchdog / error eventを発行 | queued delivery後にGUI主スレッドでsessionとwindowが更新される | workerからwidgetを直接呼ばない |
| returning user | reconnect設定と保存adapterがある | discoveryで同じadapterを検出後だけsaved reconnectを1回発行する | 別adapter fallbackとpairingを禁止する |
| user | discovery / connect / disconnect / pairing中にwindowを操作 | repaint、window移動、cancel可能なactionを100ms以上連続して塞がない | Bluetooth I/OをGUI threadで待たない |
| user | watchdog / controller errorが発生 | capture解除、neutral preview、安全なwarning / error、再操作可能stateへ戻る | tracebackと秘密値を表示しない |
| user | close / Ctrl+Q / 重複終了 | timer停止、signal無効化、neutral、runtime close / join、settings保存、window終了を一度だけ実行する | runtime operationをtimeout満了まで待たない |
| application | startup failure / unhandled exception | 開始済み資源を逆順に閉じ、安全なstderr / logと非ゼロstatusを返す | `os._exit`を使わない |

## 2. 対象範囲

- `QObject`を使う`QtRuntimeEventBridge`を実装し、workerから受けたimmutable `RuntimeEvent`をQt signalとしてemitする。
- receiverをGUI main threadへaffinityさせ、`Qt.ConnectionType.QueuedConnection`で`ApplicationSession.handle_runtime_event()`へ渡す。
- queued slotでthread identityを確認できる試験境界を持ち、worker threadから`QWidget`、`QAction`、modelを直接変更しない。
- adapter discovery、connection state、pairing progress、status、watchdog、controller error、runtime stoppedをapplication presentationへ変換し、main windowをrefreshする。
- `ApplicationSession`から旧 / 新UI具象型を除き、Qt型を含まない`ApplicationUiSnapshot`または同等のimmutable表示値を返す。
- GUI actionをapplication sessionへ渡し、connect saved、disconnect、pairing、rescan、color reconnect、capture、settings save / cancelをruntime commandまたはdomain actionへ変換する。
- startupでlogging、settings load / migration / recovery、domain service、event bridge、runtime、Qt window、input / repaint timer、discoveryを順に開始する。
- `reconnect_on_start=true`では保存adapterがdiscovery結果に存在する場合だけ`ConnectSaved`を1回発行し、新規pairingを開始しない。
- adapter 0件、saved adapter未検出、reconnect失敗を致命的起動失敗にせず、操作可能なwindowと分類済みwarningを維持する。
- settings / runtime / window作成途中のstartup failureで、生成済みtimer、signal receiver、runtime、windowを逆順に閉じ、非ゼロstatusを返す。
- main-thread未処理例外を安全なshutdown経路へ流し、worker未処理例外を`ControllerError` / `RuntimeStopped`として受け、neutralとcloseを最善努力する。
- `QTimer`、event bridge、dialog、main window、application runnerの所有関係をQObject parentまたは明示的coordinatorで固定する。
- shutdown開始時にinput / repaint timerを停止し、signal receiverを無効化またはdisconnectし、dialogを閉じ、capture neutral、runtime close / join、settings save、window closeを冪等に実行する。
- shutdown開始後にqueued event、timeout、dialog callbackが到着してもpresentation、widget、runtime commandを変更しない。
- fake slow adapter / runtimeを使い、discovery、connect、disconnect中にGUI event loopを100ms以上連続して塞がないことを測定する。
- PySide6構成でstartup / shutdownの既存integration scenarioを再実行する。

## 3. 対象外

- `ControllerRuntime`のcommand / mailbox / cancellationアルゴリズムの再設計。unit_012の契約を維持する。
- swbt-python、Bumble、Bluetooth transport、pairing protocol、bond formatの変更。
- input mapping、Raw Input、preview描画、settings domainの意味変更。
- hardware / target deviceを使うend-to-end acceptance。
- 3 OS実display、DPI、font、focus、pointer captureの最終確認。unit_018が所有する。
- PyInstaller / standalone artifact、Qt plugin収集、署名。milestone 7の後続unitが所有する。
- application層へ`QObject`、`Signal`、`QWidget`、`QColor`を導入する変更。

## 4. 関連 docs

- `spec/ui-redesign/PYSIDE6_UI_DESIGN.md`
- `spec/ui-redesign/MILESTONES.md`
- `spec/initial/architecture.md`
- `spec/initial/lifecycle.md`
- `spec/initial/requirements.md`
- `spec/initial/swbt-integration.md`
- `spec/initial/testing.md`
- `spec/complete/unit_005/CONTROLLER_RUNTIME.md`
- `spec/complete/unit_011/APPLICATION_ASSEMBLY_AND_GUI_WIRING.md`
- `spec/complete/unit_012/CONTROLLER_RUNTIME_CANCELLABLE_SHUTDOWN.md`
- `spec/complete/unit_014/PYSIDE6_APPLICATION_SHELL.md`
- `spec/complete/unit_015/QT_INPUT_AND_CONTROLLER_PREVIEW.md`
- `spec/wip/unit_016/QT_STANDARD_CONTROLS_AND_DIALOGS.md`
- `AGENTS.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| worker eventをqueueする | worker threadから`RuntimeEvent` | emit時点ではwidgetを変更せず、Qt event処理後にGUI threadで更新する | FIFOを維持する |
| adapter一覧を反映する | `AdaptersDiscovered` | snapshot、connection dialog model、toolbar enabledを更新する | 保存ID未検出を自動置換しない |
| connection / pairingを反映する | state / progress event | toolbar、status、dialog、busy stateを一貫して更新する | 重複commandを許可しない |
| watchdog / errorを反映する | `WatchdogNeutralized` / `ControllerError` | capture解除、neutral preview、分類済み表示、再操作可能state | stale eventをepoch / lifecycleで破棄する |
| startup reconnectする | enabled、保存ID、discovery一致 | saved reconnectを1回発行する | pairingとfallbackなし |
| startup reconnectを見送る | disabled / adapter不在 / ID不一致 | windowを維持し、警告またはREADYを表示する | 起動status 0を維持できる |
| GUI応答性を保つ | discovery / connect / disconnectのslow fake | 100ms未満でprobe eventを処理し続ける | I/O完了時間の保証ではない |
| startup failureを閉じる | repository / runtime / window途中失敗 | 作成済み資源を一度だけ閉じ、非ゼロstatus | 秘密値を出さない |
| unhandled exceptionを閉じる | main / workerの未処理例外 | capture neutral、runtime close、safe log、非ゼロ終了 | `BaseException`を握り潰さない |
| runtime停止を完了する | close完了 / `RuntimeStopped` | timer停止、receiver無効、dialog callback無効、thread終了 | 後着signalでstateを変更しない |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-skipped | worker eventはqueued delivery前にpresentationを変更せず、delivery後だけGUI thread上で更新する | regression | integration | worker / GUI thread idを記録し、`QtRuntimeEventBridge`自身の明示的な`QueuedConnection`でdeliveryする。`QObject.emit`の既存signatureをoverloadで保ちつつbridgeが`RuntimeEventSink`を実装するため、追加refactorは不要 |
| refactor-skipped | queued bridgeはadapter、connection、pairing、status、watchdog、error、runtime stoppedを順序どおりapplication sessionへ渡す | regression | integration | application session receiverのtest doubleへ7種のimmutable `RuntimeEvent`をFIFOで渡す。最初のitemでunion全体を検証するbridgeを実装済みのため、本itemでproduction code変更は不要 |
| refactor-skipped | `ApplicationSession`とapplication packageはPySide6型をimportせず、framework非依存snapshotでmain windowを更新する | new | package | frozen `ApplicationUiSnapshot`がcapture、presentation、dialog状態を表し、application sourceとsession sourceのPySide6 import不在を確認する。`MainWindow.refresh()`だけがQt標準部品へ変換するため、追加refactorは不要 |
| refactor-skipped | adapter discoveryはdialog候補とtoolbar stateを更新し、0件 / 保存ID未検出では別adapterを自動選択しない | regression | integration | `ApplicationUiSnapshot.adapters`がsafe adapter候補を保持し、`MainWindow.refresh()`はactiveな`ConnectionDialog`だけへ同期する。0件と保存ID未検出の選択禁止はdialog自身の既存責務であり、追加refactorは不要 |
| refactor-skipped | connection / pairing eventはbusyとaction enabledを更新し、完了 / 失敗後に再操作可能stateへ戻す | regression | integration | CONNECTINGではactionを無効にし、pairing progressはsafe warningで表示する。`ControllerError.retryable`をsessionからsnapshot、toolbarへ渡し、retryable errorだけ再試行可能にする。sessionはCONNECTING / DISCONNECTING中の重複commandを抑止するため、追加refactorは不要 |
| refactor-skipped | watchdog / error eventはcaptureを解除してneutral previewと安全な表示へ戻し、stale eventは新stateを上書きしない | regression | integration | current capture epochのwatchdogとcontroller errorはneutral frameをruntime sinkへ出し、stale watchdogは無視する。safe category messageだけをpresentationへ渡し、CaptureCoordinatorの既存neutralization責務を重複させないため追加refactorは不要 |
| refactor-skipped | startup reconnectは検出済みの保存adapterだけへ`ConnectSaved`を1回発行し、新規pairingを開始しない | regression | integration | `_startup_reconnect_pending`とdiscovery完了の組合せで一致IDへ一度だけConnectSavedを発行する。disabled、0件、保存ID未検出ではConnectSaved / StartPairingを発行しないため、追加refactorは不要 |
| refactor-skipped | settingsなし / adapterなし / reconnect失敗でもmain windowは操作可能に残る | edge | integration | production compositionはMainWindowがある場合にQt bridgeとGUI-thread routerをruntime sinkへ接続し、runtime start後にdiscoveryを発行する。FIRST_RUN + adapter 0件とretryable reconnect errorで設定actionを維持するため、追加refactorは不要 |
| refactor-skipped | discovery / connect / disconnectのslow fake実行中もGUI probe eventを100ms未満の間隔で処理する | new | integration | 30ms遅延のworker fakeでdiscovery、connect、disconnectを順に実行し、10ms GUI timerの隣接tick間隔が100ms未満であることを確認する。worker / queued bridge境界を使う既存構造で満たすため、追加refactorは不要 |
| refactor-skipped | startup途中のsettings / runtime / window failureは開始済み資源を逆順に一度だけ閉じ、安全なstderrと非ゼロstatusを返す | edge | integration | runtime factory失敗後も作成済みwindowを閉じる。runtime start失敗ではruntime close、settings保存、window closeを各1回実行する。settings loadとwindow factoryの失敗も秘密値をstderrへ出さずstatus 1で終了するため、追加refactorは不要 |
| refactor-skipped | main-thread未処理例外はneutral、runtime停止、settings / window cleanupを試行し非ゼロstatusを返す | regression | integration | GUI event loop中だけ安全な例外hookを設定し、通常例外ではneutral、runtime close、settings保存、window close、status 1を即時に確定する。KeyboardInterruptはcleanup後に伝播し、`os._exit`は使わないため、追加refactorは不要 |
| refactor-skipped | worker faultはqueued error / stoppedを処理し、widgetをworkerから変更せず安全に終了またはREADYへ戻る | regression | integration | workerのControllerErrorはqueued bridge後にGUI主スレッドでだけwidgetへ反映し、retryable分類をtoolbarへ渡す。RuntimeStoppedはCaptureCoordinatorをshutdown状態にして全actionを無効化するため、追加refactorは不要 |
| refactor-skipped | close / Ctrl+Q / RuntimeStoppedの競合でもtimer、signal、runtime、settings、windowの後処理は一度だけ実行される | edge | integration | RuntimeStoppedはrouterからapplication shutdown callbackへ進み、既にshutdown要求済みなら再実行しない。停止通知後にCtrl+Qとcloseを重ねてもtimer teardown、runtime close、settings保存は各1回のため、追加refactorは不要 |
| refactor-skipped | runtime停止後のqueued signal、timer timeout、dialog callbackはpresentation、widget、runtime commandを変更しない | regression | integration | bridgeとrouterをdeactivateし、MainWindow.begin_shutdown()でinput timerとdialog signalを停止する。停止前にqueueしたworker event、後着timer timeout、dialog finished callbackでもstate、widget、runtime commandは不変のため、追加refactorは不要 |
| refactor-skipped | Qt objectの生成・更新・破棄はGUI主スレッドで行われ、shutdown後にtop-level windowとactive timerが残らない | new | integration | QtApplicationRunnerがevent loop終了後にrunner所有windowを`deleteLater()`し、GUI主スレッドでDeferredDeleteを処理する。ApplicationのUI無効化は一回だけ実行して破棄済みwindowを再操作しない。生成、refresh、shutdown、input timer teardown、window / timerの破棄通知、top-level widget不在をoffscreenで固定したため、追加refactorは不要 |

## 7. 設計メモ

### 7.1 queued bridge

- bridgeはQt adapter層に置き、applicationの`RuntimeEventSink`を実装する。application / controller側はQt signalを認識しない。
- signal payloadのQt型制約で局所的に`object`を使う場合も、emit前とslot入口で`RuntimeEvent`契約を検証し、application全体へ`Any`を広げない。
- receiverのthread affinityをGUI threadへ固定し、`QueuedConnection`を明示する。direct connectionやworkerからのwindow method呼出しを禁止する。

### 7.2 ownershipと終了順序

```text
QtApplicationRunner
  -> MainWindow
      -> input evaluation timer
      -> repaint limiter timer
      -> toolbar / status / dialogs
      -> QtRuntimeEventBridge receiver
  -> ApplicationShutdownCoordinator
      -> stop timers / disable receiver
      -> capture neutral
      -> ControllerRuntime.close() / join
      -> persist valid window settings
      -> close dialogs / window / event loop
```

- QObject parentによる破棄だけに頼らず、runtime停止前にtimer停止とreceiver無効化を同期的に確定する。
- shutdown generationを持たせ、停止開始前にqueueされたeventも停止後にapplication stateへ適用しない。
- `RuntimeStopped`はruntime後処理完了の通知であり、window closeを再度開始するtriggerにはしない。

### 7.3 unit間の引き渡し

- unit_016から受け取る条件: 全action / dialogがfake application portでgreenである。
- unit_018へ渡す条件: production compositionでstartup、runtime event、100ms応答性、watchdog / error、shutdown、後着event無効化がgreenである。
- unit_018は本unitのsource-level契約を3 OS CIと実display acceptanceで検証し、機能を再設計しない。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/ui/event_bridge.py` | new | QObject、queued signal、receiver lifecycle |
| `src/demi/ui/main_window.py` | modify | snapshot refresh、runtime event、timer / dialog ownership |
| `src/demi/ui/application.py` | modify | startup、event loop、exception / shutdown hooks |
| `src/demi/application/ui_state.py` | new | Qt型を含まないimmutable UI snapshot |
| `src/demi/app.py` | modify | production composition rootとstartup / shutdown |
| `src/demi/application/shutdown.py` | modify | timer / receiver停止を含むordered shutdown |
| `src/demi/application/presentation.py` | verify / modify | adapter / connection / pairing / warning / error snapshot |
| `src/demi/controller/events.py` | verify | immutable runtime event契約 |
| `src/demi/controller/runtime.py` | verify | unit_012のcancellable closeと`RuntimeStopped` |
| `tests/unit/ui/test_event_bridge.py` | new | queued delivery、thread、receiver無効化 |
| `tests/unit/application/test_ui_state.py` | new | framework非依存snapshot |
| `tests/integration/lifecycle/test_qt_application_lifecycle.py` | new | startup / reconnect / failure / shutdown |
| `tests/integration/ui/test_qt_runtime_events.py` | new | event反映、watchdog / error、100ms応答性 |
| `spec/wip/unit_017/QT_RUNTIME_AND_LIFECYCLE_INTEGRATION.md` | modify | TDD状態、計測、所有権、引き渡し記録 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `rg -n "T[O]DO|T[B]D|x[x]x|前[回]|今[回]|一[旦]|上[述]|適[宜]|必要に応じ[て]" spec/wip/unit_017` | passed | 該当なし |
| `uv run pytest tests/integration/ui/test_qt_runtime_events.py -q -p no:cacheprovider` | passed | 2 passed。bridge自身がQObjectであり、worker emit直後はpresentation未変更、event処理後だけ主スレッドでreceiverを呼ぶ。7種のimmutable RuntimeEventはapplication session receiverへFIFOで到達する |
| `uv run pytest tests/unit/application/test_application_session.py tests/unit/application/test_ui_state.py tests/integration/ui/test_main_window_snapshot.py -q -p no:cacheprovider` | passed | 4 passed。Qt非依存source境界、session snapshot、MainWindowのtoolbar / status bar反映を確認した |
| `uv run pytest tests/unit/application/test_application_session.py tests/integration/ui/test_main_window_snapshot.py -q -p no:cacheprovider` | passed | 4 passed。adapter discoveryのsnapshot候補がConnectionDialogへ届き、0件と保存ID未検出で別adapterを自動選択しないことを確認した |
| `uv run pytest tests/unit/application/test_app.py tests/integration/ui/test_main_window_snapshot.py -q -p no:cacheprovider` | passed | 18 passed。connection / pairing busy表示、retryable error後の再試行、非retryable errorのaction抑止、重複connect / disconnect command抑止を確認した |
| `uv run pytest tests/unit/application/test_app.py -q -p no:cacheprovider` | passed | 15 passed。current epochのwatchdogとcontroller errorがneutral frameを出し、stale watchdogとunsafe error summaryを表示へ反映しないことを確認した |
| `uv run pytest tests/unit/application/test_app.py::test_session_reconnects_once_only_when_the_saved_adapter_is_discovered tests/unit/application/test_app.py::test_session_does_not_reconnect_for_a_missing_adapter_or_when_disabled -q -p no:cacheprovider` | passed | 2 passed。一致保存IDだけへConnectSavedを一度だけ発行し、disabled、0件、保存ID未検出でConnectSaved / StartPairingを発行しないことを確認した |
| `uv run pytest tests/unit/application/test_app.py::test_application_runner_assembles_boundaries_and_starts_the_runtime tests/integration/ui/test_application_lifecycle.py -q -p no:cacheprovider` | passed | 5 passed。runtime startとDiscoverAdapters発行、FIRST_RUN + adapter 0件、retryable reconnect failure後にもwindow設定actionが操作可能なことを確認した |
| `uv run pytest tests/integration/ui/test_application_lifecycle.py::test_qt_event_loop_stays_responsive_during_slow_runtime_operations -q -p no:cacheprovider` | passed | 1 passed。30ms worker delayのdiscovery / connect / disconnect中、GUI timerの隣接tick間隔は100ms未満 |
| `uv run pytest tests/integration/ui/test_application_lifecycle.py -q -p no:cacheprovider` | passed | 9 passed。settings load、window factory、runtime factory、runtime startの失敗でstatus 1と固定文のstderrを確認し、runtime factory失敗後のwindow closeとruntime start失敗後の逆順cleanupを確認した |
| `uv run pytest tests/integration/ui/test_application_lifecycle.py -q -p no:cacheprovider` | passed | 11 passed。Qt callback相当のmain-thread例外が安全なhookからneutral、runtime close、settings保存、window close、status 1へ進み、秘密値をstderrへ出さないことを確認した。KeyboardInterruptはcleanup後に伝播する |
| `uv run pytest tests/integration/ui/test_qt_runtime_events.py tests/unit/application/test_app.py -q -p no:cacheprovider` | passed | 19 passed。worker threadのretryable / non-retryable ControllerErrorがqueued delivery後にだけGUIを更新し、RuntimeStopped後はcapture coordinatorがshutdown状態となり全actionを無効化することを確認した |
| `uv run pytest tests/integration/ui/test_application_lifecycle.py tests/integration/ui/test_qt_runtime_events.py tests/unit/application/test_app.py -q -p no:cacheprovider` | passed | 31 passed。worker RuntimeStoppedが先にwindow closeを開始し、続くCtrl+Qとcloseでもinput timer teardown、runtime close、settings保存、native close callbackは各1回であることを確認した |
| `uv run pytest tests/integration/ui tests/unit/application/test_app.py tests/unit/ui/test_application.py -q -p no:cacheprovider` | passed | 67 passed。停止前にqueueしたworker event、後着timer timeout、dialog finished callbackがpresentation、widget、runtime commandを変更せず、既存のdialog / input / lifecycle契約も維持することを確認した |
| `uv run pytest tests/integration/ui tests/unit/application/test_app.py tests/unit/ui/test_application.py -q -p no:cacheprovider` | passed | 68 passed。worker RuntimeStoppedによる終了でQt objectの生成、refresh、shutdown、input timer teardown、window / timer破棄が主スレッドで行われ、event loop復帰後にtop-level widgetとactive timerが残らないことを確認した |
| `uv run ruff format --check src/demi/app.py src/demi/ui/application.py tests/integration/ui/test_application_lifecycle.py` | passed | 3 files already formatted |
| `uv run ruff check src/demi/app.py src/demi/ui/application.py tests/integration/ui/test_application_lifecycle.py` | passed | All checks passed |
| `uv run ty check --no-progress` | passed | All checks passed。runner所有windowの破棄境界とテスト補助型を確認した |
| `uv run ruff format --check src/demi/app.py src/demi/ui/application.py src/demi/ui/event_bridge.py src/demi/ui/main_window.py tests/integration/ui/test_qt_runtime_events.py` | passed | 5 files already formatted |
| `uv run ruff format --check src/demi/app.py tests/integration/ui/test_application_lifecycle.py` | passed | 2 files already formatted |
| `uv run ruff check src/demi/app.py tests/integration/ui/test_application_lifecycle.py` | passed | All checks passed |
| `uv run ruff format --check src/demi/app.py tests/integration/ui/test_qt_runtime_events.py` | passed | 2 files already formatted |
| `uv run ruff check src/demi/app.py tests/integration/ui/test_qt_runtime_events.py` | passed | All checks passed |
| `uv run ruff check src/demi/app.py src/demi/ui/application.py src/demi/ui/event_bridge.py src/demi/ui/main_window.py tests/integration/ui/test_qt_runtime_events.py` | passed | All checks passed |
| `uv run ruff format --check .` | passed | 118 files already formatted |
| `uv run ruff check .` | passed | All checks passed |
| `rg -n "os\._exit" src/demi` | passed | 該当なし |
| `uv run ruff format --check src/demi/ui/event_bridge.py tests/integration/ui/test_qt_runtime_events.py` | passed | 2 files already formatted |
| `uv run ruff check src/demi/ui/event_bridge.py tests/integration/ui/test_qt_runtime_events.py` | passed | All checks passed |
| `uv run ruff format --check src/demi/application/ui_state.py src/demi/app.py src/demi/ui/main_window.py tests/unit/application/test_application_session.py tests/unit/application/test_ui_state.py tests/integration/ui/test_main_window_snapshot.py` | passed | 6 files already formatted |
| `uv run ruff check src/demi/application/ui_state.py src/demi/app.py src/demi/ui/main_window.py tests/unit/application/test_application_session.py tests/unit/application/test_ui_state.py tests/integration/ui/test_main_window_snapshot.py` | passed | All checks passed |
| `uv run ruff format --check src/demi/application/ui_state.py src/demi/app.py src/demi/ui/main_window.py tests/unit/application/test_application_session.py tests/integration/ui/test_main_window_snapshot.py` | passed | 5 files already formatted |
| `uv run ruff check src/demi/application/ui_state.py src/demi/app.py src/demi/ui/main_window.py tests/unit/application/test_application_session.py tests/integration/ui/test_main_window_snapshot.py` | passed | All checks passed |
| `uv run ruff format --check src/demi/application/ui_state.py src/demi/app.py src/demi/ui/main_window.py src/demi/ui/toolbar.py tests/unit/application/test_app.py tests/integration/ui/test_main_window_snapshot.py` | passed | 6 files already formatted |
| `uv run ruff check src/demi/application/ui_state.py src/demi/app.py src/demi/ui/main_window.py src/demi/ui/toolbar.py tests/unit/application/test_app.py tests/integration/ui/test_main_window_snapshot.py` | passed | All checks passed |
| `uv run ty check --no-progress` | passed | All checks passed。QObjectの既存`emit` signatureとRuntimeEvent sinkをoverloadで両立し、snapshot型はQt importなしで公開した |
| `git diff --cached --check` | passed | first TDD itemのstaged diffにwhitespace errorなし |
| `uv sync --dev` | passed | Resolved 77 packages、Checked 74 packages |
| `uv lock --check` | passed | Resolved 77 packages |
| `uv run ruff format --check .` | passed | 118 files already formatted |
| `uv run ruff check .` | passed | All checks passed |
| `uv run ty check --no-progress` | passed | All checks passed |
| `uv run pytest tests/unit` | passed | 187 passed |
| `uv run pytest tests/integration` | passed | 54 passed |
| `uv build` | passed | `demi_controller-0.1.0.tar.gz` と `demi_controller-0.1.0-py3-none-any.whl` を生成 |
| `git diff --check` | passed | whitespace errorなし |
| GUI 100ms応答性probe | passed | 30ms遅延worker fakeによるdiscovery / connect / disconnect中、10ms GUI timerの隣接tick間隔が100ms未満 |

## 10. 先送り事項

| 観測 | 先送り理由 | 後続の置き場 |
|---|---|---|
| 3 OS source CIと実display挙動は未確認 | production composition完成後に同じ契約を各OSで検証する | `spec/complete/unit_018/QT_QUALITY_AND_OS_ACCEPTANCE.md` |
| 実Bluetooth operation中の100ms応答性は未測定 | hardwareと対象deviceが必要 | hardware acceptance / test log |
| PySide6 standaloneは未検証 | Qt plugin / license / clean環境を別artifact unitで扱う | milestone 7の後続unit |

## 11. チェックリスト

- [x] unit_014〜016のQt UI前提を確認した
- [x] Qt queued signalでworker eventをGUI threadへ渡した
- [x] adapter / connection / pairing / watchdog / errorを表示へ反映した
- [x] startup reconnect / adapter不在 / startup failureを確認した
- [x] unhandled exceptionの安全な終了を確認した
- [x] 100ms応答性probeを実行した
- [x] timer / signal / dialog / window / runtimeの所有権を固定した
- [x] runtime停止後のtimer / signal / callback無効化を確認した
- [x] application層がQt型へ依存しないことを確認した
- [x] TDD Test Listと検証結果を更新した
- [x] unit_018への引き渡し条件を満たした
