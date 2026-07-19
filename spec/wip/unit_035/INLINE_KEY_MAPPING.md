# 行内キー割り当て操作 仕様書

## 1. 概要

### 1.1 目的

キー割り当ての開始操作を対象行の中へ移し、どのcontroller入力を変更しているか分かる状態で次の入力を待ち受ける。`Escape`で待受を中止できるようにしつつ、`Escape`自体を割り当てる明示操作も残す。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user review | 表の外にある「次の入力を取得」では変更対象が分かりにくい | 対話、2026-07-19 |
| user proposal | 各行にbuttonを置くか、現在の割り当てcellをclickして待受を始める | 対話、2026-07-19 |
| user request | key mappingをescapeできる仕組みが必要 | 対話、2026-07-19 |
| input redesign | `F4`をmouse capture解除に予約し、`F12`は通常入力へ戻す | `spec/complete/unit_033/POINTER_CAPTURE_AND_KEYBOARD_ROUTING.md` |
| current implementation | 選択行、外部capture button、固定status labelで待受を操作する | `src/demi/ui/dialogs/mapping.py` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| mouse user | A行の`Remap`を押す | A行だけが待受状態になり、次のkeyまたはmouse buttonをAへ設定する | 表外の開始buttonを使わない |
| keyboard user | assigned input cellへfocusし`Enter`を押す | 同じ行の待受を開始する | Tab順とfocus表示を維持する |
| user | 待受中に`Escape`を押す | 待受だけを中止し、draft bindingを変更しない | dialog自体は閉じない |
| user | controller入力へ`Escape`を割り当てる | 行の補助操作`Assign Escape`から設定できる | 通常の待受ではEscapeをcancelに使う |
| user | 待受中に`F4`を押す | 予約keyであることを行内に表示し、割り当てを変更しない | pointer capture releaseと競合させない |
| user | 既存sourceと重複する入力を選ぶ | 対象と競合先を示して置換確認する | 現行の競合防止を弱めない |

## 2. 対象範囲

- mapping tableに操作列を追加し、各行から`Remap`を開始できるようにする。
- assigned input cellのdouble clickと、focus時の`Enter` / `Space`から同じremap commandを実行する。
- 待受中の行を選択色だけに依存せず、input cellのinstructionとactionの`Cancel`で示す。
- 待受中の`Escape`はdraftを変更せず待受だけを中止する。
- `Escape`をsourceとして設定するため、対象行のcontext menuとkeyboardから到達可能な`Assign Escape`操作を用意する。
- `F4`を予約keyとして拒否し、理由を対象行のstatusまたはvalidation messageへ表示する。
- `F12`は通常のkey sourceとして待受・保存・再表示できるようにする。
- canonical sourceの`KEY:F`、`BUTTON:MIDDLE`を永続値に保ち、表には`F`、`Middle mouse`などの利用者向け表記を出す。
- sourceの詳細とcanonical値はtooltipまたはaccessible descriptionから確認可能にする。
- conflict確認は対象行、入力source、既存割り当て先を明示し、cancel時は両方を保持する。
- bindingsとmouse gyro設定をtabまたは明確なsectionへ分け、行内remap中に無関係な設定へfocusを移しにくくする。
- inversionなど選択bindingに依存する操作は、対象行または行の詳細領域との関係が分かる位置へ移す。
- `QTableView`とmodel / delegateを維持し、行数分の常設Widgetを生成しない。
- unit_032後の追加文言は英語source textとし、日本語catalogへ追加する。
- `spec/initial/configuration.md`、`spec/initial/input.md`、`spec/initial/testing.md`、`spec/initial/ui.md`を更新する。

## 3. 対象外

- 1つのcontroller入力へ複数sourceを同時に割り当てる編集UI。
- profile import / export、profile差分表示、一括割り当てwizard。
- keyboard chordや長押しsequenceの新規binding形式。
- `setIndexWidget()`による行数分の`QPushButton`配置。paintとeditor eventを扱うdelegateを使う。
- `Escape`でmapping dialog全体を閉じること。待受中はremap cancelを優先する。
- local action全体のshortcut editor。`F4`予約規則だけをこの画面へ反映する。

