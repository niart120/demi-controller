# マウスジャイロ設定GUIと水平反転 仕様書

## 1. 概要

### 1.1 目的

保存設定に存在するマウスジャイロ項目をキー割り当てダイアログから編集できるようにし、垂直反転と対になる水平反転を追加する。初回設定では水平反転と垂直反転をともに無効とし、マウス上とI、マウス下とKが同じジャイロY方向になる現行の非反転契約を維持する。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user observation | 保存済みの垂直反転がマウスとI/Kの上下方向を逆転させているが、GUIに変更項目がない | 対話 |
| user request | 垂直反転と対になる水平反転を追加し、垂直反転の既定値を `false` とする | 対話 |
| initial UI | キー割り当てダイアログ内でマウスジャイロ設定を編集する | `spec/initial/ui.md` |
| current domain | `MouseSettings` と `SettingsEditor.update_mouse()` は垂直反転を保持するがQt GUIから呼ばれない | `src/demi/domain/settings.py`、`src/demi/application/settings_editor.py` |
| current GUI | ツールバーから開ける設定画面は割り当て、接続設定、色の3種類 | `src/demi/ui/toolbar.py`、`src/demi/ui/application.py` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| 利用者 | キー割り当てダイアログを開く | 保存済みの有効状態、感度、水平反転、垂直反転、pitch上限を標準controlで確認できる | 新しい独立ダイアログは増やさない |
| 利用者 | 水平反転だけを有効にする | マウス左右のyaw方向だけが反転する | 垂直方向と感度は変えない |
| 利用者 | 垂直反転だけを有効にする | マウス上下のpitch方向だけが反転する | I/K診断入力には適用しない |
| 利用者 | 設定を保存する | TOMLへ保存され、以後の入力評価へ即時反映される | 設定画面を開く既存のneutral契約を維持する |
| 利用者 | 設定を取り消す | 編集前の設定と入力方向を維持する | draftを永続化しない |
| 既存利用者 | `invert_x` がない `demi.settings/v1` を読み込む | 水平反転 `false` を補完し、明示済みの `invert_y` は保持する | 破損設定として復旧しない |

## 2. 対象範囲

- `MouseSettings` に `invert_x: bool = False` を追加し、`invert_y: bool = False` の既定値を明示的な回帰試験で固定する。
- TOMLの `[input.mouse]` に `invert_x` を保存する。
- `invert_x` 欠落の既存schema v1を `false` として読み込み、次回の明示保存で項目を出力する。
- 明示保存済みの `invert_y = true` は既存利用者の選択として保持し、読み込み時に上書きしない。
- マウスyaw変換へ水平反転を適用し、水平・垂直の反転を互いに独立させる。
- `SettingsEditor.update_mouse()` で水平反転を編集する。
- キー割り当てダイアログへマウスジャイロ設定の `QGroupBox` と標準form controlを追加する。
- 保存、取消、live `InputPublisher` 再設定を既存のsettings modal経路へ接続する。
- 関連する初期仕様とUnit 030のマウス設定記述を現在契約へ更新する。

## 3. 対象外

- Unit 030の統一回転意図・姿勢モデルの実装。
- マウス差分の再標本化アルゴリズム、感度計算式、基準角度の変更。
- pitch上限の既定値75度の変更。
- I/J/K/L診断入力へマウス反転設定を適用すること。
- 新しい設定schema識別子への更新。
- 保存済みの明示的な `invert_y = true` を強制的に `false` へ書き換えること。
- GUIから評価周期または円形スティック制限を編集すること。

## 4. 関連 docs

