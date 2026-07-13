# Qt 入力と controller preview 仕様書

## 1. 概要

### 1.1 目的

UI 再設計 milestone 3 として、Qt key / mouse / focus event、framework 非依存の pointer capture、Windows Raw Input、8ミリ秒入力評価、`QPainter` controller previewを接続する。入力評価で生成した同一の`ControllerFrame`をruntime送信先とpreviewへ渡し、capture解除後は保持入力と未消費deltaを破棄してneutralへ戻す。

Windowsでは`QAbstractNativeEventFilter`を入口にWin32 `WM_INPUT`を処理し、未加速の相対移動量を取得する。GLFWは追加しない。macOS / Linuxのfallbackは補正後の相対値または利用不能として明示し、未検証の値をrawと表示しない。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| milestone | milestone 3の入力、capture、timer、preview、実display条件 | `spec/ui-redesign/MILESTONES.md` |
| target UI | Qt input adapter、pointer port、preview、timer分離 | `spec/ui-redesign/PYSIDE6_UI_DESIGN.md` |
| pointer decision | native event filter、Win32 Raw Input、capability、GLFW不採用 | `spec/ui-redesign/RELATIVE_MOUSE_INPUT.md` |
| initial contracts | input mode、mapping、`ControllerFrame`、neutralization、8ms / 60Hz | `spec/initial/input.md`, `spec/initial/lifecycle.md`, `spec/initial/requirements.md` |
| completed behavior | `CaptureCoordinator`、`InputPublisher`、既存frame共有の履歴 | `spec/complete/unit_004/UI_AND_PYGLET.md`, `spec/complete/unit_011/APPLICATION_ASSEMBLY_AND_GUI_WIRING.md` |
| prerequisite | PySide6 application shellとoffscreen fixture | `spec/complete/unit_014/PYSIDE6_APPLICATION_SHELL.md` |

milestone 0、unit_013、unit_014の完了を着手条件とする。本unitは入力とpreviewだけを所有し、toolbar / settings dialogとproduction runtime event統合は後続unitへ渡す。

仕様執筆時点では上記の実装前提は未完了である。着手時に更新後の初期仕様と unit_013、unit_014 の完了記録を確認する。

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| user | main windowにfocusがあり、入力captureを開始 | key / mouse保持と相対移動が8ms評価へ入り、previewを更新する | global hookは使わない |
| Windows user | capture中に1000 Hz mouseを画面端へ継続移動 | Raw Inputのrelative deltaを欠落なく加算し、1評価周期で1回消費する | foreground windowだけを受信先にする |
| user | F12、focus loss、dialog open、shutdown | captureを解除し、保持入力、delta、仮想姿勢を消去し、neutral frameを発行する | 自動再captureしない |
| application | 8ms評価で`ControllerFrame`を生成 | 同じframeをruntime portとpreviewへ渡す | preview用に再計算しない |
| user | controller previewを見る | button、stick、gyro、accel、capture状態を最大60Hzで観測する | pixel完全一致を要件にしない |
| non-Windows user | raw backendがない環境でcapture | 補正後値か利用不能をcapabilityとして表示する | raw支援済みと記録しない |

## 2. 対象範囲

