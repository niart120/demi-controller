# キー割り当てダイアログの可視列 仕様書

## 1. 概要

### 1.1 目的

`MappingDialog` を既定表示したとき、対象、入力、反転、競合の4列と反転値を切れずに読める状態へ戻す。2026-07-15のWindows実displayで取得したQt widgetの画像では、反転列の見出しと`いいえ`が横幅不足で途中までしか表示されなかった。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| goal | unit_016以降の実GUI起動、画面画像、自己評価で配置破綻を検知する | active thread goal |
| current observation | 960 x 640のmain windowから開いたmapping dialogで反転列が切れる | `tmp/ui-audit/mapping-dialog.png`（git管理外の監査画像） |
| UI contract | mapping dialogはtarget、source、反転、競合を標準model/viewで表示する | `spec/ui-redesign/PYSIDE6_UI_DESIGN.md` |
| quality acceptance | Windows実displayではtext切れとcontrol欠落を残さない | `spec/complete/unit_018/QT_QUALITY_AND_OS_ACCEPTANCE.md` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| desktop user | 既定profileのキー割り当てdialogを開く | 4列見出しと`はい` / `いいえ`を横スクロールなしで判読できる | 全28行を一画面へ詰め込まない |
| maintainer | Qt widget testを実行する | 既定表示の各可視列が見出しと最長既定値を収める | pixel完全一致を主判定にしない |

## 2. 対象範囲

- `MappingDialog` の既定サイズとtable headerの列幅方針を、可視文字列が切れないように調整する。
- Qt widget testで既定profileの見出しと最長既定値に必要な列幅を固定する。
- Windows display上でmain window、mapping dialog、connection dialog、colors dialogの画像を再取得し、mapping dialogの表示欠けが解消したことを確認する。

## 3. 対象外

- mappingの対象・入力・反転・競合というデータ契約の変更。
- profile chooser、gyro設定、Y軸反転の意味や保存範囲の追加。
- connection dialogとcolors dialogの設計変更。
- computer-use native pipeの復旧。2回の接続試行は`os error 2`で失敗しており、本unitではQtのwidget grabを監査画像として使う。

## 4. 関連 docs

- `spec/initial/ui.md`
- `spec/initial/testing.md`
- `spec/ui-redesign/PYSIDE6_UI_DESIGN.md`
- `spec/ui-redesign/MILESTONES.md`
- `spec/complete/unit_016/QT_STANDARD_CONTROLS_AND_DIALOGS.md`
- `spec/complete/unit_018/QT_QUALITY_AND_OS_ACCEPTANCE.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| visible mapping columns | 既定profileでdialogを表示する | 対象、入力、反転、競合の見出しと`いいえ`を途中で切らずに表示する | 既定dialog width内で横scrollを要求しない |
| standard Qt sizing | 画面幅とfontが変わる | QTableViewの標準header sizingとlayoutが列幅を配分する | 独自座標hit testを導入しない |
| visual acceptance | Windows displayでdialogを開く | 画像で4列の見出しと値を読め、buttonやstatusの欠落がない | native pipeが復旧したとは扱わない |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-skipped | 既定profileのmapping dialogは、4列見出しと既定の最長可視値を各列内へ収める | regression | integration | redでは既存の対象列が100pxで、最長値に228px必要なため失敗。greenでは最初の3列を標準headerのcontent-aware sizingにし、競合列を余り幅へ伸長した。追加の構造変更は不要 |
| todo | Windows displayで取得したmapping dialog画像に、反転見出しと`いいえ`が切れず表示される | regression | manual | `tmp/ui-audit`のgit管理外画像を確認する |

## 7. 設計メモ

原因はQTableViewの既定section幅とdialogの小さなsize hintである。最初の3列は標準headerのcontent-aware sizingを使い、競合列だけを余り幅へ伸長する。dialogはそのtableが最低限必要とする幅を持つ。競合の長文は全行を同時に収める対象にせず、標準scrollとtooltip等の既存UI方針を維持する。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/ui/dialogs/mapping.py` | modify | 可視列を確保する標準headerとdialog sizeを設定する |
| `tests/integration/ui/test_mapping_dialog.py` | modify | 既定表示の列幅を回帰検査する |
| `spec/wip/unit_020/MAPPING_DIALOG_VISIBLE_COLUMNS.md` | new | TDD、監査、検証結果を記録する |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/integration/ui/test_mapping_dialog.py::test_mapping_dialog_shows_default_columns_without_text_clipping -q -p no:cacheprovider` | passed | redでは対象列が100px、最長既定文字列に228px必要と検出。greenでは1 passed、全列が見出しと既定値を収め、横scrollなし |
| `uv run ruff format --check src/demi/ui/dialogs/mapping.py tests/integration/ui/test_mapping_dialog.py` / `uv run ruff check src/demi/ui/dialogs/mapping.py tests/integration/ui/test_mapping_dialog.py` / `uv run ty check --no-progress` | passed | formatting、lint、型検査が通過 |
| Windows Qt widget screenshot audit | not run | main windowと3 dialogを再確認する |
| standard gate | not run | 実装後に実行する |

## 10. 先送り事項

- computer-use native pipeの復旧は別の環境連携問題として扱う。接続復旧後は同じ画面をComputer Useでも確認する。
- profile chooser、gyro設定、Y軸反転の意味はこの可視列修正に混ぜず、別unitで要件化する。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を更新した
- [ ] 検証結果または未実行理由を記録した
- [x] package / release / public API に触れないことを確認した
