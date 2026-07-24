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
| initial design | Qt標準部品、単一モーダル、draftの保存・取消契約 | `spec/initial/ui.md` |
| initial design | 設定 schema と旧設定読み込み | `spec/initial/configuration.md` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| 利用者 | ツールバーの `Settings` から項目を選ぶ | 1つの設定ダイアログが選択したタブを表示する | 設定ダイアログは同時に1つだけ |
| 利用者 | 設定ダイアログ内でタブを切り替える | 同じdraftの編集を維持したまま3設定面を移動できる | 非表示のキー入力待受を残さない |
| 利用者 | 割り当て対象を選んで行を追加する | 未割り当て入力を持つ新しいbinding行が追加される | targetを選ばず暗黙追加しない |
| 利用者 | binding行を選んで削除する | 選択した行だけがdraftから削除される | 選択がない場合は削除不可 |
| 利用者 | 接続設定で `Save` を選ぶ | 設定が保存され、接続commandは発行されない | 接続はメイン画面の接続操作で明示する |
| 利用者 | 保存済み接続プロファイルを削除する | 確認後に固定プロファイルファイルが削除され、未保存表示になる | 設定ファイルと入力profileは削除しない |
| 設定読込 | 旧schema v1に `bond_slot` / `timeout_seconds` がある | 旧値を利用者設定として採用せず、他の設定を読み込める | schema識別子はv1を維持する |
| 接続境界 | 接続またはpairingを開始する | 固定プロファイルパスと内部固定タイムアウトを使用する | 利用者設定から値を受け取らない |

## 2. 対象範囲

- ツールバーの `Settings` 階層と3つの子action。
- `Mappings`、`Connection`、`Colors` の3タブを持つ単一設定ダイアログ。
- 1つの設定draftをタブ間で共有する保存・取消処理。
- binding行のtarget指定追加と選択行削除。
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
| 設定階層 | toolbarが操作可能 | `Settings` の子に `Mappings`、`Connection`、`Colors` が順に表示される | 3 actionは独立したトップレベルに置かない |
| 初期タブ | 各子actionを実行 | 同じ種類の設定ダイアログが開き、選択したタブが前面になる | 既に開いている場合は2つ目を開かない |
| draft共有 | 複数タブで値を変更して保存 | 全変更を1回の保存で永続化する | 取消時は全変更を破棄し、色previewも保存値へ戻す |
| binding追加 | targetを選択して追加 | `KEY:UNASSIGNED`、amount `1.0`、非反転の行を末尾へ追加する | targetは全 `BindingTarget` から選べる |
| binding削除 | 行を選択して削除 | 対象行だけを削除し、残りの順序を維持する | 不正indexではdraftを変更しない |
| 未割り当て競合 | 未割り当て行が複数ある | `KEY:UNASSIGNED` 同士を競合として扱わない | 実入力sourceの競合判定は維持する |
| Connection区分 | Connectionタブを表示 | 接続プロファイル操作と全体設定を別groupで表示する | adapter、起動時再接続、診断レベルは全体設定 |
| 保存 | 有効なConnection draftで `Save` | repositoryへ保存してダイアログを閉じ、`ConnectSaved` を発行しない | adapter未検出でも保存済み選択値は保存可能 |
| profile削除 | 保存済み固定profileが存在 | 確認後にprofileファイルだけを削除し、削除buttonを無効化する | 取消ではファイルを残す |
| 接続固定値 | connect、startup reconnect、pairing | 固定profileファイルと30秒の内部タイムアウトをcommandへ渡す | 設定TOMLへ両値を再出力しない |
| 旧設定互換 | 旧 `bond_slot` / `timeout_seconds` を含むv1設定 | 他の有効な値を保持して読み込み、再保存時に旧keyを除去する | 旧keyの値と型は接続挙動へ影響させない |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-skipped | toolbarは`Settings`階層の子に3設定actionを表示し、各actionは選択タブを指定する | new | unit / integration | Settings menu階層はgreen。選択タブroutingは次の統合dialog cycleで確認 |
| todo | 1つの設定ダイアログは3タブで同じdraftを共有し、保存または取消を一度だけ処理する | new | integration | 色preview取消も確認 |
| todo | editorは選択targetの未割り当てbindingを末尾へ追加し、指定行だけを削除する | new / edge | unit | 不正indexと未割り当て競合を含む |
| todo | Mappingsタブはtarget指定追加と選択行削除を標準controlから実行する | new | integration | modelの行通知とbutton状態を確認 |
| todo | Connectionタブはprofile操作と全体設定を別groupで表示し、bond slotとtimeout controlを表示しない | new / regression | integration | 利用者向け境界 |
| todo | ConnectionのSaveは設定を保存するが接続commandを発行しない | regression | unit / integration | `Save and connect`を廃止 |
| todo | 固定接続profileの削除は確認時だけprofileファイルを削除してUI状態を更新する | new / edge | unit / integration | profileなし、取消を含む |
| todo | current codecはbond slotとtimeoutを出力せず、旧v1 keyを無視して読み込む | regression | unit | 他keyとschemaの厳格性は維持 |
| todo | connect、startup reconnect、pairingは固定profileパスと30秒timeoutを使う | regression | unit | application command境界 |
| todo | 英語と日本語で設定階層、タブ、connection区分、保存、profile削除を表示できる | regression | integration / package | catalog再生成を含む |
| todo | 800x520で統合設定ダイアログの主要操作へ到達でき、3タブの状態を画像で確認する | new | integration / manual | Windows通常描画 |

## 7. 設計メモ

- `Settings` はツールバー上の `QToolButton` と `QMenu` で階層を表す。子actionは既存の利用者向け名称を `Connection` に揃える。
- 単一の設定ダイアログが `QTabWidget` と共通の `QDialogButtonBox` を所有する。各設定面はダイアログを閉じず、共有editorだけを更新する。
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
| TDD itemごとの対象pytest | not run | 実装前 |
| `uv run pytest tests/unit` | not run | 実装前 |
| `uv run pytest tests/integration` | not run | 実装前 |
| `uv lock --check` | not run | 実装前 |
| `uv run ruff format --check .` | not run | 実装前 |
| `uv run ruff check .` | not run | 実装前 |
| `uv run ty check --no-progress` | not run | 実装前 |
| `uv build` | not run | 実装前 |
| `git diff --check` | not run | 実装前 |
| Windows GUI画像確認 | not run | 実装前 |

## 10. 先送り事項

- none

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test Listを更新した
- [ ] 検証結果または未実行理由を記録した
- [ ] package / release / public APIに触れる場合のgateを記録した