## 4. 関連 docs

- `spec/initial/configuration.md`
- `spec/initial/input.md`
- `spec/initial/requirements.md`
- `spec/initial/testing.md`
- `spec/initial/ui.md`
- `spec/complete/unit_003/INPUT_PIPELINE.md`
- `spec/complete/unit_015/QT_INPUT_AND_CONTROLLER_PREVIEW.md`
- `spec/complete/unit_016/QT_STANDARD_CONTROLS_AND_DIALOGS.md`
- `spec/complete/unit_032/UI_LOCALIZATION_FOUNDATION.md`
- `spec/complete/unit_033/POINTER_CAPTURE_AND_KEYBOARD_ROUTING.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| 行からremapする | action clickまたはinput cell activation | 対象row idを持つ待受へ入り、その行だけinstructionを表示する | selectionだけを対象識別に使わない |
| 待受をcancelする | 待受中のEscape、同じ行のCancel | 待受前のdraftを維持し、行表示を元へ戻す | dialogは開いたまま |
| Escapeを割り当てる | 行の`Assign Escape`補助操作 | conflict確認後に`KEY:ESCAPE`をdraftへ設定する | mouseとkeyboardの両方から到達可能にする |
| reserved keyを拒否する | 待受中のF4 | draftを変えず、F4がpointer capture releaseであることを表示する | 待受は継続または明示cancel可能とする |
| F12を割り当てる | 待受中のF12 | 通常sourceとしてdraftに反映し、save後に往復する | legacy固定予約を除去する |
| conflictを解決する | 他rowで使用中のsource | replace / cancelを提示し、replace時だけ旧rowを解除する | 対象名とsourceを表示する |
| 表示名を変換する | canonical sourceをmodelへ渡す | localeに応じたfriendly labelを表示し、canonical値を保持する | model roleを分ける |
| 設定領域を切り替える | Bindings / Mouse gyro tab | mapping待受はBindings内で完結し、tab移動時は安全にcancelする | 隠れた待受を残さない |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-skipped | 全binding rowにdelegateのRemap actionがあり、clickとkeyboard activationが同じrow idで待受を開始する | new | unit / integration | 11件green。列単位delegateと単一row commandで成立し追加の構造変更なし |
| refactor-done | 待受中は対象input cellにinstruction、actionにCancelを表示し、他rowの表示は変えない | new | unit | 12件green。dialogとmodelの二重状態を同時resetする境界へ整理 |
| refactor-done | Escape keyとCancel actionは待受前のdraftを保持して待受だけを中止する | new / regression | integration | 13件green。keyとactionを共通取消処理へ集約し、action clickをsource captureから除外 |
| refactor-skipped | context menuとkeyboardからAssign Escapeを実行でき、KEY:ESCAPEを保存・再表示できる | new / regression | integration | 14件green。context menuとshortcutが単一QActionを共有し追加の構造変更なし |
| refactor-skipped | F4は理由付きで拒否され、F12は通常bindingとしてcapture、save、reloadできる | regression | unit / integration | 20件green。SettingsEditorの予約規則を維持しdialog待受だけ理由表示を追加 |
| refactor-done | conflict dialogはsource、変更先、既存割り当て先を示し、cancel時はdraftを一切変更しない | regression | unit / integration | 21件green。候補確認とatomic置換をapplication/editor境界へ分離 |
| refactor-done | canonical sourceとfriendly display roleを分離し、locale変更で永続値が変わらない | new / regression | unit | 16件green。display変換をmodel境界へ分離しcanonical roleを保持 |
| refactor-done | Bindings / Mouse gyro間のtab移動は待受を残さず、Tab順がrow actionとSave / Cancelへ到達する | new / edge | integration | 16件green。tab変更時の取消とAction列keyboard転送を追加 |
| refactor-done | mapping dialogから表外の「次の入力を取得」buttonと固定対象labelがなくなる | regression | integration | 22件green。入力待受を行内Actionへ限定し、予約・不正入力の説明を対象行の状態列へ集約 |
| refactor-done | Windows通常描画で選択、待受、reserved、conflict後の状態が不自然に見えない | new | manual | 6状態を原寸確認。待受終了後に予約理由が残る不具合を修正し再取得 |

## 7. 設計メモ

表内に実button Widgetを行数分埋め込むとfocus、scroll、model更新が複雑になる。操作列は`QStyledItemDelegate`でbutton相当を描画し、mouse releaseとkeyboard eventをrow commandへ変換する。accessible actionがdelegateだけでは不足する場合はtable側のactionとcontext menuを同じcommandへ接続する。

`Escape`は待受の中止に使うため、通常の次入力captureだけではsourceとして区別できない。時間差や長押しで意味を変えず、`Assign Escape`という明示操作を用意する。これによりcancelは即時かつ予測可能なまま、既存のEscape bindingも保持できる。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/ui/dialogs/mapping.py` | modify | tab構成、table model / delegate、行内remap、待受状態、補助操作 |
| `src/demi/application/settings_editor.py` | modify | F4予約、F12許可、Escape明示割り当て、conflict処理 |
| `tests/unit/ui/test_mapping_model.py` | modify | role、row state、friendly label |
| `tests/unit/ui/test_mapping_delegate.py` | new | hit testとrow command |
| `tests/integration/ui/test_mapping_dialog.py` | modify | click、keyboard、cancel、tab、conflict |
| `tests/unit/application/test_settings_editor.py` | modify | reserved / conflict / draft保持 |
| `spec/initial/configuration.md` | modify | binding表示と予約key |
| `spec/initial/input.md` | modify | remap captureとEscape規則 |
| `spec/initial/testing.md` | modify | delegate、keyboard、accessibility受入 |
| `spec/initial/ui.md` | modify | 行内操作とdialog構成 |
| `spec/wip/unit_035/INLINE_KEY_MAPPING.md` | new | 作業境界と検証記録 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/unit/test_documentation.py tests/unit/test_work_unit_records.py` | pass | 3 passed、仕様作成時の文書構造を確認 |
| `uv run pytest -p no:cacheprovider --basetemp tmp/pytest/unit035-delegate-green2 tests/unit/ui/test_mapping_delegate.py tests/unit/ui/test_mapping_model.py tests/integration/ui/test_mapping_dialog.py -q` | pass | 11 passed。mouse / keyboardが同じrow commandを発行し、行Widgetを生成しないことを確認 |
| `uv run pytest -p no:cacheprovider --basetemp tmp/pytest/unit035-rowstate-green3 tests/unit/ui/test_mapping_model.py tests/unit/ui/test_mapping_delegate.py tests/integration/ui/test_mapping_dialog.py -q` | pass | 12 passed。対象行だけのinstruction / Cancel表示と既存capture往復を確認 |
| `uv run pytest -p no:cacheprovider --basetemp tmp/pytest/unit035-cancel-green2 tests/integration/ui/test_mapping_dialog.py tests/unit/ui/test_mapping_model.py tests/unit/ui/test_mapping_delegate.py -q` | pass | 13 passed。Escapeと行内Cancelがdraftとdialogを保持することを確認 |
| `uv run pytest -p no:cacheprovider --basetemp tmp/pytest/unit035-escape-green tests/integration/ui/test_mapping_dialog.py tests/unit/ui/test_mapping_model.py tests/unit/ui/test_mapping_delegate.py -q` | pass | 14 passed。Assign Escape actionのcontext menu登録、shortcut、保存、再表示を確認 |
| `uv run pytest -p no:cacheprovider --basetemp tmp/pytest/unit035-f4-green tests/unit/application/test_settings_editor.py tests/integration/ui/test_mapping_dialog.py tests/integration/ui/test_dialog_validation.py -q` | pass | 20 passed。F4理由表示と待受継続、F12 captureと再表示、予約source拒否を確認 |
| `uv run pytest -p no:cacheprovider --basetemp tmp/pytest/unit035-conflict-green3 tests/unit/application/test_settings_editor.py tests/integration/ui/test_mapping_dialog.py -q` | pass | 21 passed。重複source、変更先、既存先の表示、Cancel無変更、Replace時の旧row解除を確認 |
| `uv run pytest -p no:cacheprovider --basetemp tmp/pytest/unit035-friendly-green2 tests/unit/ui/test_mapping_model.py tests/integration/ui/test_mapping_dialog.py tests/integration/ui/test_localization.py -q` | pass | 16 passed。friendly表示、canonical role、保存往復を確認 |
| `uv run pytest -p no:cacheprovider --basetemp tmp/pytest/unit035-tabs-green2 tests/integration/ui/test_mapping_dialog.py tests/unit/ui/test_mapping_delegate.py -q` | pass | 16 passed。tab移動の待受取消、Action列keyboard操作、Save / Cancel focusを確認 |
| `uv run pytest -p no:cacheprovider --basetemp tmp/pytest/unit035-inline-only-green2 tests/unit/ui/test_mapping_model.py tests/unit/ui/test_mapping_delegate.py tests/integration/ui/test_mapping_dialog.py tests/integration/ui/test_dialog_validation.py tests/integration/ui/test_localization.py -q` | pass | 22 passed。表外取得buttonと固定labelの不在、行内待受、行内の予約・不正入力説明を確認 |
| `uv run python .agents/skills/inspect-gui-states/scripts/capture_gui.py --scenario tmp/gui-audit/unit-035-inline/scenario.py --output tmp/gui-audit/unit-035-inline` | pass | Windows通常描画で6 PNGを取得。通常、選択、待受、F4予約、競合確認に文字切れ・重なりなし。待受と予約理由が対象行だけに表示されることを目視確認 |
| `uv run pytest -p no:cacheprovider --basetemp tmp/pytest/unit035-visual-fix tests/unit/ui/test_mapping_model.py tests/integration/ui/test_mapping_dialog.py -q` | pass | 18 passed。待受の移動・取消で直前行の一時statusが消えることを確認 |
| `$inspect-gui-states`による`capture-02`の6状態 | pass | Windows通常描画の通常、選択、待受、F4予約、競合確認、置換後を原寸確認。文字切れなし、置換後の古い予約理由なし |
| `uv sync --dev` / `uv lock --check` | pass | 77 packagesを解決しlock整合を確認 |
| `uv run ruff format --check .` / `uv run ruff check .` | pass | 148 files formatted、lint errorなし |
| `uv run ty check --no-progress` | pass | 型errorなし |
| `uv run pytest -p no:cacheprovider --basetemp tmp/pytest/unit035-unit2 tests/unit` | pass | 278 passed |
| `uv run pytest -p no:cacheprovider --basetemp tmp/pytest/unit035-int-nonui2 tests/integration --ignore=tests/integration/ui` | pass | 15 passed |
| `uv run pytest -p no:cacheprovider --basetemp tmp/pytest/unit035-int-ui2 tests/integration/ui --ignore=tests/integration/ui/test_source_entry_points.py` | pass | 76 passed |
| `uv run pytest -p no:cacheprovider --basetemp tmp/pytest/unit035-entry2 tests/integration/ui/test_source_entry_points.py` | pass | 3 passed |
| `$env:PYTHONUTF8='1'; uv build` | pass | sdistとwheelを生成 |
| `git diff --check` | pass | whitespace errorなし |

## 10. 先送り事項

- 複数source割り当てとbinding検索は、1行1sourceの編集が安定した後に別unitで扱う。
- local action shortcut editorと`Ctrl+C`競合の解消は、pointer capture操作全体を扱う別unitへ分ける。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test Listを作成した
- [x] 実装検証が未実行である理由を記録した
- [x] Escape cancelとEscape割り当ての両立方法を定義した
- [x] 行内remapのmouse / keyboard操作をgreenにした
- [x] F4予約とF12許可をunit_033と共通化した
- [x] `$inspect-gui-states`で代表画面を評価した
