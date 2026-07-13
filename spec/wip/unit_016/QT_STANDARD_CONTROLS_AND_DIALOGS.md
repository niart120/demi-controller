# Qt 標準 control と dialog 仕様書

## 1. 概要

### 1.1 目的

UI 再設計 milestone 4 として、接続、切断、入力capture、設定をQt Widgetsの標準controlで操作できるようにする。`QToolBar`、`QAction`、`QStatusBar`、`QDialog`、`QDialogButtonBox`、model/view control、`QColorDialog`を使用し、旧UIの座標計算、独自hit test、独自text field、独自combo boxを再実装しない。

本unitはFR-002〜FR-004、FR-008、FR-010〜FR-014のGUI操作面を所有する。保存失敗、取消、重複binding、busy、adapter 0件を観測可能な状態として固定し、Tab、Shift+Tab、Enter、Space、Escとenabled stateをQt標準挙動へ委ねる。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| milestone | milestone 4のtoolbar、status bar、dialog、edge、完了条件 | `spec/ui-redesign/MILESTONES.md` |
| target UI | 標準control構成、dialog draft、model/view、keyboard操作 | `spec/ui-redesign/PYSIDE6_UI_DESIGN.md` |
| requirements | FR-002〜004、FR-008、FR-010〜014の受入条件 | `spec/initial/requirements.md` |
| settings / lifecycle | immutable draft、atomic save、capture neutralization、color reconnect | `spec/initial/configuration.md`, `spec/initial/lifecycle.md` |
| completed behavior | settings editor / modal controller、runtime command、presentationの現行契約 | `spec/complete/unit_007/SETTINGS_MODAL.md`, `spec/complete/unit_011/APPLICATION_ASSEMBLY_AND_GUI_WIRING.md` |
| prerequisite | Qt shell、input capture、controller preview | `spec/complete/unit_014/PYSIDE6_APPLICATION_SHELL.md`, `spec/wip/unit_015/QT_INPUT_AND_CONTROLLER_PREVIEW.md` |

milestone 0とunit_013〜015の完了を着手条件とする。本unitはstandard controlとapplication actionの接続をfake runtimeで完成させ、production worker event / startup / shutdown統合はunit_017へ渡す。

仕様執筆時点では上記の実装前提は未完了である。着手時に更新後の初期仕様と unit_013〜015 の完了記録を確認する。

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| user | toolbarから接続、切断、capture、設定を選ぶ | 現在stateでenabledなactionだけがapplication actionを1回発行する | 座標hit testを持たない |
| user | mapping dialogでbindingを編集 | 次のkey / mouseをdraftへ取得し、反転、重複、local action競合を表示する | F12は割当不可 |
| user | connection dialogでadapterを選択 / 再検索 | 非同期列挙結果をmodelへ反映し、0件時は接続 / pairingを無効化する | 別adapterを自動選択しない |
| user | colors dialogで4色を編集 | draft previewを即時更新し、取消は保存値へ戻し、保存は再接続選択を提示する | 不正色を保存しない |
| user | 保存中 / 接続中に操作 | busyな重複操作を無効にし、window event loopは動き続ける | runtime I/OをGUI threadで待たない |
| keyboard user | Tab、Shift+Tab、Enter、Space、Esc | Qt標準のfocus移動、action実行、dialog取消が働く | controller mappingへ同じeventを流さない |

## 2. 対象範囲

