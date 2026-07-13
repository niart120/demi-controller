# UI 再設計 実装マイルストーン

## 1. 進行方針

旧 UI を最初に削除し、その後 PySide6 UI を積み直す。移行中の作業 branch では GUI が
一時的に利用不能になることを許容するが、その状態を release しない。default branch へ
取り込む単位は、少なくとも source 起動の主要機能と標準 gate が green に戻った時点とする。

各マイルストーンの着手時に `spec/wip/unit_XXX/FEATURE_NAME.md` を作成する。複数の
マイルストーンを1つの work unit にまとめる場合も、TDD Test List と検証結果をマイルストーン別に
記録する。

## 2. milestone 0: 設計正本の更新

### 目的

pyglet を採用していた `spec/initial` と PySide6 採用判断の矛盾を解消する。

### 作業

- `requirements.md` の pyglet 固有要件と Qt 不採用条件を廃止する。
- `architecture.md` の UI、input backend、thread、event loop を PySide6 前提へ更新する。
- `ui.md` を Qt Widgets の標準部品と `ControllerPreviewWidget` 前提へ更新する。
- `input.md`、`lifecycle.md`、`testing.md`、`risks.md` の pyglet 固有記述を更新する。
- 診断 snapshot の GUI library version を PySide6 と Qt version へ変更する。
- 最初の実装 work unit を `spec/wip` に作成する。

### 完了条件

- 現行仕様の採用 UI が一意に PySide6 / Qt Widgets となる。
- 完了済み work unit の履歴を改変していない。
- 撤去と置換の対象外が作業仕様に記録されている。

### milestone 0 の更新記録

- 現行仕様の UI、入力、ライフサイクル、試験、リスク、診断項目を PySide6 / Qt Widgets 前提へ更新した。
- 完了済みの `spec/complete/unit_001`〜`unit_012` は変更していない。
- 旧 UI 撤去の対象範囲と維持する境界は `CURRENT_UI_REMOVAL.md` に記録済みである。
- 最初の実装 work unit として `spec/wip/unit_013/LEGACY_UI_AND_PYGLET_REMOVAL.md` を作成済みである。
- milestone 0 は設計文書だけを対象とし、Python実装・依存関係・lockは変更しない。

## 3. milestone 1: 旧 UI と pyglet の一括撤去

### 目的

新 UI が旧設計へ依存する余地をなくす。

### 作業

- `src/demi/ui` の現行実装をすべて削除する。
- `src/demi/input/pyglet_backend.py` を削除する。
- pyglet 固有 test を削除する。
- `app.py` から旧 UI の import、factory、具象 type hint を削除する。
- `pyproject.toml` と `uv.lock` から pyglet を削除する。
- package builder、license inventory、pytest marker から pyglet を削除する。
- CLI version、package import、非 UI test を復旧する。

### 許容する中間状態

- 引数なし GUI 起動は未実装として非ゼロ終了してよい。
- full unit / integration gate は GUI 契約の再実装まで green でなくてよい。
- `uv lock --check`、package import、CLI version、domain/config/controller の対象 test は green にする。

### 完了条件

- `CURRENT_UI_REMOVAL.md` の撤去完了条件を満たす。
- pyglet 不在を原因とする traceback を CLI へ露出しない。
- standalone package workflow から release artifact を発行しない状態になっている。

## 4. milestone 2: PySide6 最小 application shell

### 目的

PySide6 dependency、event loop、main window、正常終了を最小構成で成立させる。

### 作業

- PySide6 6.x の版範囲を決め、`uv.lock` を更新する。
- `QApplication` と `QMainWindow` を生成する runner を実装する。
- window size、minimum size、maximized state の読込と保存を接続する。
- close event を `ApplicationShutdownCoordinator` へ接続する。
- `--version` と module import で Qt display を初期化しない。
- offscreen Qt test fixture を用意する。

### 完了条件

- 引数なし CLI で empty main window が起動する。
- close request が runtime と settings を一度だけ閉じる。
- display を開かない CLI / import test が通る。
- Windows、macOS、Linux CI で dependency install と機材不要 test が通る。

## 5. milestone 3: 入力捕捉と controller preview

### 目的

キー・マウス入力から `ControllerFrame` の生成、runtime 送信、画面表示までを復旧する。

### 作業

