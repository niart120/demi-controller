# PySide6 application shell 仕様書

## 1. 概要

### 1.1 目的

UI 再設計 milestone 2 として、PySide6 6.x、`QApplication`、`QMainWindow`、window state、close / shutdown を最小構成で接続する。引数なし CLI から空の main window を起動して正常終了できる状態へ戻し、入力、controller preview、標準 control、runtime event の詳細は後続 unit に渡す。

`import demi` と `--version` は Qt display を初期化しない。Qt widget test は1 processにつき1個の `QApplication` を offscreen で共有し、Windows、macOS、Linux の source CI で機材なしに実行できることを確認する。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| milestone | milestone 2 の dependency、event loop、window、close、offscreen、3 OS 条件 | `spec/ui-redesign/MILESTONES.md` |
| target design | `QtApplicationRunner`、`MainWindow`、Qt主スレッド所有、遅延 import | `spec/ui-redesign/PYSIDE6_UI_DESIGN.md` |
| initial design | milestone 0で更新済みの application / lifecycle / testing 契約 | `spec/initial/architecture.md`, `spec/initial/lifecycle.md`, `spec/initial/testing.md` |
| completed behavior | CLI runner、settings load、window state、ordered shutdown の現行契約 | `spec/complete/unit_011/APPLICATION_ASSEMBLY_AND_GUI_WIRING.md`, `spec/complete/unit_012/CONTROLLER_RUNTIME_CANCELLABLE_SHUTDOWN.md` |
| prerequisite | pyglet と旧 UI の production / package 境界を撤去した状態 | `spec/complete/unit_013/LEGACY_UI_AND_PYGLET_REMOVAL.md` |

milestone 0 の初期仕様更新と unit_013 の撤去完了を着手条件とする。本 unit は PySide6 shell だけを所有し、入力・標準 control・production runtime 統合を先行実装しない。

milestone 0とunit_013は完了済みである。着手時に両方の完了記録を確認し、更新後の初期仕様とunit_013の引き渡し条件を入力にする。本unitの実装は未着手である。

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| CLI user | 引数なし `demi` / `project-demi` / `python -m demi` | 同じ Qt runner が main window を1つ表示し、event loop の終了 status を返す | adapter と display以外の機材を要求しない |
| package user | `import demi` または `--version` | Qt platform plugin、`QApplication`、windowを生成せず成功する | PySide6 importもGUI起動時まで遅延する |
| returning user | 保存済み window width / height / maximized | 有効な寸法と最大化状態でwindowを開始する | 最小 800x520 を下回らない |
| user | window close、Ctrl+Q、重複 close | shutdown coordinator を一度だけ要求し、settings と runtime のcloseを重複させず終了する | 後続runtime統合でも同じclose入口を使う |
| CI | offscreen platform、3 OS、機材なし | dependency installとshell/widget testが成功する | 実display受入の証拠にはしない |

## 2. 対象範囲

- PySide6 6.x の版範囲を決定し、runtime dependency と `uv.lock` に追加する。
- GUI 起動時だけ `QApplication` を1個生成し、`QApplication.exec()` のstatusをCLIへ返す runner を実装する。
- `QMainWindow` を唯一のtop-level main windowとして生成し、central placeholder、既定 960x640、最小 800x520、resizeを構成する。
- `WindowSettings.width`、`height`、`maximized` を開始時に適用し、close時に有効な状態を保存する。
- `closeEvent` と Ctrl+Q を `ApplicationShutdownCoordinator.request()` へ集約し、neutral、runtime close、settings save、window終了を一度だけ要求する。
- shutdown 成功時だけ close event を受理し、失敗時のstatusと安全な診断を既存application境界へ返せるようにする。
- `demi.app` / `demi.cli` からQt moduleを遅延 importし、module import、version、unknown argumentでdisplay初期化しない。
- widget test用にprocess内共有 `QApplication` fixtureと `QT_QPA_PLATFORM=offscreen` の設定を用意する。
- Windows、macOS、Linux のCIでPySide6 install、package import、CLI、offscreen shell testを実行する。
- source wheel / sdistをbuildし、PySide6 dependency metadataとQt shell moduleの同梱を確認する。

## 3. 対象外