- `QToolBar`と`QAction`でconnection、disconnect、capture start / stop、mapping、connection settings、colorsを構成する。
- action label、check state、enabled stateをapplication / connection / capture / dialog / shutdown stateから更新する。
- `QStatusBar`と複数の`QLabel`でadapter、connection、capture、pointer capability、preview-only、warning / errorを文字表示する。
- mapping dialogを`QDialog`と`QTableView`または`QTreeView`で実装し、target、source、inverted、conflictをmodelとして表示する。
- binding取得は明示操作後の次のkeyまたはmouse buttonだけを候補にし、dialog中の通常入力をcontroller mappingへ流さない。
- duplicate sourceとlocal action conflictを表示し、保存前に確定または取消を選択できるようにする。同じtargetへの異なるsourceは既存domain契約どおり許可する。
- mapping標準復元、gyro enabled、水平 / 垂直感度、Y反転、pitch上限を既存`SettingsEditor`のdraftへ接続する。
- connection dialogを`QComboBox`またはmodel/view controlで構成し、adapter再検索、保存済み接続、接続設定、明示pairing確認を提供する。
- adapter 0件、保存adapter未検出、discovery / connect / disconnect / pairing中のenabled stateを明示する。
- controller colors dialogで4色の`#RRGGBB` field、swatch、`QColorDialog`、draft preview、保存 / 取消、再接続選択を実装する。
- `QDialogButtonBox.Save` / `Cancel`を使い、validation / persistence失敗時はdialogとdraftを保持して該当fieldと説明を表示する。
- dialog open前にcapture解除とneutral frame発行を要求し、dialog close後に自動captureしない。
- 同時に開けるdialogを1つに制限し、pairing confirmationとcolor reconnect promptを明示的なstateとして扱う。
- Qtのfocus chain、default button、shortcut context、enabled stateを利用し、独自の座標hit testや手作りtab orderを実装しない。

## 3. 対象外

- adapter I/OをGUI threadで実行する処理、worker eventのqueued delivery、startup reconnect、watchdog / errorのproduction wiring。unit_017が所有する。
- settings schema、atomic repository、binding conflictのdomain意味、controller commandの意味変更。
- custom-drawn button、独自combo box、独自text editor、座標付きtoolbar / dialog control。
- profile import / export、Joy-Con、複数controller type、bond削除UI。
- OS native file dialog、独自theme、QML、Qt Quick、Qt WebEngine。
- 実displayのfont、DPI、focus、native keyboard差の最終受入。unit_018が所有する。
- PyInstaller / standalone packaging。milestone 7の後続unitが所有する。

## 4. 関連 docs

