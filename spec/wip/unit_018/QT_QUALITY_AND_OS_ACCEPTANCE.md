# Qt 品質 gate と OS 受入 仕様書

## 1. 概要

### 1.1 目的

UI 再設計 milestone 6 として、unit_013〜017で実装したPySide6 / Qt Widgets UIをsource実行とwheel配布の範囲で受け入れる。標準gate、対象integration test、`ty`、Windows / macOS / Linux source CI、実display、DPI、font、focus、pointer capture、利用者文書、初期仕様、診断、license notice、pyglet残存検索を1つの完了記録へ集約する。

PyInstaller / standalone artifactのbuild、Qt plugin収集、署名、clean environment standalone smokeは本unitの対象外とし、milestone 7へ送る。source / wheelの成功をstandalone支援の証拠として扱わない。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| milestone | milestone 6のfull gate、3 OS、manual acceptance、docs、残存検索、source / wheel契約 | `spec/ui-redesign/MILESTONES.md` |
| redesign package | 採用判断、未検証事項、license / portability、standalone分離 | `spec/ui-redesign/README.md`, `spec/ui-redesign/PYSIDE6_UI_DESIGN.md` |
| initial quality | 標準gate、CI、OS / hardware証拠の分離 | `spec/initial/QUALITY_GATES.md`, `spec/initial/testing.md` |
| previous OS / packaging | source CIとstandalone履歴、未検証display | `spec/complete/unit_009/OS_PORTABILITY.md`, `spec/complete/unit_010/PACKAGING.md` |
| prerequisites | UI再設計milestone 1〜5の作業仕様と検証結果 | `spec/complete/unit_013/`〜`spec/complete/unit_015/`、`spec/wip/unit_016/`〜`spec/wip/unit_017/` |

milestone 0とunit_013〜017の完了を着手条件とする。本unitは既存behaviorを再設計せず、品質gate、OS evidence、public text、source / wheel契約の不足を修正して受入結果を記録する。

仕様執筆時点では上記の実装前提は未完了である。着手時に更新後の初期仕様と unit_013〜017 の完了記録を確認する。

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| maintainer | standard gateと対象integration testを実行 | lock、format、lint、type、unit、integration、build、whitespaceがgreen | warningを未確認のまま成功扱いにしない |
| CI | Windows / macOS / Linux source matrix | dependency install、offscreen Qt、unit / integration、buildが成功する | 実displayの証拠ではない |
| desktop user | sourceからGUIを起動 | window、font、DPI、focus、capture、F12、closeが対象OSで観測できる | 実施環境を記録する |
| wheel user | clean Python環境へwheelをinstallしGUIを起動 | PySide6 dependencyが解決され、同じQt runnerが起動 / closeする | standalone executableではない |
| support user | diagnosticsを確認 | OS、Python、Project_Demi、swbt、PySide6、Qt、pointer capabilityを確認できる | pyglet版と秘密値を含めない |
| license reader | source / wheelのnoticeを確認 | Project licenseとPySide6 / Qtの利用条件・noticeへの到達経路がある | 法的判断完了とは記録しない |

## 2. 対象範囲