- Qt input adapter を実装する。
- pointer capture port を framework 非依存の名前へ変更する。
- Windows は `QAbstractNativeEventFilter` と Win32 Raw Input で未加速の相対移動量を取得する。
- GLFW を dependency として追加しない。
- backend capability で未加速値、補正後の相対値、利用不能を区別する。
- F12、focus loss、dialog open、shutdown の neutralization を接続する。
- 8ミリ秒 input evaluation timer を接続する。
- `ControllerPreviewWidget` を `QPainter` で実装する。
- 最大60 Hzの再描画要求を接続する。
- 実 display で pointer capture と画面端の挙動を確認する。

### 完了条件

- 同じ `ControllerFrame` が runtime と preview に渡る。
- capture 外と focus loss 後に neutral frame になる。
- dialogへ入力中の key を controller mapping へ流さない基盤がある。
- Windows で F12 による解除と継続的な相対マウス入力を手動確認する。
- Windows で Raw Input の登録、1000 Hz mouse、通常のQt操作との共存を確認する。
- macOS / Linux の未実行事項を支援済みと記録しない。

## 6. milestone 4: 標準 toolbar、status bar、settings dialog

### 目的

独自 control を作らず、主要な GUI 操作を Qt Widgets で復旧する。

### 作業

- `QToolBar` と `QAction` で接続、切断、capture、設定操作を実装する。
- `QStatusBar` で adapter、connection、capture、warning/error を表示する。
- mapping dialog を model/view control で実装する。
- connection dialog と pairing confirmation を実装する。
- controller colors dialog と live preview を実装する。
- 保存失敗、取消、重複、busy、adapter 0件の状態を実装する。

### 完了条件

- 現行 requirements の FR-002～FR-004、FR-008、FR-010～FR-014 を GUI から実行できる。
- toolbar と dialog に独自座標 hit test がない。
- Tab、Enter、Space、Esc と enabled state が Qt の標準挙動に従う。
- settings save 失敗時に draft と dialog が保持される。
- 色変更の取消と再接続選択が既存 domain 契約を守る。

## 7. milestone 5: runtime event と lifecycle の統合

### 目的

worker、application state、Qt GUI、終了処理を production composition root で接続する。

### 作業

- Qt queued signal を使う runtime event bridge を実装する。
- adapter discovery、connection、pairing、watchdog、error を main window へ反映する。
- startup reconnect と adapter 不在を復旧する。
- startup failure と未処理例外の安全な終了を復旧する。
- timer、signal connection、dialog、window、runtime の所有権を整理する。
- application 層から Qt widget 型への依存がないことを確認する。

### 完了条件

- worker event は GUI 主スレッドでだけ widget を更新する。
- 接続処理中も GUI event loop を100ミリ秒以上連続して塞がない。
- watchdog/error 後に capture を解除し、安全な表示へ戻る。
- startupとshutdownの既存 integration scenarioがPySide6構成で通る。
- runtime停止後にQt timerとsignal receiverが動作しない。

## 8. milestone 6: 品質 gate と OS 受入

### 目的

PySide6 UI を通常の source 配布として完了可能な状態にする。

### 作業

- 関連する unit、integration、UI test を全て green にする。
- `ty` で PySide6 境界を確認し、広域な `Any` や ignore を残さない。
- Windows、macOS、Linux の source-level CI を通す。
- OS別に実 display、DPI、font、focus、pointer capture を確認する。
- README、初期設計、診断項目、license notice を実装結果へ合わせる。
- pyglet の current dependency / source / test / current docs 残存を検索する。

### 完了条件

- 標準 gate と対象 integration test が通る。
- Windows の source GUI smoke が通る。
- macOS / Linux の実 display が未実行なら、制約と後続確認先が記録されている。
- PyInstaller を除く source 実行と wheel の GUI 起動契約が確認されている。
- UI 再設計 work unit の checklist と検証結果が完了している。

## 9. milestone 7: standalone packaging

このマイルストーンは UI 再設計の完了後に扱い、先行マイルストーンを止めない。

### 対象

- PyInstaller の PySide6 hook と Qt plugin 収集
- license inventory
- one-file / one-folder の選択
- 3 OS の clean environment GUI smoke
- 起動時間、artifact size、署名、macOS app bundle
- package workflow と tag release gate

## 10. TDD Test List