- `spec/ui-redesign/PYSIDE6_UI_DESIGN.md`
- `spec/ui-redesign/MILESTONES.md`
- `spec/initial/requirements.md`
- `spec/initial/ui.md`
- `spec/initial/configuration.md`
- `spec/initial/input.md`
- `spec/initial/lifecycle.md`
- `spec/complete/unit_007/SETTINGS_MODAL.md`
- `spec/complete/unit_011/APPLICATION_ASSEMBLY_AND_GUI_WIRING.md`
- `spec/wip/unit_015/QT_INPUT_AND_CONTROLLER_PREVIEW.md`
- `AGENTS.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| toolbarを更新する | app / connection / capture / dialog state | label、check、enabledがstateへ追従する | 色だけに依存しない |
| connection actionを実行する | READY / CONNECTED / busy / adapter未設定 | connect / disconnect / dialog openを1回発行、busyは無効 | 重複commandを発行しない |
| statusを表示する | adapter、connection、capture、pointer quality、warning / error | 独立した文字領域へ表示する | tracebackを表示しない |
| mapping draftを編集する | row選択、次のkey / mouse、inverted | domain語彙のdraftを更新し、競合を表示する | Qt enum値を保存しない |
| mappingを保存する | valid draft、重複確認済み | atomic save成功後にdialogを閉じ、live inputへ反映する | 保存失敗時は閉じない |
| mappingを取り消す | 変更済みdraft、Cancel / Esc | 保存値を変更せずdraftを破棄する | captureを自動再開しない |
| adapterを再検索する | connection dialog open | GUIを塞がずdiscovery actionを発行し、modelを更新する | 0件時も再検索できる |
| adapter 0件を扱う | discovery完了、候補なし | connect / pairingを無効化し、必要機材を説明する | 先頭候補を仮定しない |
| pairingを開始する | adapter選択、明示確認 | confirmation後だけpairing actionを1回発行する | 起動 / 保存だけでは開始しない |
| colorsをpreviewする | valid draft color | previewをdraft色へ更新する | settings fileは未更新 |
| colorsを取り消す | draft変更済み | previewとfieldを保存色へ戻し、repositoryを変更しない | connectionも変更しない |
| colorsを保存する | valid draft、connected | 保存後に「後で」/「再接続」を提示する | 再接続時もcaptureを再開しない |
| keyboard操作する | Tab / Shift+Tab / Enter / Space / Esc | Qt標準focusとdialog resultが働く | controller mappingより優先する |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| todo | toolbar actionのlabel、check、enabled stateがapplication / connection / capture / dialog / shutdown stateに追従する | regression | unit | `QAction`公開stateを観測する |
| todo | READY / CONNECTEDのconnection actionはconnect / disconnectを1回発行し、busy中の重複操作は発行しない | regression | integration | fake application actionsで確認する |
| todo | status barはadapter、connection、capture、pointer quality、preview-only、warning / errorを文字で区別する | regression | unit | 色だけの表現を禁止する |
| todo | mapping modelはtarget、source、inverted、conflictを公開し、標準復元とdraft編集をapplication境界へ渡す | new | unit | model/viewのindexとdataを確認する |
| todo | mapping dialogの文字 / key / mouse取得はcontroller入力へ流れず、F12はcapture解除を優先する | regression | integration | FR-008 / FR-010 |
| todo | duplicate sourceとlocal action conflictを保存前に表示し、確定 / 取消を区別する | regression | integration | 同一targetへの異なるsourceは許可する |
| todo | mapping保存失敗はdialogとdraftを保持し、取消は保存値を変更せず閉じる | edge | integration | FR-013 |
| todo | connection dialogはadapter再検索を非同期actionとして発行し、結果modelを更新する間もGUI eventを処理できる | regression | integration | FR-002 |
| todo | adapter 0件ではconnect / pairingを無効にして説明を表示し、再検索だけを有効にする | regression | integration | FR-002 edge |
| todo | 保存adapter未検出時に別候補を自動選択せず、明示選択後だけ保存 / 接続できる | edge | integration | FR-002 / FR-003 |
| todo | pairingは確認dialogのaccept後だけ開始し、cancel / close / busyではcommandを発行しない | regression | integration | FR-003 |
| todo | disconnect actionはcapture neutralization後に発行され、処理中のframeと重複disconnectを抑止する | regression | integration | FR-004 |
| todo | color draftはpreviewを即時更新し、Cancelは保存色へ戻し、Saveは再接続選択へ進む | regression | integration | FR-012 |
| todo | 無効な色、timeout、bond slot、mapping値は保存されず、該当controlと説明がdialogに残る | edge | integration | FR-011〜013 |
| todo | inverted bindingは文字またはcheck stateで明示され、保存後のdomain値を維持する | regression | integration | FR-014 |
| todo | Tab / Shift+Tab、Enter、Space、EscがQt標準のfocus移動、action、取消として動作する | new | integration | 独自key routingで再実装しない |
| todo | toolbarとdialogのproduction sourceに独自座標hit testが存在しない | new | package | `QToolBar` / model/view / layoutを利用する |

## 7. 設計メモ

### 7.1 FRの所有範囲

| requirement | 本unitで固定するGUI観測面 |
|---|---|
| FR-002 | adapter model、再検索、0件、保存ID未検出、enabled state |
| FR-003 | saved connect、新規pairing確認、busy、失敗後の再操作 |
| FR-004 | toolbar disconnect、neutral先行、重複抑止、capture解除 |
| FR-008 | capture action、F12、focus / dialog時の解除、状態表示 |
| FR-010 | mapping model、入力取得、競合、標準復元、F12保護 |
| FR-011 | adapter、controller種別、bond slot、timeout、reconnect、diagnostic level |
| FR-012 | 4色、`#RRGGBB`、draft preview、再接続選択 |
| FR-013 | validation、atomic save成功、保存失敗時のdraft保持 |
| FR-014 | binding単位のinverted表示と保存、capture外neutral |

### 7.2 control境界

- widget値をsettingsへ直接永続化しない。Qt dialogは既存`SettingsEditor`と`SettingsModalController`へ意味のある値を渡す。
- adapter一覧とbinding一覧はmodelを正本とし、row widgetを手作業で並べて状態を複製しない。
- modal event loopの多重利用を避け、controller workerの生存期間をdialogに従属させない。
- warning / errorは短い分類済み文字列を表示し、詳細はlog / diagnostics導線へ分離する。

### 7.3 unit間の引き渡し