- `uv sync --dev`、`uv lock --check`、ruff format / lint、`ty`、unit、integration、`uv build`、`git diff --check`を実行する。
- Qt / PySide6 boundaryの型を確認し、production全域へ広がる`Any`、理由のない`# type: ignore`、Qt型のapplication / domain流入を残さない。
- Windows、macOS、Linuxのsource CIでPySide6 dependency install、display-free import / version、offscreen widget、unit / integration、source package buildを実行する。
- CI workflowと3 OS source gateをrepository testで固定する。
- Windowsのsource GUI smokeを実displayで実行し、起動、window size、font、DPI scale、focus、Tab / dialog、pointer capture、F12、画面端、closeを記録する。
- macOS / Linuxでも実display acceptanceを実行できる環境では同じ項目を記録する。未実行の場合はOS / display server / compositor、未実行理由、制約、後続確認先を記録し、確認済みと表記しない。
- 入力評価間隔の平均 / 95 / 99 percentile、preview最大60Hz、100ms GUI応答性、250ms watchdog誤発火の診断値を対象環境で記録する。
- READMEのsource起動、支援範囲、pointer capability、standalone停止状態を実装結果へ合わせる。
- `spec/initial`のrequirements、architecture、input、lifecycle、testing、risks、UI、診断項目をPySide6実装結果へ同期する。完了済みunit履歴は変更しない。
- diagnosticsをPySide6 / Qt versionとpointer backend capabilityへ更新し、pyglet versionをcurrent snapshotから削除する。
- source / wheel配布で必要なProject、PySide6、Qt、third-party license / noticeの到達経路を文書化し、取得できるlicense fileを検証する。
- `src`、現行test、`pyproject.toml`、`uv.lock`、`packaging`、README、`spec/initial`でpyglet current dependency / import /収集 /採用指示が0件であることを検索する。
- `spec/complete`と`spec/ui-redesign`にある履歴・移行説明は残存0件判定から除外し、current採用指示ではないことを明示する。
- source checkoutからの3 entry pointと、clean環境へinstallしたwheelからのGUI起動 / close契約を自動smokeで確認する。
- unit_013〜018のchecklist、TDD status、実行command、結果、未実行理由、先送り先を横断確認する。

## 3. 対象外

- PyInstaller / Nuitkaによるstandalone build、one-file / one-folder選定。
- Qt platform plugin、DLL、framework、native backend、license fileのstandalone artifact収集。
- 3 OS standalone artifactのclean environment GUI smoke、起動時間、artifact size、署名、macOS app bundle。
- `.github/workflows/package.yml`のartifact release再開とtag release gate。
- Bluetooth / target deviceを使うpairing、reconnect、inputのhardware acceptance。
- macOS native raw pointer、XInput2、Wayland protocolの新backend実装。unit_015で記録したcapabilityを受け入れる。
- GPLのみのQt module、QML、Qt Quick、Qt WebEngineの導入。

上記standalone項目はmilestone 7の後続unitへ送り、本unitの未完了理由にはしない。ただし、実行していないstandalone commandを実行済みまたは成功として記録しない。

## 4. 関連 docs