- Qt key press / release、mouse button press / release、focus / deactivateをdomain sourceと`CaptureCoordinator`へ変換する`QtInputAdapter`を実装する。
- auto-repeatを含む重複pressと未保持releaseを冪等に扱い、Qt enum値やlocalized文字列をsettingsへ保存しない。
- 旧`WindowPort.set_exclusive_mouse()`を`PointerCapturePort.set_pointer_capture(enabled)`へ変更し、application / domainにQt型を持ち込まない。
- pointer captureの開始、解除、cursor表示、window focus、capture epochを1つのcoordinatorで管理する。
- `RelativePointerBackend`のcapabilityを`RAW_UNACCELERATED`、`RELATIVE_ACCELERATED`、`UNAVAILABLE`として区別する。
- Windowsで`QAbstractNativeEventFilter`と`ctypes`によるWin32 Raw Input backendを実装する。
- main windowのnative handle確定後にforeground mouse deviceを1箇所へ登録し、capture終了時に登録解除する。
- `WM_INPUT`のrelative `lLastX` / `lLastY`を1評価周期内で加算し、absolute input、対象外message、古いcapture epochをcontroller入力へ流さない。
- `RIDEV_INPUTSINK`と`RIDEV_NOLEGACY`を使わず、通常のQt button / dialog mouse eventを維持する。
- registration / read失敗を分類し、登録失敗時はcaptureを開始せず、連続read失敗時はcapture解除と安全な警告へ戻す。
- macOS / LinuxはQt通常eventのfallbackを実装し、未加速を確認できない値を`RELATIVE_ACCELERATED`として報告する。取得不能時は`UNAVAILABLE`とする。
- `Qt.TimerType.PreciseTimer`の8ミリ秒入力評価timerを接続し、実際の間隔を診断計測できるようにする。
- `ControllerPreviewWidget`を`QWidget` / `QPainter`で実装し、body、button、stick、gyro、accel、capture overlayを`ControllerFrame`とcolor settingsだけから描画する。
- previewの`update()`要求を最大60Hzへ制限し、paint event内でruntime、input、settingsを変更しない。
- Windows実displayでF12、focus loss、画面端、1000 Hz mouse、通常Qt操作との共存を手動確認する。

## 3. 対象外

- mapping / connection / color dialogの実装とdialog内入力の最終UI。unit_016が所有する。本unitはdialog open時にneutralizeできるportを用意する。
- adapter discovery、connect / disconnect、pairing、watchdog / errorのproduction表示。unit_017が所有する。
- macOSの`NSEvent` raw判定、XInput2、Wayland native protocolの専用backend。計測後の後続候補とする。
- mouse deviceごとの分離、background capture、global hook、keyboard排他。
- GLFW dependency、GLFW window、GLFW event loop。
- 実機Bluetooth入力、controller renderingのpixel完全一致、公式画像・ロゴ。
- PyInstaller / standaloneにおけるQt pluginとnative backend収集。milestone 7の後続unitが所有する。

## 4. 関連 docs