- unit_015から受け取る条件: capture / neutralizationとcontroller previewがQt shell上で成立している。
- unit_017へ渡す条件: 全actionがfake application / runtime portで観測でき、dialog edgeと標準keyboard操作がgreenである。
- unit_017はqueued runtime eventから同じpresentation stateを更新し、Qt widgetをworker threadから直接変更しない。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/ui/main_window.py` | modify | toolbar、status bar、dialog ownershipとrefresh |
| `src/demi/ui/toolbar.py` | new | `QToolBar` / `QAction`構成とstate同期 |
| `src/demi/ui/status_bar.py` | new | `QStatusBar` / `QLabel`による状態表示 |
| `src/demi/ui/dialogs/mapping.py` | new | mapping model/view、capture、conflict、save/cancel |
| `src/demi/ui/dialogs/connection.py` | new | adapter model、再検索、接続設定、pairing確認 |
| `src/demi/ui/dialogs/colors.py` | new | 4色editor、`QColorDialog`、preview、再接続選択 |
| `src/demi/application/dialogs.py` | verify / modify | dialog排他と意味のあるstate |
| `src/demi/application/settings_editor.py` | verify / modify | Qt非依存draft操作の不足分 |
| `src/demi/application/settings_modal.py` | verify / modify | save/cancel/failure/reconnect契約 |
| `src/demi/app.py` | modify | Qt control actionとapplication sessionのcomposition |
| `tests/unit/ui/test_toolbar.py` | new | action state |
| `tests/unit/ui/test_status_bar.py` | new | status表示 |
| `tests/unit/ui/dialogs/` | new | model/view、validation、keyboard |
| `tests/integration/ui/test_qt_dialogs.py` | new | action、neutral、save/cancel、edge |
| `spec/wip/unit_016/QT_STANDARD_CONTROLS_AND_DIALOGS.md` | modify | FR trace、TDD状態、検証、引き渡し記録 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `rg -n "T[O]DO|T[B]D|x[x]x|前[回]|今[回]|一[旦]|上[述]|適[宜]|必要に応じ[て]" spec/wip/unit_016` | passed | 該当なし |
| `git diff --no-index --check -- NUL spec/wip/unit_016/QT_STANDARD_CONTROLS_AND_DIALOGS.md` | passed | whitespace errorなし。LF / CRLF変換予告のみ |
| `uv run ruff format --check .` | not run | 仕様執筆だけでPython sourceを変更していない |
| `uv run ruff check .` | not run | 仕様執筆だけでPython sourceを変更していない |
| `uv run ty check --no-progress` | not run | Qt model / action / dialog境界は未実装 |
| `uv run pytest tests/unit` | not run | Qt standard controls未実装のため |
| `uv run pytest tests/integration` | not run | dialogとapplication action未実装のため |
| `uv build` | not run | 仕様執筆だけでsource packageを変更していない。実装完了時に実行する |

## 10. 先送り事項

| 観測 | 先送り理由 | 後続の置き場 |
|---|---|---|
| production adapter eventによるaction / status更新は未接続 | workerからGUI threadへのdeliveryを先に固定する必要がある | `spec/wip/unit_017/QT_RUNTIME_AND_LIFECYCLE_INTEGRATION.md` |
| 3 OS実displayのfocus chain、font、DPI差は未検証 | 対象desktopで手動確認が必要 | `spec/wip/unit_018/QT_QUALITY_AND_OS_ACCEPTANCE.md` |
| profile import / exportと複数controller type | 0.1.xのFR範囲外 | 後続roadmapで判断する |

## 11. チェックリスト

- [ ] unit_015のinput / preview前提を確認した
- [ ] QToolBar / QAction / QStatusBarを実装した
- [ ] mapping / connection / colorsを標準dialogとmodel/viewで実装した
- [ ] FR-002〜004、FR-008、FR-010〜014のGUI観測面を確認した
- [ ] 保存失敗、取消、重複、busy、adapter 0件を確認した
- [ ] Tab、Enter、Space、Escとenabled stateを確認した
- [ ] 独自座標hit testが存在しないことを確認した
- [ ] TDD Test Listと検証結果を更新した
- [ ] unit_017への引き渡し条件を満たした