- `spec/ui-redesign/README.md`
- `spec/ui-redesign/MILESTONES.md`
- `spec/ui-redesign/PYSIDE6_UI_DESIGN.md`
- `spec/ui-redesign/RELATIVE_MOUSE_INPUT.md`
- `spec/initial/PROJECT_GUIDE.md`
- `spec/initial/QUALITY_GATES.md`
- `spec/initial/requirements.md`
- `spec/initial/architecture.md`
- `spec/initial/input.md`
- `spec/initial/lifecycle.md`
- `spec/initial/testing.md`
- `spec/initial/risks.md`
- `spec/complete/unit_009/OS_PORTABILITY.md`
- `spec/complete/unit_010/PACKAGING.md`
- `spec/complete/unit_013/`〜`spec/complete/unit_015/`、`spec/wip/unit_016/`〜`spec/wip/unit_017/`
- `README.md`
- `packaging/LICENSES.md`
- `AGENTS.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| standard gateを通す | clean dependency / current source | lock、format、lint、type、unit、integration、build、whitespaceがgreen | commandと件数を記録する |
| 3 OS source CIを通す | Windows / macOS / Linux runner | 同じsource gateとoffscreen Qt testがgreen | OS別jobを列挙する |
| display-free契約を守る | import / version | Qt application / displayを生成せずstatus 0 | wheel環境でも確認する |
| source GUIを起動する | 引数なしCLI、実display | main window表示、操作、正常close | Windowsは完了条件 |
| DPI / fontを受け入れる | 100%以外のscale、OS標準font | text切れ、control欠落、固定座標依存がない | scaleとscreen情報を記録する |
| focus / keyboardを受け入れる | Tab、Enter、Space、Esc、Alt+Tab、dialog | 標準focus、dialog優先、focus loss neutralが働く | F12解除を維持する |
| pointer capabilityを受け入れる | OS backend / capture | Raw / OS補正あり / 利用不可が実挙動と一致する | 未確認値をrawとしない |
| diagnosticsを出す | support snapshot | PySide6 / Qt版とpointer capabilityを含み、pyglet /秘密値を含まない | log rotationを維持する |
| current残存を検索する | current source / test / metadata / docs | pyglet dependency、import、収集、採用指示が0件 | 履歴文書は別分類 |
| wheel GUIを起動する | clean environment、built wheel | dependency install、GUI起動、timerによる自動close、status 0 | standaloneとは別証拠 |
| standaloneを分離する | milestone 6 acceptance | package workflowを再開せずmilestone 7へ記録する | source completionを止めない |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-skipped | standard gateと対象integration testがすべて成功し、実行commandと件数がwork unitへ記録される | characterization | package | `uv sync --dev`、lock、format、lint、ty、unit 187件、integration 54件、build、diffを現行main由来の基準として記録した。production変更はなく、追加refactorは不要 |
| refactor-skipped | `ty`はPySide6境界をerror / warningなしで通し、application / domainにQt型、広域`Any`、理由のないignoreがない | regression | package | source回帰テストで`application`と`domain`の`PySide6`、`Any`、`# type: ignore`を禁止し、`ty`もgreenである。production境界は既に分離済みのため、追加refactorは不要 |
| refactor-skipped | Windows、macOS、Linux CIでdependency install、display-free import / version、offscreen Qt、unit / integration、buildが成功する | regression | package | workflow contractで3 OS、Python 3.12 / 3.13、offscreen Qt、unit / integration / buildを固定し、PR #22の6 job成功をsource-level証拠として記録した。追加refactorは不要 |
| refactor-skipped | source checkoutの`demi`、`project-demi`、`python -m demi`は同じQt runnerを起動し、test用timerで正常closeできる | regression | integration | `DEMI_QT_TEST_CLOSE_AFTER_MS`が有効な整数の場合だけrunnerが通常の`window.close()`を予約する。3 entry pointをoffscreen subprocessで起動してstatus 0を確認し、通常CLI引数は追加しなかったため、追加refactorは不要 |
| refactor-skipped | clean環境へwheelをinstallするとPySide6 dependencyが解決され、GUI起動 / closeとversion表示が成功する | regression | package | temporary venvへlocal wheelだけをinstallし、親sourceの`PYTHONPATH`を除外してPySide6 import、`python -m demi --version`、offscreen Qt起動 / closeを確認した。standalone artifactは対象外のため、追加refactorは不要 |
| todo | Windows実displayでwindow、DPI、font、focus、Tab / Enter / Space / Esc、dialog、capture、F12、画面端、closeを確認する | new | manual | OS / scale / mouse / screenを記録する |
| refactor-skipped | macOS実displayでwindow、DPI、font、focus、pointer capability、closeを確認するか、未実行理由と制約を記録する | new | manual | 現在の作業環境にmacOS host / desktop sessionがないため未実行。OS版、display scale、font、native focus、pointer capability、closeの実画面証拠は取得していない。macOS CIのoffscreen成功を実display acceptanceと扱わず、macOS desktop環境での後続受入が必要 |
| refactor-skipped | Linux実displayでX11 / Waylandを明記し、window、DPI、font、focus、pointer capability、closeを確認するか、未実行理由を記録する | new | manual | 現在の作業環境にLinux host / desktop sessionがないため未実行。X11 / Wayland、compositor、OS版、display scale、font、native focus、pointer capability、closeを取得していない。Linux CIのoffscreen成功を実display acceptanceと扱わず、対象desktopでの後続受入が必要 |
| refactor-skipped | 8ms入力評価の平均 / 95 / 99、preview最大60Hz、100ms GUI応答性、250ms watchdog誤発火を診断値で確認する | characterization | integration | `InputPublisher.timing_metrics`が最大512件の正の評価間隔から平均、nearest-rank p95 / p99を出す。fake clockの8 / 8 / 16 / 8 / 8msで平均9.6ms、p95 / p99 16msを確認し、preview 60Hz、slow runtime中の100ms未満probe、250ms未満watchdog非発火を既存統合 / unit testで再確認した。これはdesktop OSの実時間保証ではないため、追加refactorは不要 |
| refactor-skipped | diagnosticsはOS、Python、Demi、swbt、PySide6、Qt、pointer capabilityを含み、pyglet版、bond内容、秘密値を含まない | regression | unit | UI境界の`SupportDiagnostics`が許可リストだけをsingle-line logへ整形し、起動 smokeでsupport snapshotと終了時入力統計を確認した。diagnostics収集失敗時も例外型だけを記録して起動を継続するため、追加refactorは不要 |
| refactor-skipped | READMEとcurrent `spec/initial`がPySide6実装、source起動、支援範囲、standalone停止状態と一致する | regression | docs | 文書回帰テストで3 entry point、PySide6 / Qt Widgets、旧未実装説明の撤去、source / wheel、単体配布停止を確認した。README、FR-001、roadmap、hardware test logを現行実装へ合わせ、追加refactorは不要 |
| refactor-skipped | source / wheel利用者がProject、PySide6、Qt、third-party license / noticeへ到達でき、欠落を検査できる | new | package | `THIRD_PARTY_NOTICES.md`をmodule rootへ置き、source inventoryとREADMEから導線を設けた。新規wheel生成testでProject licenseとnotice fileのarchive同梱を確認した。法的判断は完了と記録せず、追加refactorは不要 |
| refactor-skipped | current source、test、dependency、lock、builder、README、initial specにpygletのimport /収集 /採用指示が0件である | regression | package | AST回帰testで`src` / `tests`のlegacy import・型参照を禁止し、metadata、lock、builder、license inventory、README、initial specも検査する。語が残るのは削除済み境界を検出する否定testだけであり、scoped searchでimport /収集 /採用指示0件を確認した。追加refactorは不要 |
| todo | unit_013〜018のTDD、verification、checklist、deferred handoffに重複・抜け・誤った完了表現がない | new | docs | milestone 1〜6を1対1で確認する |
| deferred | standalone artifactがQt pluginとlicenseを含み、3 OS clean環境でGUI起動する | regression | package | milestone 7の後続unit |

