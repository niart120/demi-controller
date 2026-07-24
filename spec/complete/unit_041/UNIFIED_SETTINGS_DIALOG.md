# 設定ダイアログ統合と接続プロファイル整理 仕様書

## 1. 概要

### 1.1 目的

メインツールバーの設定操作を `Settings` 配下へまとめ、キー割り当て、接続、コントローラーカラーを1つの設定ダイアログ内で切り替えられるようにする。キー割り当て行の追加・削除を可能にし、接続設定では保存と接続を分離する。固定の接続プロファイルとアプリケーション全体の接続設定を区別し、利用者が変更する意味のないボンドスロットと接続タイムアウトを設定面から除去する。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user request | `Mappings`、`Connection settings`、`Colors` を `Settings` 配下へまとめる | conversation |
| user request | 3種類の設定を1つのタブ付きダイアログへ統合する | conversation |
| user request | キーバインディング行を追加・削除できるようにする | conversation |
| user request | 接続設定の保存時に自動接続しない | conversation |
| user request | 接続プロファイル削除、ボンドスロット除去、プロファイル設定と全体設定の区別、接続タイムアウトの非公開化 | conversation |
| user review | 削除操作と反転トグルをbinding行へ置き、行との対応を明確にする | conversation |
| user review | `Bindings` / `Mouse gyro` の入れ子をなくし、`Mouse` をSettings直下へ置く | conversation |
| user review | ツールバーのSettingsメニューもタブと同じ名称・順序へ揃える | conversation |
| user review | タブとSettingsメニューを`Connection`、`Bindings`、`Mouse`、`Colors`の順にする | conversation |
| user review | binding追加UIを利用者の選択負荷と画面占有の観点から再検討する | conversation |
| user review | Connectionタブでは`Global settings`を`Controller profile`より上に置く | conversation |
| user review | Bindings表の`Action`を`Inverted`と`Conflict`の間へ置く | conversation |
| user review | binding削除セルは`Remove`文字列ではなくゴミ箱アイコンで示す | conversation |
| initial design | Qt標準部品、単一モーダル、draftの保存・取消契約 | `spec/initial/ui.md` |
| initial design | 設定 schema と旧設定読み込み | `spec/initial/configuration.md` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| 利用者 | ツールバーの `Settings` から項目を選ぶ | 1つの設定ダイアログが選択したタブを表示する | 設定ダイアログは同時に1つだけ |
| 利用者 | 設定ダイアログ内でタブを切り替える | 同じdraftの編集を維持したまま4設定面を移動できる | 非表示のキー入力待受を残さない |
| 利用者 | 割り当て対象を選んで行を追加する | 未割り当て入力を持つ新しいbinding行が追加される | targetを選ばず暗黙追加しない |
| 利用者 | binding行の削除操作を実行する | 操作した行だけがdraftから削除される | 選択行と別の場所に削除buttonを置かない |
| 利用者 | binding行の反転トグルを操作する | その行が反転可能な場合だけ値を変更できる | 反転不可のtargetにはトグルを表示しない |
| 利用者 | 接続設定で `Save` を選ぶ | 設定が保存され、接続commandは発行されない | 接続はメイン画面の接続操作で明示する |
| 利用者 | 保存済み接続プロファイルを削除する | 確認後に固定プロファイルファイルが削除され、未保存表示になる | 設定ファイルと入力profileは削除しない |
| 設定読込 | 旧schema v1に `bond_slot` / `timeout_seconds` がある | 旧値を利用者設定として採用せず、他の設定を読み込める | schema識別子はv1を維持する |
| 接続境界 | 接続またはpairingを開始する | 固定プロファイルパスと内部固定タイムアウトを使用する | 利用者設定から値を受け取らない |

## 2. 対象範囲

- ツールバーの `Settings` 階層と4つの子action。
- `Connection`、`Bindings`、`Mouse`、`Colors` の4タブを持つ単一設定ダイアログ。
- ツールバーの `Settings` メニューに同名・同順序の4項目を置く。
- 1つの設定draftをタブ間で共有する保存・取消処理。
- binding行内の反転トグルと削除操作。
- binding targetを分類して選択する追加操作。
- Connectionタブの `Controller profile` と `Global settings` の視覚的な分離。
- 設定保存と接続command発行の分離。
- 固定Pro Controller接続プロファイルの存在表示、確認付き削除。
- `bond_slot` と利用者設定の `timeout_seconds` のdomain、codec、UIからの除去。
- 旧schema v1の `bond_slot` と `timeout_seconds` を受理して無視する読み込み互換。
- 接続commandで使う固定プロファイルパスと内部タイムアウト。
- 英語の翻訳元文言と日本語catalogの更新。
- 関連する初期仕様の現行化。