- key / mouse eventの正規化、pointer capture、Raw Input、8ミリ秒入力評価、controller preview。unit_015が所有する。
- toolbar、status bar、mapping / connection / color dialog、model/view。unit_016が所有する。
- queued signalによるworker event delivery、startup reconnect、watchdog / errorのproduction接続。unit_017が所有する。
- 3 OSの実display、DPI、font、focus、pointer captureの受入。unit_018が所有する。
- PyInstaller hook、Qt plugin収集、standalone artifact、署名、配布サイズ。milestone 7の後続unitが所有する。
- application/domain/controller/configへQt型を導入する変更。

## 4. 関連 docs

- `spec/ui-redesign/README.md`
- `spec/ui-redesign/PYSIDE6_UI_DESIGN.md`
- `spec/ui-redesign/MILESTONES.md`
- `spec/initial/architecture.md`
- `spec/initial/configuration.md`
- `spec/initial/lifecycle.md`
- `spec/initial/testing.md`
- `spec/complete/unit_011/APPLICATION_ASSEMBLY_AND_GUI_WIRING.md`
- `spec/complete/unit_012/CONTROLLER_RUNTIME_CANCELLABLE_SHUTDOWN.md`
- `spec/complete/unit_013/LEGACY_UI_AND_PYGLET_REMOVAL.md`
- `AGENTS.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| Qt applicationを開始する | 引数なしCLI、application未生成 | `QApplication`を1つ作り、main windowを表示し、`exec()`のstatusを返す | 二重生成を禁止する |
| display-free境界を守る | import、version、unknown argument | `QApplication.instance()`が作られず、platform pluginを読み込まない | Qt importはrunner呼出し後 |
| window stateを適用する | 有効なwidth、height、maximized | 保存値、最小寸法、最大化状態が公開window stateで観測できる | pixel描画比較をしない |
| window stateを保存する | normal / maximized windowをclose | 有効なnormal寸法とmaximized flagをsettingsへ1回保存する | 最小未満や取得不能値は保存しない |
| closeを順序化する | closeEvent / Ctrl+Q / 重複要求 | shutdown coordinatorを1回呼び、成功後にwindowとevent loopを閉じる | runtime具象はfakeでよい |
| 初回起動する | settingsなし、adapterなし | 既定windowを表示し、shell自体は起動失敗にしない | 接続操作は未実装 |
| offscreen testする | `QT_QPA_PLATFORM=offscreen` | fixtureが1つのapplicationを共有し、window作成・closeが成功する | 実displayの支援証明ではない |
| 3 OS CIを実行する | Windows / macOS / Linux runner | install、import、CLI、unit / integration shell testが通る | source-level証拠として記録する |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-skipped | 引数なしCLIはPySide6 application runnerを一度だけ呼び、Qt event loopの終了statusを返す | regression | unit | `demi.app.run_application()`を引数なし分岐で遅延importし、3つのentry pointが戻り値をそのまま返す。Qt runnerの実装は後続項目で接続する |
| todo | module import、`--version`、unknown argumentは`QApplication`とmain windowを生成しない | regression | package | display-free subprocessで確認する |
| refactor-skipped | runnerは既存instanceを尊重し、同じprocessで`QApplication`を二重生成しない | edge | unit | offscreen session fixtureが生成した`QApplication`を`QtApplicationRunner`が再利用する。Qt型は`demi.ui.application`の内側に閉じ、application / domainへ渡さない |
| refactor-skipped | main windowは既定960x640、最小800x520、resize可能なshellとして開始する | regression | unit | `QtApplicationRunner.create_main_window()`が唯一のtop-level shellを生成し、`MainWindow`はQt widgetと中央placeholderだけを所有する |
| refactor-skipped | 保存済みwidth / height / maximizedはmain windowへ適用され、close時に有効なstateを保存する | regression | integration | `MainWindow`が`WindowSpec`を適用し、最大化中はnormal geometryから有効な`WindowSettings`を返す。repositoryへの保存はordered close項目で接続する |
| refactor-skipped | closeEventとCtrl+Qはneutral、runtime停止、settings保存、window終了を一度だけ要求する | regression | integration | `MainWindow.closeEvent()`と標準Quit actionを同じcallbackへ集約し、`ApplicationShutdownCoordinator`のneutralize → runtime close → settings save → capture finishを一度だけ実行する |
| todo | settingsなし・adapterなしでもempty main windowを表示し、ユーザーcloseでstatus 0となる | edge | integration | pairingやdiscoveryは開始しない |
| todo | offscreen fixtureはprocess内のapplicationを共有し、test終了後にtop-level windowを残さない | new | unit | test isolationを確認する |
| todo | Windows、macOS、Linux CIでPySide6 installとdisplay-free / offscreen shell testが成功する | new | package | Python 3.12 / 3.13の既存matrixを維持する |
| todo | wheel / sdist metadataが選定したPySide6 6.xを要求し、Qt shell moduleを含む | regression | package | `uv build`後に確認する |

## 7. 設計メモ

### 7.1 採用する境界

- `QtApplicationRunner` が `QApplication` の生成、main windowの生成、`exec()`、終了statusを所有する。CLIはrunnerの戻り値だけを扱う。
- `MainWindow` はQt objectを所有するが、settings、runtime、shutdownの具象実装を正本として持たない。意味のあるactionとframework非依存値をapplication境界へ渡す。
- `QApplication` はPython processで1つというQt契約に合わせ、test fixtureもproduction runnerも既存instanceを検出する。
- Qt moduleの遅延importはversion表示の速度だけでなく、displayのないpackage操作を壊さない公開契約としてtestする。
- offscreen test成功を実display、font、DPI、native focusの成功と解釈しない。

### 7.2 PySide6版範囲の決定

- 6.x内でPython 3.12 / 3.13と3 OSのwheelが提供され、`ty`と標準gateを通る範囲を実装時に選ぶ。
- 未検証の時点で具体的な下限・上限をこの仕様に推測で固定しない。選定結果は`pyproject.toml`、`uv.lock`、本unitの検証欄へ記録する。
- Qt moduleは`QtCore`、`QtGui`、`QtWidgets`から開始し、GPLのみのmoduleやQt WebEngineを追加しない。
- `PySide6>=6.11,<6.12`を選定し、lockした版は6.11.1である。2026-07-14に[PyPI project page](https://pypi.org/project/PySide6/)でPython 3.10以上3.15未満、Windows / macOS / Linuxのabi3 wheel提供を確認した。Project_DemiのPython 3.12 / 3.13 matrixを満たす。

### 7.3 unit間の引き渡し

- unit_013から受け取る条件: pyglet依存と旧UIが消え、version / import / source package buildが成立している。
- unit_015へ渡す条件: 引数なしCLIがQt shellを開始でき、window state、close、offscreen fixture、3 OS dependency testが成立している。
- unit_015は本unitのmain windowとapplication fixtureを再利用し、別のevent loopやtop-level windowを作らない。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `pyproject.toml` | modify | PySide6 6.x runtime dependency、Qt UI marker |
| `uv.lock` | modify | PySide6、Shiboken、Qt component lock |
| `src/demi/ui/__init__.py` | new | 新Qt UI packageの公開境界 |
| `src/demi/ui/application.py` | new | `QApplication` runnerと遅延import境界 |
| `src/demi/ui/main_window.py` | new | 最小`QMainWindow`、window state、close event |
| `src/demi/app.py` | modify | Qt runner / window factoryのproduction composition |
| `src/demi/cli.py` | modify | unit_013の一時エラーからQt runner起動へ復旧 |
| `src/demi/application/shutdown.py` | verify / modify | Qt closeから使う既存ordered shutdown契約 |
| `tests/conftest.py` | new / modify | offscreen platformとprocess共有`QApplication` fixture |
| `tests/unit/ui/test_application.py` | new | runner、遅延import、single application |
| `tests/unit/ui/test_main_window.py` | new | window寸法、最大化、close action |
| `tests/unit/test_cli.py` | modify | Qt runner dispatchとdisplay-free version契約 |
| `tests/integration/lifecycle/test_application_lifecycle.py` | modify | Qt shell startup / closeのfake境界 |
| `.github/workflows/ci.yml` | modify | 3 OSのQt dependency / offscreen test環境 |
| `tests/unit/test_ci.py` | modify | 3 OS shell gateのworkflow契約 |
| `spec/wip/unit_014/PYSIDE6_APPLICATION_SHELL.md` | modify | TDD状態、版選定、検証、引き渡し記録 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `rg -n "T[O]DO|T[B]D|x[x]x|前[回]|今[回]|一[旦]|上[述]|適[宜]|必要に応じ[て]" spec/wip/unit_014` | passed | 該当なし |
| `git diff --no-index --check -- NUL spec/wip/unit_014/PYSIDE6_APPLICATION_SHELL.md` | passed | whitespace errorなし。LF / CRLF変換予告のみ |
| `uv run pytest tests/unit/test_cli.py -q -p no:cacheprovider` | expected failed (2 failed, 5 passed) | red: 引数なしCLI、module entry point、packaging launcherが一時error status 1を返した |
| `uv run pytest tests/unit/test_cli.py -q -p no:cacheprovider` | passed (7 passed) | green: 3つのentry pointが同じ遅延import済みapplication runnerを1回ずつ呼び、runner statusを返す |
| `uv run pytest tests/unit/ui/test_application.py -q -p no:cacheprovider` | expected failed (collection error) | red: `demi.ui.application`が存在しなかった |
| `uv add "PySide6>=6.11,<6.12"` | passed | PySide6、PySide6_Addons、PySide6_Essentials、shiboken6を6.11.1でlockし、development environmentへ導入した |
| `uv run pytest tests/unit/ui/test_application.py -q -p no:cacheprovider` | passed (1 passed) | green: offscreen fixtureの`QApplication`をrunnerが再利用した |
| `uv lock --check` | passed | 77 packagesでmetadataとlockfileの整合を確認した |
| `uv run pytest tests/unit/ui/test_application.py -q -p no:cacheprovider` | expected failed (1 failed, 1 passed) | red: runnerにmain window生成がなかった |
| `uv run pytest tests/unit/ui/test_application.py -q -p no:cacheprovider` | passed (2 passed) | green: 既定寸法、最小寸法、central placeholder、resizeをoffscreenで確認した |
| `uv run pytest tests/unit/ui/test_application.py -q -p no:cacheprovider` | expected failed (1 failed, 2 passed) | red: 保存済み`maximized=True`がmain windowへ適用されなかった |
| `uv run pytest tests/unit/ui/test_application.py -q -p no:cacheprovider` | passed (3 passed) | green: 最大化中のnormal sizeと通常表示後のresizeを`WindowSettings`へ保存できた |
| `uv run pytest tests/unit/ui/test_application.py -q -p no:cacheprovider` | expected failed (1 failed, 3 passed) | red: main windowにshutdown callbackの接続口がなかった |
| `uv run pytest tests/unit/ui/test_application.py -q -p no:cacheprovider` | passed (4 passed) | green: closeEvent、重複close、標準Quit actionが同じcallbackを一度だけ通す |
| `uv run pytest tests/integration/ui/test_application_lifecycle.py -q -p no:cacheprovider` | passed (1 passed) | integration: Qt Quitから既存ordered shutdownへ接続し、neutralize、runtime close、settings save、capture finishの順序と冪等性を確認した |
| `uv sync --dev` | not run | `uv add`はdependency解決とenvironment更新を実行済み。標準gateの同一commandはunit完了時に再実行する |
| `uv run ruff format --check .` | not run | 仕様執筆だけでPython sourceを変更していない |
| `uv run ruff check .` | not run | 仕様執筆だけでPython sourceを変更していない |
| `uv run ty check --no-progress` | not run | PySide6境界の型は実装後に確認する |
| `uv run pytest tests/unit` | not run | Qt shell未実装のため |
| `uv run pytest tests/integration` | not run | Qt lifecycle未実装のため |
| `uv build` | not run | package metadata未変更。実装時は必須 |

## 10. 先送り事項

| 観測 | 先送り理由 | 後続の置き場 |
|---|---|---|
| Qt inputとcontroller previewは未実装 | shellの生存期間と入力契約を分離する | `spec/wip/unit_015/QT_INPUT_AND_CONTROLLER_PREVIEW.md` |
| 標準toolbar / dialogは未実装 | controlの挙動をinput復旧後に扱う | `spec/wip/unit_016/QT_STANDARD_CONTROLS_AND_DIALOGS.md` |
| production worker eventとstartup reconnectは未接続 | queued signalとruntime ownershipを別に検証する | `spec/wip/unit_017/QT_RUNTIME_AND_LIFECYCLE_INTEGRATION.md` |
| 実displayとstandaloneは未検証 | source acceptanceとartifact packagingを分離する | unit_018、milestone 7 |

## 11. チェックリスト

- [x] milestone 0とunit_013の前提を確認した
- [x] PySide6 6.xの版範囲を根拠とともに固定した
- [ ] QApplication / QMainWindow / event loopを最小構成で接続した
- [ ] window stateとordered closeを接続した
- [ ] import / versionのdisplay-free契約を維持した
- [ ] offscreen fixtureと3 OS dependency testを追加した
- [ ] `uv lock --check`と`uv build`を含むgateを記録した
- [ ] TDD Test Listを更新した
- [ ] unit_015への引き渡し条件を満たした