## 7. 設計メモ

### 7.1 証拠の区分

| 証拠 | 確認できる範囲 | 確認できない範囲 |
|---|---|---|
| offscreen unit / integration | widget state、signal、model、action、lifecycle | 実font、DPI、native focus、pointer capture |
| 3 OS source CI | wheel解決、import、offscreen、source package | desktop hardware、Bluetooth、standalone |
| 実display manual | 対象OS / display / input deviceの表示と操作 | 未試験OS / deviceへの一般化 |
| wheel clean install | Python配布dependencyとQt runner | PyInstaller plugin / executable |
| standalone milestone 7 | artifact固有resource、license、起動 | source CIの代替ではない |

### 7.2 current pyglet残存判定

- 0件を要求する対象は`src`、現行`tests`、`pyproject.toml`、`uv.lock`、`packaging`、README、`spec/initial`である。
- `spec/complete`は過去の実装記録、`spec/ui-redesign`は移行理由と撤去条件を記録するため、語の存在自体を失敗にしない。
- 履歴文書を除外した検索commandと、除外理由を検証欄へ残す。除外を使ってcurrent source / docsの残存を隠さない。

### 7.3 license

- PySide6 / Qtの採用module、配布形態、取得したlicense / notice fileを列挙する。
- source / wheelで利用者がnoticeへ到達できる導線を確認する。standalone artifactへの同梱はmilestone 7で別に確認する。
- LGPLv3の具体的遵守方法は技術記録と法的判断を分ける。未確認の法的結論を書かない。

### 7.4 unit間の引き渡し