- `spec/initial/configuration.md`
- `spec/initial/input.md`
- `spec/initial/requirements.md`
- `spec/initial/testing.md`
- `spec/initial/ui.md`
- `spec/complete/unit_002/DOMAIN_AND_SETTINGS.md`
- `spec/complete/unit_007/SETTINGS_MODAL.md`
- `spec/complete/unit_016/QT_STANDARD_CONTROLS_AND_DIALOGS.md`
- `spec/wip/unit_030/UNIFIED_ROTATION_POSE_MODEL.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| 反転の既定値を作る | `MouseSettings()` または初回設定 | `invert_x is False`、`invert_y is False` | 上下はマウス上=I、マウス下=Kの符号 |
| 既存設定を読む | schema v1のmouse tableに `invert_x` がない | `invert_x is False`、既存の `invert_y` は入力値を保持 | 読込失敗やRECOVEREDにしない |
| 現在設定を往復する | X/Y反転を任意に設定してTOML保存・読込 | 両方の真偽値が一致する | 保存時は `invert_x` を必ず出力 |
| 水平だけ反転する | 同じ `dx`、`invert_x` のみ切替 | ジャイロX/Zのyaw由来符号だけが逆転する | pitchと加速度は同じ |
| 垂直だけ反転する | 同じ `dy`、`invert_y` のみ切替 | ジャイロYとpitch由来加速度Xの符号だけが逆転する | yaw方向は同じ |
| GUIへ現在値を表示する | 保存済みmouse設定で割り当て画面を開く | checkboxと数値controlがdraftと一致する | 水平・垂直感度は0.1..10.0、pitch上限は1.0..89.0 |
| GUIでdraftを編集する | 各controlを変更する | 他項目を変えず `SettingsEditor` のmouse draftへ反映する | Qt標準controlを使用 |
| GUI編集を保存する | mouse draftを変更して保存 | repositoryとsession設定が更新され、live Publisherが新しい反転を使う | modalはAcceptedで閉じる |
| GUI編集を取り消す | mouse draftを変更して取消 | repository、session、live Publisherを変更しない | modalはRejectedで閉じる |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-skipped | 初回設定でX/Y反転がともに無効となり、既存schema v1の `invert_x` 欠落をfalseで補完し、明示済みY反転を保持してTOML往復する | new / regression | unit | redはfield不在で4件失敗。greenはdomain/codec 23件。field末尾追加で位置引数順を維持し、追加整理なし |
| refactor-skipped | 水平反転がyawだけ、垂直反転がpitchだけを反転し、両方の無効時はマウス上/下がI/Kと同じ符号になる | new / regression | unit | redは水平反転でyaw不変の1件。greenはモデルとPublisher方向比較14件。方向係数1か所で完結し追加整理なし |
| refactor-skipped | settings editorが水平反転を含むmouse項目を独立して更新し、入力loop設定を変えてもmouse設定を保持する | new / regression | unit | redはkeyword未対応で2件。greenはeditor 8件。既存の単一再構築経路へ追加し重複なし |
| refactor-done | キー割り当てダイアログが保存済みmouse設定を標準controlへ表示し、全controlの変更をdraftへ反映する | new | integration | redはgroup不在。green後に感度spinbox構築を共通化し、全MappingDialog 8件で不変確認 |
| refactor-skipped | GUIの保存がrepository、session、live Publisherへ反映され、取消は編集前の設定を維持する | new / regression | integration | production routerとmodal経路の回帰2件は追加直後からgreen。既存保存経路を再利用し追加整理なし |
| refactor-skipped | 全unit / integration treeとpackage buildが新旧schema v1の両方で通る | regression | package | unit 245件、integration 79件、buildがgreen。追加整理なし |

## 7. 設計メモ

### 7.1 Tidy First判定

- classification: behavior
- action: split
- reason: 新しい設定値、設定互換、回転符号、GUI操作を追加するため。Unit 030の姿勢モデル置換とは分離する。
- verification: 設定読込、変換モデル、GUI draft、保存後のlive Publisherを境界ごとに確認する。

### 7.2 反転の意味

設定名はマウスnative差分に合わせて `invert_x` / `invert_y` とする。GUIでは座標軸だけを露出せず「水平反転」「垂直反転」と表示する。`invert_x = false` は現行の `yaw_delta = -dx * 基準角度 * 感度` を維持し、`true` のときだけ符号を反転する。`invert_y = false` は現行の `pitch_delta = dy * 基準角度 * 感度` を維持する。

### 7.3 schema v1互換

`invert_x` はschema v1へ追加する省略可能な読込項目とする。decoderは欠落時に `false` を補完し、encoderは常に出力する。未知項目の拒否は維持する。既存の `invert_y` は必須のままとし、明示値を変更しない。

### 7.4 GUI境界

初期UI仕様どおり、マウスジャイロ設定はキー割り当てダイアログ内の `QGroupBox` に置く。独立したtoolbar action、dialog kind、draft所有者は増やさない。widgetは値を直接保存せず、変更ごとにapplication-owned `SettingsEditor` のdraftを更新する。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/domain/settings.py` | modify | `MouseSettings.invert_x` とX/Y既定値 |
| `src/demi/config/codec.py` | modify | `invert_x` の保存と既存schema v1補完 |
| `src/demi/application/settings_editor.py` | modify | 水平反転を含むmouse draft更新 |
| `src/demi/input/yaw_pitch_model.py` | modify | 水平反転のyaw符号 |
| `src/demi/ui/dialogs/mapping.py` | modify | マウスジャイロ設定groupと標準control |
| `tests/unit/domain/test_settings.py` | modify | X/Y反転の既定値と型制約 |
| `tests/unit/config/test_codec.py` | modify | 新旧schema v1互換とTOML往復 |
| `tests/unit/application/test_settings_editor.py` | modify | mouse draftの独立更新 |
| `tests/unit/input/test_yaw_pitch_model.py` | modify | 水平・垂直反転と非干渉 |
| `tests/unit/input/test_publisher.py` | modify | 既定のマウス上下とI/Kの方向一致 |
| `tests/unit/application/test_app.py` | modify | 保存後のlive Publisher反映 |
| `tests/integration/ui/test_mapping_dialog.py` | modify | control表示、draft更新、保存・取消 |
| `tests/integration/ui/test_qt_runtime_events.py` | modify | production GUI routeからの保存 |
| `spec/initial/configuration.md` | modify | `invert_x`、既定値、旧設定補完 |
| `spec/initial/input.md` | modify | X/Y反転とyaw変換 |
| `spec/initial/requirements.md` | modify | 水平・垂直反転の受入条件 |
| `spec/initial/testing.md` | modify | X/Y反転、codec、GUIの試験項目 |
| `spec/initial/ui.md` | modify | 水平・垂直反転control |
| `spec/wip/unit_030/UNIFIED_ROTATION_POSE_MODEL.md` | modify | 後続モデルがX/Y反転を受け取る契約 |
| `spec/complete/unit_031/MOUSE_GYRO_SETTINGS_GUI.md` | new | 作業範囲、TDD状態、検証記録 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/unit/domain/test_settings.py tests/unit/config/test_codec.py tests/unit/application/test_settings_editor.py tests/unit/input/test_yaw_pitch_model.py tests/unit/application/test_app.py tests/integration/ui/test_mapping_dialog.py tests/integration/ui/test_qt_runtime_events.py -q -p no:cacheprovider` | passed | 変更前baseline、77 passed |
| `uv run pytest tests/unit/domain/test_settings.py tests/unit/config/test_codec.py -q -p no:cacheprovider` | failed as expected | red: `MouseSettings` に `invert_x` 引数・属性がなく4 failed、19 passed |
| `uv run pytest tests/unit/domain/test_settings.py tests/unit/config/test_codec.py -q -p no:cacheprovider` | passed | X/Y既定値、型制約、旧schema v1補完、明示Y反転保持、TOML往復、23 passed |
| `uv run pytest tests/unit/input/test_yaw_pitch_model.py tests/unit/input/test_publisher.py::test_default_mouse_vertical_direction_matches_ijkl -q -p no:cacheprovider` | failed as expected | red: `invert_x = true` でもyaw符号が変わらず1 failed、13 passed |
| `uv run pytest tests/unit/input/test_yaw_pitch_model.py tests/unit/input/test_publisher.py::test_default_mouse_vertical_direction_matches_ijkl -q -p no:cacheprovider` | passed | 水平反転、垂直反転、既定マウス上下とI/Kの方向一致、14 passed |
| `uv run pytest tests/unit/application/test_settings_editor.py -q -p no:cacheprovider` | failed as expected | red: `update_mouse()` が `invert_x` keywordを受け付けず2 failed、6 passed |
| `uv run pytest tests/unit/application/test_settings_editor.py -q -p no:cacheprovider` | passed | 水平反転を含むmouse draft更新とinput設定変更後の保持、8 passed |
| `uv run pytest tests/integration/ui/test_mapping_dialog.py::test_mapping_dialog_exposes_and_edits_mouse_gyro_settings -q -p no:cacheprovider` | failed as expected | red: `mouse_gyro_group` が存在せず1 failed |
| `uv run pytest tests/integration/ui/test_mapping_dialog.py -q -p no:cacheprovider` | passed | 現在値、範囲、全controlのdraft反映と感度spinbox共通化後の回帰、8 passed |
| `uv run pytest tests/unit/application/test_app.py::test_session_applies_saved_settings_to_the_live_input_publisher tests/integration/ui/test_qt_runtime_events.py::test_mapping_dialog_saves_mouse_gyro_settings_and_discards_cancelled_edits -q -p no:cacheprovider` | passed | 保存後のrepository、session、live Publisher反映とGUI取消、2 passed。既存経路が成立していたため独立したredなし |
| `uv run pytest tests/unit/test_documentation.py tests/unit/test_work_unit_records.py -q -p no:cacheprovider` | passed | 完了移動後の文書構造、3 passed |
| `uv run pytest tests/unit/domain/test_settings.py tests/unit/config/test_codec.py tests/unit/application/test_settings_editor.py tests/unit/input/test_yaw_pitch_model.py tests/unit/input/test_publisher.py tests/unit/application/test_app.py tests/integration/ui/test_mapping_dialog.py tests/integration/ui/test_qt_runtime_events.py -q -p no:cacheprovider` | passed | 変更境界の回帰、108 passed |
| `uv sync --dev` | passed | 77 packages resolved、74 packages checked |
| `uv lock --check` | passed | lock整合、77 packages resolved |
| `uv run ruff format --check .` | passed | 131 files already formatted |
| `uv run ruff check .` | passed | All checks passed |
| `uv run ty check --no-progress` | passed | 公開設定型とQt境界、All checks passed |
| `uv run pytest tests/unit -q -p no:cacheprovider` | passed | 全unit tree、245 passed |
| `uv run pytest tests/integration -q -p no:cacheprovider` | passed | 全integration tree、79 passed |
| `uv build` | passed | sdistとwheelを生成 |
| `git diff --check` | passed | whitespace errorなし。作業treeの改行変換警告のみ |
| `rg -n "T[O]DO\|T[B]D\|x[x]x\|前[回]\|今[回]\|一[旦]\|上[述]\|適[宜]\|必要に応じ[て]" spec/complete/unit_029/MOUSE_MOTION_RESAMPLER_EXTRACTION.md spec/wip/unit_030/UNIFIED_ROTATION_POSE_MODEL.md spec/complete/unit_031/MOUSE_GYRO_SETTINGS_GUI.md` | passed | 該当なし |

### 9.1 GUI描画確認

Qtのoffscreen描画で既定寸法720×640の `MappingDialog` を生成した。割り当て表は698×284、マウスジャイロ設定groupは698×189で、表、各control、保存・取消ボタンに重なりがないことを画像で確認した。検証環境にはQt用日本語フォントがなく文字は□表示だったため、文言の描画品質は未検証であり、control配置と寸法だけを確認済みとする。検証画像は確認後に削除した。

## 10. 先送り事項

- Unit 030の統一姿勢モデルは、本Unitで確定したX/Y反転設定をマウス回転意図の生成時に適用する。
- pitch上限の既定値変更は実機比較後の独立作業単位で扱う。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test Listを作成した
- [x] TDD Test Listを全項目更新した
- [x] 検証結果または未実行理由を記録した
- [x] package / releaseは変更対象外と確認した
- [x] public設定型、設定互換、利用者向け文言のgateを記録した
- [x] GUIから水平・垂直反転を保存・取消できることを確認した
- [x] `invert_y = false` の既定値を回帰試験で確認した