## 3. 対象外

- 複数の接続プロファイル管理。
- 接続プロファイル名、保存先、接続タイムアウトの利用者指定。
- 入力profileの新規作成、複製、名称変更、切替、profile自体の削除。
- pairing手順、Bluetooth transport、controller runtimeの再設計。
- 色pickerとマウスジャイロ各項目の挙動変更。
- 設定schema識別子の変更。

## 4. 関連 docs

- `spec/initial/ui.md`
- `spec/initial/configuration.md`
- `spec/initial/lifecycle.md`
- `spec/initial/swbt-integration.md`
- `spec/initial/testing.md`
- `spec/complete/unit_016/QT_STANDARD_CONTROLS_AND_DIALOGS.md`
- `spec/complete/unit_035/INLINE_KEY_MAPPING.md`
- `spec/complete/unit_036/COLOR_SWATCH_BUTTONS.md`
- `spec/complete/unit_040/SWBT_PYTHON_0_5_MIGRATION.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| 設定階層 | toolbarが操作可能 | `Settings` の子に `Connection`、`Bindings`、`Mouse`、`Colors` が順に表示される | 4 actionは独立したトップレベルに置かない |
| 初期タブ | 各子actionを実行 | 同じ種類の設定ダイアログが開き、同名のタブが前面になる | 既に開いている場合は2つ目を開かない |
| draft共有 | 複数タブで値を変更して保存 | 全変更を1回の保存で永続化する | 取消時は全変更を破棄し、色previewも保存値へ戻す |
| binding追加 | 分類された一覧からtargetを選択 | `KEY:UNASSIGNED`、amount `1.0`、非反転の行を末尾へ追加する | 常設のtarget選択欄で表の横幅を消費しない |
| binding削除 | 行内の削除操作を実行 | 対象行だけを削除し、残りの順序を維持する | 不正indexではdraftを変更しない |
| binding反転 | 行内の反転トグルを操作 | button targetだけが更新され、stickと診断targetは変更不可 | 表外の選択行用checkboxを置かない |
| binding列順 | Bindingsタブを表示 | `Target`、`Input`、`Inverted`、`Action`、`Conflict`、`Remove`の順に表示する | 行の変更操作を入力と反転の近くへ置く |
| binding削除表示 | Removeセルを表示 | Qt標準のゴミ箱アイコンを表示し、ツールチップで`Remove`を説明する | フォント依存の絵文字を使わない |
| タブ平坦化 | 設定ダイアログを開く | `Connection`、`Bindings`、`Mouse`、`Colors` が同じ階層に並ぶ | `Mappings`内の入れ子タブを表示しない |
| メニュー整合 | ツールバーの`Settings`を開く | `Connection`、`Bindings`、`Mouse`、`Colors` がタブと同じ順序で表示される | 各項目は同名タブを初期表示する |
| 未割り当て競合 | 未割り当て行が複数ある | `KEY:UNASSIGNED` 同士を競合として扱わない | 実入力sourceの競合判定は維持する |
| Connection区分 | Connectionタブを表示 | 全体設定を上、接続プロファイル操作を下の別groupで表示する | adapter、起動時再接続、診断レベルは全体設定 |
| 保存 | 有効なConnection draftで `Save` | repositoryへ保存してダイアログを閉じ、`ConnectSaved` を発行しない | adapter未検出でも保存済み選択値は保存可能 |
| profile削除 | 保存済み固定profileが存在 | 確認後にprofileファイルだけを削除し、削除buttonを無効化する | 取消ではファイルを残す |
| 接続固定値 | connect、startup reconnect、pairing | 固定profileファイルと30秒の内部タイムアウトをcommandへ渡す | 設定TOMLへ両値を再出力しない |
| 旧設定互換 | 旧 `bond_slot` / `timeout_seconds` を含むv1設定 | 他の有効な値を保持して読み込み、再保存時に旧keyを除去する | 旧keyの値と型は接続挙動へ影響させない |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-done | toolbarは`Settings`階層の子に4設定actionを表示し、各actionは同名tabを指定する | new / regression | unit / integration | 4 factoryを統合dialogの初期tab指定へ変更 |
| refactor-done | 1つの設定ダイアログは4タブで同じdraftを共有し、保存または取消を一度だけ処理する | new / regression | integration | 共通Save/Cancelと再接続確認を外側へ集約 |
| refactor-skipped | editorは選択targetの未割り当てbindingを末尾へ追加し、指定行だけを削除する | new / edge | unit | `12 passed`。責務は既存editor内で完結しており追加整理なし |
| refactor-done | Bindingsタブは分類menuからtargetを追加し、反転と削除を各行から実行する | new / regression | integration | 常設comboと表外checkbox・削除buttonを除去 |
| refactor-skipped | Connectionタブはprofile操作と全体設定を別groupで表示し、bond slotとtimeout controlを表示しない | new / regression | integration | `Controller profile`と`Global settings`へ分離し、旧controlを除去 |
| refactor-skipped | ConnectionのSaveは設定を保存するが接続commandを発行しない | regression | unit / integration | router経由でrepository保存と`ConnectSaved`不在を確認 |
| refactor-skipped | 固定接続profileの削除は確認時だけprofileファイルを削除してUI状態を更新する | new / edge | unit / integration | 取消、確認、固定path以外の維持、存在表示を確認 |
| refactor-skipped | current codecはbond slotとtimeoutを出力せず、旧v1 keyを無視して読み込む | regression | unit | current出力から除去し、旧keyは型に依存せず無視。domainと固定pathを整理 |
| refactor-skipped | connect、startup reconnect、pairingは固定profileパスと30秒timeoutを使う | regression | unit | 3 command経路を固定値へ統一。application境界の定数で完結 |
| refactor-skipped | 英語と日本語で設定階層、タブ、connection区分、保存、profile削除を表示できる | regression | integration / package | `155 finished`、localizationとcatalogの`3 passed` |
| refactor-skipped | 800x520で統合設定ダイアログの主要操作へ到達でき、4タブと追加menuを画像で確認する | new | integration / manual | Windows通常描画5状態で切れ、重なり、操作欠落なし |
| refactor-done | 埋め込み設定面にfocusがある状態のEscは共有draft全体を1回だけ取消する | regression | integration | child取消を共有draft ownerへrouting |
| refactor-done | Inverted列は反転可能な行だけ標準チェック状態を表示し、その場でdraftを更新する | regression | unit / integration | 表外checkboxと選択行同期を除去。Spaceと標準delegateの更新経路を使用 |
| refactor-done | 各binding行の削除操作はその行だけを削除する | regression | unit / integration | 表外削除buttonと選択行同期を除去。Remapと同じdelegate方式を再利用 |
| refactor-done | Settingsは`Connection`、`Bindings`、`Mouse`、`Colors`を入れ子なしで表示する | regression | integration | 既存mapping pagesを外側tabへ移し、入力待受の所有期間を共有dialogへ統合 |
| refactor-done | toolbarのSettings menuは4タブと同じ名称・順序で各タブを開く | regression | unit / integration | 4 factoryへ分離し、`mapping_action`と`Mappings`表記を除去 |
| refactor-done | binding追加は分類されたtargetを選択でき、選択後に未割り当て行を末尾へ追加する | regression | integration | 常設comboを分類付きmenuへ置換。全31 targetの重複・欠落なし |
| refactor-skipped | Connectionタブは`Global settings`を`Controller profile`より上に表示する | regression | integration | `6 passed`。groupの追加順だけで完結しており追加整理なし |
| refactor-skipped | Bindings表は`Action`を`Inverted`と`Conflict`の間に表示する | regression | unit / integration | `22 passed`。delegate、keyboard操作、Conflict表示を移動後の列へ追従。固定6列のため追加整理なし |
| refactor-done | binding削除セルはQt標準のゴミ箱アイコンを中央表示し、説明用ツールチップを持つ | regression | unit / integration | `23 passed`。標準iconをmodel roleで供給し、既存delegateへ中央寄せoptionを追加 |

## 7. 設計メモ

- `Settings` はツールバー上の `QToolButton` と `QMenu` で階層を表す。子actionとtabは `Connection`、`Bindings`、`Mouse`、`Colors` の同名・同順序とする。
- 単一の設定ダイアログが4タブの `QTabWidget` と共通の `QDialogButtonBox` を所有する。`Mappings`用の入れ子タブは作らず、`Bindings`と`Mouse`を同じ階層に置く。各設定面はダイアログを閉じず、共有editorだけを更新する。
- 反転と削除は対象行の値・操作なので表内に置く。追加は行がまだ存在しないため表外に置くが、target分類を開いたときだけ選択肢を表示する。
- 接続プロファイルは `SettingsPaths` が返す固定ファイル1個とする。入力mappingの `InputProfile` とは別概念であり、Connectionタブでは `Controller profile` と明記する。
- 接続タイムアウトはcontroller command境界で30秒を指定する内部定数とし、`ConnectionSettings` とTOMLから外す。
- schema識別子は `demi.settings/v1` のままとする。decoderは旧2keyを任意keyとして受理するが値を解釈しない。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/ui/toolbar.py` | modify | Settings階層 |
| `src/demi/ui/dialogs/settings.py` | new | 統合ダイアログとタブ |
| `src/demi/ui/dialogs/mapping.py` | modify | 埋め込み設定面、行追加・削除 |
| `src/demi/ui/dialogs/connection.py` | modify | 設定区分、固定profile操作、保存 |
| `src/demi/ui/dialogs/colors.py` | modify | 統合ダイアログ内の色設定面 |
| `src/demi/ui/main_window.py` | modify | 統合dialog factoryとsnapshot反映 |
| `src/demi/ui/application.py` | modify | 共有draft、保存、pairing、profile削除のrouting |
| `src/demi/application/settings_editor.py` | modify | binding追加・削除、connection field整理 |
| `src/demi/application/ui_state.py` | modify | profile存在状態 |
| `src/demi/app.py` | modify | profile削除、固定接続値、統合dialog state |
| `src/demi/domain/settings.py` | modify | connection設定境界 |
| `src/demi/config/codec.py` | modify | current出力と旧key読込互換 |
| `src/demi/config/paths.py` | modify | 固定profileパス |
| `src/demi/i18n/demi_ja.ts` | modify | 新規UI文言 |
| `src/demi/i18n/demi_ja.qm` | modify | 翻訳catalog |
| `tests/unit` | modify | editor、codec、application、toolbarの振る舞い |
| `tests/integration/ui` | modify | 統合dialog、mapping、connection、localization |
| `spec/initial` | modify | 現行UI、設定、接続契約 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/unit/ui/test_toolbar.py tests/integration/ui/test_main_window_dialogs.py tests/integration/ui/test_main_window_snapshot.py -q` | passed | `6 passed`。Settings menuと既存dialog起動回帰 |
| `uv run pytest tests/unit/application/test_settings_editor.py -q` | passed | `12 passed`。binding追加・削除、不正index、未割り当て競合 |
| `uv run ruff check src/demi/application/settings_editor.py tests/unit/application/test_settings_editor.py` | passed | editor cycleのlint |
| `uv run pytest tests/unit/ui/test_mapping_model.py tests/integration/ui/test_mapping_dialog.py -q` | passed | `19 passed`。target指定追加、選択行削除、既存mapping操作 |
| `uv run pytest tests/unit -q` | passed | `300 passed`。connection domain、codec旧設定互換、固定profile path、3 command経路を含むTDD途中の回帰確認 |
| `uv run pytest tests/unit tests/integration/ui -q` | passed | `410 passed`。Connectionの区分、Save非接続、profile削除routingを含む |
| `uv run pytest tests/unit tests/integration/ui -q` | passed | `414 passed`。統合3タブ、共有draft、初期tab、Esc取消を含む |
| `uv run pytest tests/integration/ui/test_unified_settings_dialog.py tests/integration/ui/test_qt_runtime_events.py -q` | passed | `20 passed`。統合dialogのrefactor後回帰 |
| `.venv\Scripts\pyside6-lrelease.exe src\demi\i18n\demi_ja.ts -qm src\demi\i18n\demi_ja.qm` | passed | `153 finished`、`0 unfinished` |
| `uv run pytest tests/integration/ui/test_localization.py tests/integration/package/test_translation_catalog.py -q` | passed | `3 passed`。英語、日本語、配布catalog |
| `uv run python .agents\skills\inspect-gui-states\scripts\capture_gui.py --scenario tmp\gui-audit\unit041-scenario.py --output tmp\gui-audit\unit041-20260724` | passed | Windows通常描画。Mappings、Connection、Colorsの3 PNG |
| `view_image` による `tmp/gui-audit/unit041-20260724/*.png` の原寸確認 | passed | 論理800x520。主要controlの切れ、重なり、欠落なし |
| `uv sync --dev` | passed | 77 packages resolved、74 packages checked |
| `uv lock --check` | passed | lock file変更なし |
| `uv run ruff format --check .` | passed | 148 files formatted |
| `uv run ruff check .` | passed | 全lint検査成功 |
| `uv run ty check --no-progress` | passed | 全型検査成功 |
| `uv run pytest tests/unit` | passed | `303 passed`。integrationとの並行実行では`tmp/pytest`の清掃が競合したため、単独で再実行 |
| `uv run pytest tests/integration` | passed | `131 passed`。controller、input、package、UIを含む。単独で再実行 |
| `uv build` | passed | sdistとwheelを作成 |
| `git diff --check` | passed | 空白エラーなし |
| `rg`による公開文書、作業仕様、翻訳catalogの仮テキスト検索 | passed | 仮テキスト標識なし |
| `rg`による廃止UI文言と部品名の残存検索 | passed | 現行のSettings経路と公開文書に旧3タブ構成なし。単体利用する`MappingDialog`内部の互換tab名、翻訳catalogの`vanished`項目、不存在を確認するtest名は対象外 |
| `uv run pytest tests/unit/ui/test_mapping_model.py tests/integration/ui/test_mapping_dialog.py -q` | passed | `20 passed`。行内Invertedトグルと既存mapping操作 |
| `uv run pytest tests/unit/ui/test_mapping_model.py tests/integration/ui/test_mapping_dialog.py tests/unit/ui/test_mapping_delegate.py -q` | passed | `22 passed`。行内Removeとdelegate回帰 |
| `uv run pytest tests/integration/ui/test_unified_settings_dialog.py -q` | passed | `3 passed`。4タブの平坦化、順序、共有draft |
| `uv run pytest tests/unit/ui/test_toolbar.py tests/integration/ui/test_unified_settings_dialog.py tests/integration/ui/test_main_window_dialogs.py tests/integration/ui/test_main_window_snapshot.py tests/integration/ui/test_qt_runtime_events.py -q` | passed | `27 passed`。4 action、同名tab routing、modal排他 |
| `uv run pytest tests/integration/ui/test_mapping_dialog.py tests/integration/ui/test_unified_settings_dialog.py -q` | passed | `19 passed`。分類menuの全31 target、追加、行内操作、共有draft |
| `uv run ty check --no-progress src/demi/ui/dialogs/mapping.py tests/integration/ui/test_mapping_dialog.py tests/integration/ui/test_unified_settings_dialog.py` | passed | 追加menuとQt型境界 |
| `uv run python .agents\skills\inspect-gui-states\scripts\capture_gui.py --scenario tmp\gui-audit\unit041-scenario.py --output tmp\gui-audit\unit041-followup-menu-20260724` | passed | Windows通常描画。4タブと追加menuの5 PNG |
| `view_image` によるfollow-up PNGの原寸確認 | passed | 800x520で列、チェック、行操作、4タブ、分類menuの切れ・重なりなし |
| `.venv\Scripts\pyside6-lrelease.exe src\demi\i18n\demi_ja.ts -qm src\demi\i18n\demi_ja.qm` | passed | `155 finished`、`0 unfinished` |
| `uv run pytest tests/integration/ui/test_localization.py tests/integration/package/test_translation_catalog.py -q` | passed | `3 passed`。4 action、4 tab、分類menu、行内Remove |
| `uv run pytest tests/integration/ui/test_connection_dialog.py -q` | passed | `6 passed`。`Global settings`、`Controller profile`の表示順と既存保存操作 |
| `uv run pytest tests/unit/ui/test_mapping_model.py tests/unit/ui/test_mapping_delegate.py tests/integration/ui/test_mapping_dialog.py -q` | passed | `22 passed`。Action列移動、delegate、keyboard操作、Conflict表示 |
| `uv run pytest tests/unit/ui/test_mapping_model.py tests/unit/ui/test_mapping_delegate.py tests/integration/ui/test_mapping_dialog.py -q` | passed | `23 passed`。ゴミ箱icon、tooltip、既存の行削除操作 |
| `uv run ty check --no-progress src/demi/ui/dialogs/mapping.py tests/unit/ui/test_mapping_model.py tests/unit/ui/test_mapping_delegate.py tests/integration/ui/test_mapping_dialog.py` | passed | ゴミ箱iconのQt model roleとdelegate型境界 |
| `uv run python .agents\skills\inspect-gui-states\scripts\capture_gui.py --scenario tmp\gui-audit\unit041-scenario.py --output tmp\gui-audit\unit041-layout-followup-20260724` | passed | Windows通常描画。Connection、Bindings、追加menu、Mouse、Colorsの5 PNG |
| `view_image` によるConnectionとBindings PNGの原寸確認 | passed | 800x520でgroup順、列順、右端のゴミ箱iconを確認。切れ、重なり、横scrollなし |

## 10. 先送り事項

- none

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test Listを更新した
- [x] 検証結果または未実行理由を記録した
- [x] package / release / public APIに触れる場合のgateを記録した