- unit_017から受け取る条件: production composition、queued event、startup、100ms応答性、shutdown、後着event無効化がgreenである。
- milestone 7へ渡す条件: source / wheel UIがaccepted、pyglet release停止が維持、PySide6 module / license / OS別未検証事項が具体的に記録されている。
- milestone 7はPyInstaller / standaloneだけを所有し、milestone 1〜6のsource UI behaviorを再実装しない。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `.github/workflows/ci.yml` | modify | 3 OS PySide6 source / offscreen / package gate |
| `tests/unit/test_ci.py` | modify | source CI matrixとQt gateのcontract |
| `tests/unit/test_packaging.py` | modify | dependency / wheel contents / import contract |
| `tests/unit/test_legacy_ui_removal.py` | verify | source / testのlegacy import・型境界をASTで禁止 |
| `tests/integration/lifecycle/` | modify / new | source / wheel GUI startup / close smoke |
| `src/demi/ui/diagnostics.py` | new | PySide6 / Qt / pointer capabilityの安全なsupport snapshot |
| `src/demi/input/timing.py` | new | 入力評価間隔の平均、p95、p99を出すbounded metrics |
| `src/demi/THIRD_PARTY_NOTICES.md` | new | wheelに同梱するProject、PySide6、Qtのnotice導線 |
| `src/demi/app.py` | verify / modify | safe diagnosticsとsource runner契約 |
| `README.md` | modify | source起動、支援範囲、standalone停止、license導線 |
| `tests/unit/test_documentation.py` | new | READMEと初期仕様の現在向け実行・配布説明を回帰検査 |
| `spec/hardware-test-log.md` | modify | 実機記録で収集するGUI runtime版をPySide6 / Qtへ更新 |
| `spec/initial/README.md` | modify | 採用UIと実行model |
| `spec/initial/requirements.md` | modify | PySide6 / Qt、診断、応答性のcurrent契約 |
| `spec/initial/architecture.md` | modify | Qt UI、input backend、queued signal、ownership |
| `spec/initial/ui.md` | modify | Qt Widgets、preview、standard controls |
| `spec/initial/input.md` | modify | Qt event、pointer capability、Raw Input |
| `spec/initial/lifecycle.md` | modify | Qt startup / shutdown / timer / signal |
| `spec/initial/testing.md` | modify | offscreen、3 OS、manual acceptance |
| `spec/initial/risks.md` | modify | PySide6 / Qt / pointer / license / packaging risk |
| `packaging/LICENSES.md` | modify | source / wheel noticeとmilestone 7境界 |
| `tests/integration/package/test_wheel_license_notices.py` | new | source / wheel noticeとProject licenseのarchive同梱を検査 |
| `spec/complete/unit_013/`〜`spec/complete/unit_015/`、`spec/wip/unit_016/`〜`spec/wip/unit_018/` | modify | 最終TDD、検証、checklist、handoff結果 |

`spec/complete`の過去記録は変更しない。`pyproject.toml`または`uv.lock`へ実装結果の修正が必要になった場合は対象へ追加し、`uv lock --check`と`uv build`を再実行する。

## 9. 検証