- `spec/ui-redesign/PYSIDE6_UI_DESIGN.md`
- `spec/ui-redesign/RELATIVE_MOUSE_INPUT.md`
- `spec/ui-redesign/MILESTONES.md`
- `spec/initial/input.md`
- `spec/initial/lifecycle.md`
- `spec/initial/requirements.md`
- `spec/initial/testing.md`
- `spec/complete/unit_003/INPUT_PIPELINE.md`
- `spec/complete/unit_011/APPLICATION_ASSEMBLY_AND_GUI_WIRING.md`
- `spec/complete/unit_014/PYSIDE6_APPLICATION_SHELL.md`
- `AGENTS.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| keyを正規化する | Qt key press / release、modifier、auto-repeat | `KeySource`保持を冪等に更新する | F12はmappingへ流さない |
| mouse buttonを正規化する | left / middle / right / extra button | `MouseButtonSource`保持を冪等に更新する | capture外はcontroller入力にしない |
| captureを開始する | focusあり、dialogなし、backend利用可能 | backend登録、epoch更新、初期neutral、CAPTUREDへ遷移 | 失敗時はIDLEを維持する |
| captureを解除する | F12 / focus loss / dialog open / shutdown | backend解除、input / delta / yaw-pitch reset、capture外neutral | 後着eventはepochで破棄する |
| Windows raw deltaを受ける | 対象windowのrelative `WM_INPUT` | dx / dyを加算し、8ms評価で1回だけ消費する | filterはQt eventを消費しない |
| 不正native inputを無視する | absolute flag、対象外message、古いepoch | frameとdeltaを変更しない | native pointerをdomainへ渡さない |
| capabilityを表示する | backend選定 / failure | `Raw`、`OS補正あり`、`利用不可`を区別する | 色だけに依存しない |
| frameを共有する | 8ms入力評価 | runtime portとpreviewが同一frameを観測する | 未接続でもpreviewは更新する |
| previewを描画する | 完全なframeと4色 | button、stick、gyro、accel、captureを描画modelへ反映する | official assetを使わない |
| repaintを制限する | 8msでframe更新、描画要求が連続 | `update()`要求は最大60Hz、最新frameを描画する | 同期repaintを強制しない |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-skipped | Qt keyとmouse press / releaseは正規化された保持状態を冪等に更新し、capture外ではcontroller mappingを変更しない | regression | unit | `QtInputAdapter`がcapture中のeventだけを`PhysicalInputState`へ変換する。auto-repeatと未保持releaseは既存stateの冪等性で吸収し、Back buttonは`BUTTON_4`へ正規化する |
| refactor-skipped | F12、focus loss、dialog open、shutdownはpointer captureを解除し、input / delta /姿勢をclearしてneutral frameを発行する | regression | integration | `QtInputAdapter`はF12・focus・dialog callbackだけを受け、`CaptureCoordinator`がcapture epoch、pointer release、state clear、neutral frameを所有する。focus復帰後はIDLEへ戻るが自動再captureしない |
| refactor-skipped | framework非依存`PointerCapturePort`でapplication試験を実行でき、application / domainがPySide6をimportしない | new | unit | `CaptureCoordinator`は`set_pointer_capture(enabled)`だけを要求し、`MainWindow`がQtのmouse grabとcursorを実装する。current source / testから`set_exclusive_mouse`を撤去した |
| refactor-skipped | native event filterは対象外messageを消費せず、Qtの通常処理へ返す | new | unit | `WindowsRawInputFilter`はQtのnative filterを実装し、Windows / 非Windowsの対象外messageへ常に`False`を返す |
| refactor-skipped | capture開始はmain windowをRaw Input mouseの唯一のforeground受信先として登録し、終了時に解除する | new | unit | `WindowsRawInputBackend`は`RawInputRegistrar`を境界に、mouse usage page `0x01` / usage `0x02`をmain window handleへflags `0`で登録する。別windowの二重登録は拒否し、解除は`RIDEV_REMOVE`とnull handleを使う |
| refactor-skipped | relative `WM_INPUT` deltaは1評価周期内で加算され1回だけ消費される | new | unit | `CtypesRawInputReader`は`GetRawInputData`でcopied payloadを取得し、pointerを外へ出さず`RawMousePacket`へ変換する。複数のrelative packetを`PhysicalInputState`へ加算し、`InputPublisher`の1評価で消費する |
| refactor-skipped | absolute input、capture外、古いepoch、対象外windowのnative eventはframeへ反映されない | edge | integration | `MOUSE_MOVE_ABSOLUTE`、capture token、Qt main window handleを確認してからdeltaを渡す。integration testは許可されたrelative eventだけで生成したframeとの完全一致で検証する |
| todo | Raw Input登録失敗はcaptureを開始せず、連続read失敗はcapture解除と安全な警告を返す | edge | integration | tracebackをUIへ出さない |
| todo | fallback backendは補正後値と利用不能を区別し、未確認値を`RAW_UNACCELERATED`と報告しない | new | unit | macOS / Linux capability契約 |
| todo | Raw Input登録中もQtのbutton、focus、dialog用mouse eventが通常どおり届く | regression | integration | legacy eventを抑止しない |
| todo | 8ミリ秒評価で生成した同一`ControllerFrame`をruntime portとpreviewが観測する | regression | integration | identityまたは完全な値一致を確認 |
| todo | previewはbutton、stick、gyro、accel、capture、colorを1つのframe modelから更新する | regression | unit | pixel完全一致を要求しない |
| todo | frameが8ミリ秒で更新されてもpreviewの再描画要求は最大60Hzとなり、常に最新frameを使う | new | unit | fake clock / timerで確認 |
| todo | Windows実displayで画面端、1000 Hz mouse、通常Qt操作、focus loss、F12解除を確認する | new | manual | OS、mouse、DPI、観測値を記録する |

## 7. 設計メモ

### 7.1 pointer backend

- `QAbstractNativeEventFilter`はRaw Inputそのものではなく、Qt event dispatcherからnative messageへ到達するhookとして使う。
- Windows backendはprocess内1個とし、dialogやpreview widgetが個別登録しない。foreground入力だけを扱い、background captureはしない。
- native filterは対象messageを処理した後も`False`を返し、Qtの通常mouse eventを壊さない。
- backend切替時はcaptureを停止し、deltaと`YawPitchModel`をresetして新しいepochを開始する。異なるqualityを同じepochへ混在させない。
- 8msは目標周期であり実時間保証ではない。平均、95、99 percentileと250ms watchdog誤発火を後続acceptanceで記録する。

### 7.2 preview

- 描画modelへの変換はQt objectを返さない純粋境界として試験可能にする。
- `paintEvent()`は保存済み最新frameを読み、`QPainter`で描画するだけとする。domain state、settings、runtimeを更新しない。
- 同期的な`repaint()`連打を避け、60Hz limiterが`update()`を要求する。

### 7.3 unit間の引き渡し

- unit_014から受け取る条件: single `QApplication`、main window、close、offscreen fixtureが成立している。
- unit_016へ渡す条件: Qt入力、capture neutralization、capability表示用値、8ms frame、60Hz previewがfake runtimeで成立している。
- unit_016はdialog表示中のkey / mouseを標準controlへ優先し、本unitの`dialog open` neutralization portを呼ぶ。
- unit_017は本unitのtimerとframe sinkをproduction runtimeへ接続し、shutdown時の停止所有権を確定する。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/application/coordinator.py` | modify | `PointerCapturePort`、capture epoch、neutralization |
| `src/demi/domain/physical_input.py` | verify / modify | backend qualityを含まない正規化入力の維持 |
| `src/demi/input/qt_adapter.py` | new | Qt key / mouse / focus event正規化 |
| `src/demi/input/relative_pointer.py` | new | framework非依存motion / capability契約 |
| `src/demi/platform/windows_raw_input.py` | new | native event filter、Win32登録、`WM_INPUT`読出し |
| `src/demi/ui/controller_preview.py` | new | frame model、`QPainter` widget、60Hz更新 |
| `src/demi/ui/main_window.py` | modify | input adapter、capture、preview、timerの所有 |
| `src/demi/app.py` | modify | pointer backendとframe fan-outのcomposition |
| `tests/unit/input/test_qt_adapter.py` | new | key / mouse / focus正規化 |
| `tests/unit/input/test_relative_pointer.py` | new | capability、delta、epoch |
| `tests/unit/platform/test_windows_raw_input.py` | new | Win32 API fakeとnative message |
| `tests/unit/ui/test_controller_preview.py` | new | frame modelと60Hz更新 |
| `tests/integration/ui/test_qt_input_capture.py` | new | capture / neutral / frame共有 |
| `spec/wip/unit_015/QT_INPUT_AND_CONTROLLER_PREVIEW.md` | modify | TDD状態、計測、OS受入、引き渡し記録 |