実装開始時に各項目を対応する `spec/wip` へ移し、1項目ずつ red / green / refactor を記録する。

| status | item | type | layer | notes |
|---|---|---|---|---|
| todo | pyglet を環境へ導入しなくても package import と3つの version entry point が成功する | regression | package | milestone 1 |
| todo | pyglet の production import、runtime dependency、package収集指定が0件になる | new | package | 過去の完了記録は検索対象外 |
| todo | 引数なしCLIは1つのQt application runnerを呼び、その終了statusを返す | regression | unit | milestone 2 |
| todo | module importと`--version`は`QApplication`を生成しない | regression | package | milestone 2 |
| todo | 設定済みwindow寸法・最小寸法・最大化状態でmain windowを開始する | regression | unit | milestone 2 |
| todo | window closeはneutral、runtime停止、settings保存、window終了を一度だけ実行する | regression | integration | milestone 2 / 5 |
| todo | Qt keyとmouse press/releaseは正規化された保持状態を冪等に更新する | regression | unit | milestone 3 |
| todo | F12、focus loss、dialog openはcaptureを解除しneutral frameを発行する | regression | integration | milestone 3 |
| todo | 8ミリ秒評価で生成した同じframeをruntimeとpreviewが観測する | regression | integration | milestone 3 |
| todo | controller previewはbutton、stick、gyro、accel、captureを1つのframeから表示する | regression | unit | pixel完全一致を要求しない |
| todo | toolbar actionのlabelとenabled状態がapplication stateに追従する | regression | unit | milestone 4 |
| todo | mapping dialogの文字・key取得はcontroller入力へ流れず、保存と取消を区別する | regression | integration | milestone 4 |
| todo | adapter 0件のconnection dialogは接続とpairingを無効にし、再検索できる | regression | integration | milestone 4 |
| todo | color dialogの取消は保存値を変えず、保存はpreviewと再接続選択へ反映する | regression | integration | milestone 4 |
| todo | worker eventはqueued delivery後だけGUI thread上のpresentationを更新する | regression | integration | milestone 5 |
| todo | startup reconnectは検出済みの保存adapterだけを選び、新規pairingを開始しない | regression | integration | milestone 5 |
| todo | startup failureは開始済み資源を閉じ、安全なstderrと非ゼロstatusを返す | regression | integration | milestone 5 |
| todo | Windows、macOS、Linuxのoffscreen testが機材なしで成功する | new | package | milestone 6 |
| deferred | standalone artifactがQt pluginとlicenseを含み、clean環境でGUI起動する | regression | package | milestone 7 |

## 11. 検証 command

### 設計文書だけの段階

| command | result | notes |
|---|---|---|
| `rg -n "pyglet|Pyglet|ControllerView" spec\initial` | passed | `roadmap.md` の完了済みunit履歴だけに残り、現行採用指示ではないことを注記済み |
| `rg -n "T[O]DO|T[B]D|x[x]x|今[回]|一[旦]|上[述]|適[宜]|必要に応じ[て]" spec\initial spec\ui-redesign` | passed | 該当なし |
| `git diff --name-only -- spec\complete` | passed | 完了済みwork unitの差分なし |
| `git diff --check` | passed | whitespace errorなし。LF / CRLF変換予告のみ |
| Python標準 gate | not run | 設計文書だけを変更し、production code、dependency、lockを変更していない |

### 実装完了時の標準 gate

```powershell
uv sync --dev
uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
uv run pytest tests/unit
uv run pytest tests/integration
uv build
git diff --check
```

PyInstaller の `packaging/build.py` と `packaging/smoke.py` は milestone 7 まで `not run` を
許容する。実行していない場合は `not applicable` と書かず、UI 機能移行を優先したため
`not run` と記録する。

## 12. 先送り事項

| 観測 | 先送り理由 | 後続の置き場 |
|---|---|---|
| Qtの通常mouse eventがraw input要件を満たすか未検証 | OS実機とpointer capture実装が必要 | milestone 3 のOS受入 |
| PySide6 standaloneのplugin・license収集が未検証 | PyInstaller対応を劣後させる | milestone 7 |
| macOS / Linuxの実display挙動が未検証 | 対象OSのdesktop環境が必要 | milestone 6 のOS受入 |
| LGPLv3の配布方法が未確定 | 最終artifact形式が未確定 | milestone 7 のlicense review |