| command | result | notes |
|---|---|---|
| `rg -n "T[O]DO|T[B]D|x[x]x|前[回]|今[回]|一[旦]|上[述]|適[宜]|必要に応じ[て]" spec/wip/unit_018` | passed | 該当なし |
| `git diff --no-index --check -- NUL spec/wip/unit_018/QT_QUALITY_AND_OS_ACCEPTANCE.md` | passed | whitespace errorなし。LF / CRLF変換予告のみ |
| `uv sync --dev` | passed | Resolved 77 packages、Checked 74 packages |
| `uv lock --check` | passed | Resolved 77 packages |
| `uv run ruff format --check .` | passed | 118 files already formatted |
| `uv run ruff check .` | passed | All checks passed |
| `uv run ty check --no-progress` | passed | All checks passed |
| `uv run pytest tests/unit/application/test_ui_state.py -q -p no:cacheprovider` | passed | 2 passed。application / domainのQt型、広域`Any`、理由のないignore残存を検出する |
| `uv run ruff format --check tests/unit/application/test_ui_state.py` | passed | 1 file already formatted |
| `uv run ruff check tests/unit/application/test_ui_state.py` | passed | All checks passed |
| `uv run pytest tests/unit/test_ci.py -q -p no:cacheprovider` | passed | 3 passed。3 OS、Python 3.12 / 3.13、offscreen Qt、integration / build gateをworkflow契約として確認した |
| `uv run ruff format --check tests/unit/test_ci.py` | passed | 1 file already formatted |
| `uv run ruff check tests/unit/test_ci.py` | passed | All checks passed |
| GitHub Actions PR #22 `CI` | passed | `29370086048` のubuntu / macOS / Windows、Python 3.12 / 3.13の6 jobがすべてSUCCESS。dependency install、offscreen Qt、unit / integration、buildを確認した |
| `uv run pytest tests/integration/ui/test_source_entry_points.py -q -p no:cacheprovider` | passed | 3 passed。`demi`、`project-demi`、`python -m demi`がoffscreen Qt runnerを起動し、test用timerから通常closeしてstatus 0を返す |
| `uv run pytest tests/integration/ui/test_source_entry_points.py tests/integration/ui/test_application_lifecycle.py tests/unit/ui/test_application.py -q -p no:cacheprovider` | passed | 23 passed。source smokeと既存runner lifecycleを同時に確認した |
| `uv run ruff format --check src/demi/ui/application.py tests/integration/ui/test_source_entry_points.py` | passed | 2 files already formatted |
| `uv run ruff check src/demi/ui/application.py tests/integration/ui/test_source_entry_points.py` | passed | All checks passed |
| `uv run pytest tests/integration/package/test_wheel_gui_smoke.py -q -p no:cacheprovider` | passed | 1 passed。temporary venvでwheelをinstallし、PySide6 dependency、配布version、offscreen Qt runnerの起動 / closeを確認した |
| `uv run ruff format --check tests/integration/package/test_wheel_gui_smoke.py` | passed | 1 file already formatted |
| `uv run ruff check tests/integration/package/test_wheel_gui_smoke.py` | passed | All checks passed |
| `uv run pytest tests/unit/input/test_timing.py tests/unit/input/test_publisher.py tests/unit/ui/test_controller_preview.py tests/unit/controller/test_watchdog.py tests/integration/ui/test_application_lifecycle.py::test_qt_event_loop_stays_responsive_during_slow_runtime_operations -q -p no:cacheprovider` | passed | 13 passed。入力評価平均9.6ms、p95 / p99 16msのdeterministic sample、preview 60Hz制限、100ms未満GUI probe、250ms未満watchdog非発火を確認した |
| `uv run ruff format --check src/demi/input/timing.py src/demi/input/publisher.py tests/unit/input/test_timing.py tests/unit/input/test_publisher.py` | passed | 4 files already formatted |
| `uv run ruff check src/demi/input/timing.py src/demi/input/publisher.py tests/unit/input/test_timing.py tests/unit/input/test_publisher.py` | passed | All checks passed |
| `uv run pytest tests/unit/config/test_paths.py tests/unit/ui/test_diagnostics.py tests/unit/application/test_app.py tests/unit/application/test_logging.py tests/integration/ui/test_source_entry_points.py tests/integration/package/test_wheel_gui_smoke.py tests/integration/ui/test_application_lifecycle.py -q -p no:cacheprovider` | passed | 38 passed。safe support snapshot、起動／終了ログ、test root、source / wheel GUI smoke、既存lifecycleを確認した |
| `uv run ruff format --check src/demi/config/paths.py src/demi/app.py src/demi/ui/diagnostics.py tests/unit/config/test_paths.py tests/unit/ui/test_diagnostics.py tests/integration/ui/test_source_entry_points.py tests/integration/package/test_wheel_gui_smoke.py` | passed | 7 files already formatted |
| `uv run ruff check src/demi/config/paths.py src/demi/app.py src/demi/ui/diagnostics.py tests/unit/config/test_paths.py tests/unit/ui/test_diagnostics.py tests/integration/ui/test_source_entry_points.py tests/integration/package/test_wheel_gui_smoke.py` | passed | All checks passed |
| `uv run pytest tests/unit/test_documentation.py -q -p no:cacheprovider` | passed | 1 passed。READMEとinitial specのQt実装、3 entry point、source / wheel、単体配布停止の説明を確認した |
| `uv run ruff format --check tests/unit/test_documentation.py` | passed | 1 file already formatted |
| `uv run ruff check tests/unit/test_documentation.py` | passed | All checks passed |
| `uv run pytest tests/integration/package/test_wheel_license_notices.py -q -p no:cacheprovider` | passed | 1 passed。new wheelに`demi/THIRD_PARTY_NOTICES.md`とProject MIT licenseが同梱され、source inventoryとともにProject、PySide6、Qt、third-party noticeを案内することを確認した |
| `uv run ruff format --check tests/integration/package/test_wheel_license_notices.py` | passed | 1 file already formatted |
| `uv run ruff check tests/integration/package/test_wheel_license_notices.py` | passed | All checks passed |
| `uv run pytest tests/unit/test_legacy_ui_removal.py tests/unit/test_packaging.py tests/unit/test_cli.py tests/unit/application/test_application_session.py -q -p no:cacheprovider` | passed | 18 passed。source / test AST、package metadata / lock / builder、README / initial specのlegacy GUI採用残存を確認した |
| `uv run ruff format --check tests/unit/test_packaging.py tests/unit/application/test_application_session.py` | passed | 2 files already formatted |
| `uv run ruff check tests/unit/test_packaging.py tests/unit/application/test_application_session.py` | passed | All checks passed |
| `rg -n -i "import[[:space:]]+pyglet|from[[:space:]]+pyglet|collect-all[[:space:]]+pyglet|pyglet[[:space:]]*[<=>]|pyglet[[:space:]]+input|pyglet.*(backend|window)" src tests pyproject.toml uv.lock packaging README.md spec/initial --glob "!tests/unit/test_legacy_ui_removal.py"` | passed | import /収集 /採用指示の該当なし。除外したfileは削除済み境界を検出する否定test |
| macOS実display acceptance | not run | 現在の作業環境にmacOS host / desktop sessionがない。offscreen CIはsource-level証拠であり、実displayのwindow、DPI、font、focus、pointer capability、closeを確認していない |
| Linux実display acceptance | not run | 現在の作業環境にLinux host / desktop sessionがない。X11 / Wayland、compositorを含む実displayのwindow、DPI、font、focus、pointer capability、closeを確認していない |
| `uv run pytest tests/unit` | passed | 187 passed |
| `uv run pytest tests/integration` | passed | 54 passed |
| `uv build` | passed | `demi_controller-0.1.0.tar.gz` と `demi_controller-0.1.0-py3-none-any.whl` を生成 |
| `git diff --check` | passed | whitespace errorなし |
| 3 OS source CI | not run | PySide6 UI実装とworkflow更新前 |
| Windows実display acceptance | not run | PySide6 UI実装後に対象Windows desktopで実行する |
| macOS / Linux実display acceptance | not run | 対象desktop環境が必要。未実行時は理由と後続先を記録する |
| `uv run python packaging/build.py` / standalone smoke | not run | 本unitの対象外。milestone 7で実行する |