実装時にmodule名を調整してよいが、Qt event変換、native backend、framework非依存port、preview描画の責務は混在させない。

## 9. 検証

| command | result | notes |
|---|---|---|
| `rg -n "T[O]DO|T[B]D|x[x]x|前[回]|今[回]|一[旦]|上[述]|適[宜]|必要に応じ[て]" spec/wip/unit_015` | passed | 該当なし |
| `git diff --no-index --check -- NUL spec/wip/unit_015/QT_INPUT_AND_CONTROLLER_PREVIEW.md` | passed | whitespace errorなし。LF / CRLF変換予告のみ |
| `uv run pytest tests/unit/input/test_qt_adapter.py -q -p no:cacheprovider` | expected failed (collection error) | red: `demi.input.qt_adapter`が存在しなかった |
| `uv run pytest tests/unit/input/test_qt_adapter.py -q -p no:cacheprovider` | passed (1 passed) | green: capture外の無変更、key / extra mouse button、auto-repeat、未保持release、Qt通常処理への非消費を確認した |
| `uv run ruff format --check tests/unit/input/test_qt_adapter.py src/demi/input/qt_adapter.py` / `uv run ruff check tests/unit/input/test_qt_adapter.py src/demi/input/qt_adapter.py` / `uv run ty check --no-progress` | passed | formatter、lint、PySide6型境界を確認した |
| `uv run pytest tests/integration/ui/test_qt_input_capture.py -q -p no:cacheprovider` | expected failed (1 failed) | red: `QtInputAdapter`にF12、focus、dialogのcapture callbackがなかった |
| `uv run pytest tests/integration/ui/test_qt_input_capture.py -q -p no:cacheprovider` | passed (1 passed) | green: F12、focus loss / gain、dialog open、shutdownがpointer release、state / delta clear、neutral frameを一度ずつ要求し、自動再captureしないことを確認した |
| `uv run pytest tests/unit/input/test_qt_adapter.py tests/integration/ui/test_qt_input_capture.py -q -p no:cacheprovider` / `uv run ruff format --check <changed files>` / `uv run ruff check <changed files>` / `uv run ty check --no-progress` | passed | Qt event adapterとcapture neutralizationの回帰、formatter、lint、型境界を確認した |
| `uv run pytest tests/unit/application/test_pointer_capture_boundary.py -q -p no:cacheprovider` | expected failed (collection error) | red: `PointerCapturePort`がapplication境界に存在しなかった |
| `uv run pytest tests/unit/application/test_pointer_capture_boundary.py tests/unit/application/test_coordinator.py tests/unit/application/test_application_session.py tests/unit/application/test_app.py tests/integration/ui/test_settings_modal.py tests/integration/ui/test_qt_input_capture.py -q -p no:cacheprovider` | passed (23 passed) | green: port経由のcapture enable / release、既存application / integration回帰、application / domainにPySide6 importがないことを確認した |
| `rg -n "set_exclusive_mouse" src tests --glob "*.py"` | passed | 該当なし |
| `uv run ruff format --check <changed files>` / `uv run ruff check <changed files>` / `uv run ty check --no-progress` / `git diff --check` | passed | formatter、lint、型境界、whitespaceを確認した |
| `uv run pytest tests/unit/platform/test_windows_raw_input.py -q -p no:cacheprovider` | expected failed (collection error) | red: `demi.platform.windows_raw_input`が存在しなかった |
| `uv run pytest tests/unit/platform/test_windows_raw_input.py -q -p no:cacheprovider` / `uv run ruff format --check tests/unit/platform/test_windows_raw_input.py src/demi/platform` / `uv run ruff check tests/unit/platform/test_windows_raw_input.py src/demi/platform` / `uv run ty check --no-progress` / `git diff --check` | passed (1 passed) | green: Qt native filterを継承し、`windows_generic_MSG`と非Windows event typeの対象外messageを消費せず返すことを確認した |
| `uv run pytest tests/unit/platform/test_windows_raw_input.py -q -p no:cacheprovider` | expected failed (collection error) | red: Raw Input mouse usage定数と`WindowsRawInputBackend`が存在しなかった |
| `uv run pytest tests/unit/platform/test_windows_raw_input.py -q -p no:cacheprovider` / `uv run ruff format --check tests/unit/platform/test_windows_raw_input.py src/demi/platform` / `uv run ruff check tests/unit/platform/test_windows_raw_input.py src/demi/platform` / `uv run ty check --no-progress` / `git diff --check` | passed (2 passed) | green: fake registrarでmain windowだけをforeground登録し、`RIDEV_INPUTSINK` / `RIDEV_NOLEGACY`なし、別window拒否、`RIDEV_REMOVE`とnull handleの解除を確認した |
| `uv run pytest tests/unit/platform/test_windows_raw_input.py -q -p no:cacheprovider` | expected failed (collection error) | red: `WM_INPUT`、native message reader、raw mouse payload decoderが存在しなかった |
| `uv run pytest tests/unit/platform/test_windows_raw_input.py -q -p no:cacheprovider` / `uv run ruff format --check tests/unit/platform/test_windows_raw_input.py src/demi/platform` / `uv run ruff check tests/unit/platform/test_windows_raw_input.py src/demi/platform` / `uv run ty check --no-progress` / `git diff --check` | passed (3 passed) | green: copied Win32 `RAWINPUT` mouse structure fixtureを3件注入し、relative deltaの加算と8ms評価での一回消費、filterの非消費を確認した |
| `uv run pytest tests/unit/platform/test_windows_raw_input.py tests/integration/ui/test_windows_raw_input_capture.py -q -p no:cacheprovider` | expected failed (collection error) | red: absolute flagとcapture epoch / target windowのreject境界が存在しなかった |
| `uv run pytest tests/unit/platform/test_windows_raw_input.py tests/integration/ui/test_windows_raw_input_capture.py -q -p no:cacheprovider` / `uv run ruff format --check src/demi/platform tests/unit/platform/test_windows_raw_input.py tests/integration/ui/test_windows_raw_input_capture.py` / `uv run ruff check src/demi/platform tests/unit/platform/test_windows_raw_input.py tests/integration/ui/test_windows_raw_input_capture.py` / `uv run ty check --no-progress` / `git diff --check` | passed (4 passed) | green: absolute、capture外、異なるwindow、古いepochのeventを捨て、許可されたrelative eventだけで生成した`ControllerFrame`との一致を確認した |
| `uv run ruff format --check .` | not run | 仕様執筆だけでPython sourceを変更していない |
| `uv run ruff check .` | not run | 仕様執筆だけでPython sourceを変更していない |
| `uv run ty check --no-progress` | passed | current Qt input adapterの型境界を確認した。ctypes / Protocol境界は後続itemで追加する |
| `uv run pytest tests/unit` | not run | Qt input / preview未実装のため |
| `uv run pytest tests/integration` | not run | capture / frame共有未実装のため |
| `uv build` | not run | 仕様執筆だけでsource packageを変更していない。実装完了時に実行する |
| Windows実display / 1000 Hz mouse受入 | not run | native backendと対象Windows環境が必要 |
| macOS / Linux pointer capability受入 | not run | 対象desktop環境が必要。未実行を支援済みと記録しない |