## 10. 先送り事項

| 観測 | 先送り理由 | 後続の置き場 |
|---|---|---|
| PySide6 standaloneのQt plugin / DLL / framework収集は未検証 | source / wheelとartifact固有resourceを分離する | milestone 7 standalone packaging unit |
| one-file / one-folder、起動時間、artifact size、署名、macOS app bundleは未決定 | OS別artifact比較とrelease設計が必要 | milestone 7 standalone packaging unit |
| 3 OS clean environment standalone GUI smokeは未実行 | package workflow再設計後に実行する | milestone 7 standalone packaging unit |
| macOS / Linux実displayが未実行の場合の支援範囲 | 対象desktopを利用できない限り確認済みにできない | 本unit検証欄の未実行理由と後続OS acceptance記録 |

## 11. チェックリスト

- [ ] milestone 0とunit_013〜017の完了を確認した
- [ ] 標準gateと対象integration testをすべて実行した
- [ ] `ty`でPySide6 / application / domainの型境界を確認した
- [ ] Windows、macOS、Linux source CIを確認した
- [ ] Windows実display / DPI / font / focus / pointer captureを確認した
- [ ] macOS / Linuxの実行結果または未実行理由を記録した
- [ ] README、initial spec、diagnostics、license noticeを実装結果へ同期した
- [ ] current pyglet残存検索を実行した
- [ ] source checkoutとwheelのGUI起動契約を確認した
- [ ] PyInstaller / standaloneを対象外としてmilestone 7へ送った
- [ ] unit_013〜018のTDD、検証、checklist、handoffを横断確認した
- [ ] TDD Test Listと検証結果を更新した