## 10. 先送り事項

| 観測 | 先送り理由 | 後続の置き場 |
|---|---|---|
| macOS native motionの加速有無は未検証 | 対象hardware / OSで比較が必要 | unit_018のOS受入または専用backend unit |
| X11 / Waylandのraw motionは未実装 | compositor / QPA別の計測が必要 | unit_018のOS受入後に専用backend unitを判断 |
| toolbar / dialogの入力優先は未実装 | Qt標準controlのfocusとkeyboard操作を同時に検証する | `spec/wip/unit_016/QT_STANDARD_CONTROLS_AND_DIALOGS.md` |
| production runtimeへのframe接続とtimer停止所有権は未完了 | lifecycle全体でsignal / timerを停止する必要がある | `spec/wip/unit_017/QT_RUNTIME_AND_LIFECYCLE_INTEGRATION.md` |

## 11. チェックリスト

- [x] unit_014のapplication shell前提を確認した
- [ ] Qt key / mouse / focus adapterを実装した
- [x] framework非依存pointer capture portへ変更した
- [ ] Windows native event filterとRaw Inputを実装した
- [ ] GLFWをdependencyへ追加していない
- [ ] capability、neutralization、8ms評価を確認した
- [ ] QPainter previewと最大60Hz更新を確認した
- [ ] Windows実displayの手動結果を記録した
- [ ] macOS / Linuxの未実行事項を支援済みと記録していない
- [ ] TDD Test Listと検証結果を更新した
- [ ] unit_016 / unit_017への引き渡し条件を満たした
