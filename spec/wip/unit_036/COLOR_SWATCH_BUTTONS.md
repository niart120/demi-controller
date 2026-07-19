# 色見本ボタンによる配色設定 仕様書

## 1. 概要

### 1.1 目的

色設定の各値を、現在色で塗った無文字のbuttonとして表示する。利用者は色見本そのものを押して標準色選択を開き、画面上のcolor codeと`Change...`表記を読まずに対象色を確認・変更できる。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user proposal | 各設定色をbutton横の色見本として示す | 対話、2026-07-19 |
| user refinement | 色見本そのものをbuttonにして、color codeと`Change...`を廃止する | 対話、2026-07-19 |
| user constraint | buttonには文字を置かず、背景色とのcontrast問題を避ける | 対話、2026-07-19 |
| current implementation | fieldごとのbutton textにhex colorを表示し、標準`QColorDialog`を開く | `src/demi/ui/dialogs/colors.py` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| user | Colors dialogを開く | Body、Buttons、Left grip、Right gripの各行で現在色を直接見られる | 可視のhex textを置かない |
| mouse user | Bodyの色見本buttonを押す | Bodyの現在色を初期値として標準色選択を開く | row labelで対象を識別する |
| keyboard user | 色見本へTab移動しEnterまたはSpaceを押す | mouse clickと同じ色選択を開く | focus位置を色だけに依存させない |
| screen reader user | 色見本へfocusする | field名と現在のhex値を読み上げる | buttonのvisible textは空のまま |
| user | 白、黒、鮮やかな色を設定する | 色にかかわらずborderとfocus indicatorを判別できる | 色上に文字を重ねない |
| user | color pickerをcancelする | draft、preview、swatchを変更しない | dialog全体のcancel契約も維持する |

## 2. 対象範囲

- Body、Buttons、Left grip、Right gripの各行をlabelと色見本buttonで構成する。
- 色見本buttonの内部を現在の設定色で塗り、visible textを空にする。
- color code、`Change...`、`Choose...`などの可視文字をbutton内外へ併記しない。
- 色見本のclick、`Enter`、`Space`で既存の標準`QColorDialog`を開く。
- color pickerへ現在色を初期値として渡し、確定時だけ対象fieldのdraftとlive previewを更新する。
- buttonにfill colorと独立したborder、hover、pressed、focus indicatorを持たせる。
- accessible nameへfield名、accessible descriptionへ現在の`#RRGGBB`値と操作内容を設定する。
- tooltipにはfield名と現在値を含め、可視の常設code表示の代替とする。
- light / dark themeの双方で標準focus操作を失わないpalette / stylesheet境界を定める。
- dialogのSave / Cancel、再接続確認、draft rollback、profile保存の既存契約を維持する。
- unit_032後のfield labelとaccessibility文言は英語source textとし、日本語catalogへ追加する。
- `spec/initial/configuration.md`、`spec/initial/requirements.md`、`spec/initial/testing.md`、`spec/initial/ui.md`を更新する。

## 3. 対象外

- custom color wheel、eyedropper、gradient editor、alpha channel編集。
- visible hex editorと手入力validation。domainのhex validationは維持する。
- 色見本上の文字色contrast計算。visible textを置かないため不要とする。
- palette preset、recent colors、reset-to-default buttonの追加。
- 左右gripを同色に固定する設定やtheme import / export。
- Qt標準色選択dialogの独自再実装。

## 4. 関連 docs

- `spec/initial/configuration.md`
- `spec/initial/requirements.md`
- `spec/initial/testing.md`
- `spec/initial/ui.md`
- `spec/complete/unit_002/DOMAIN_AND_SETTINGS.md`
- `spec/complete/unit_016/QT_STANDARD_CONTROLS_AND_DIALOGS.md`
- `spec/complete/unit_032/UI_LOCALIZATION_FOUNDATION.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| 現在色を表示する | Colors dialog open | 各buttonのfillが対応fieldのdraft colorと一致する | button textは空文字 |
| 色選択を開く | swatch click / Enter / Space | 対象fieldと現在色を渡して標準pickerを開く | 他fieldを変更しない |
| 色を確定する | picker accepted、新しいvalid color | 対象swatch、draft、live previewを同じ色へ更新する | Save前は永続化しない |
| 色選択を中止する | picker rejected | swatch、draft、previewを変更しない | 無変更signalを発行しない |
| focusを示す | keyboard focus、任意のfill color | border外側またはshapeでfocus indicatorを表示する | fillとのcontrastだけに依存しない |
| 補助情報を公開する | tooltip / accessibility query | field名、現在の#RRGGBB、色変更操作を取得できる | hexは視覚上常設しない |
| dialog変更をcancelする | 複数色を変更後にCancel | 保存済み色とpreviewへ戻る | 現行draft rollbackを維持する |
| reconnectを確認する | 接続中にSave | 必要な確認を経て確定し、cancel時は保存しない | 現行接続契約を維持する |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-skipped | 4つの色fieldに対応するswatch buttonが現在色を保持し、visible textとvisible hex labelを持たない | new / regression | unit / integration | 2件green。既存refresh境界でswatchColor propertyと塗りを更新し追加の構造変更なし |
| refactor-skipped | 各swatchのclick、Enter、Spaceが正しいfieldと現在色でpickerを開く | new / regression | integration | 4 field × 3操作をgreen化。QPushButton標準activationを単一clicked接続で使用 |
| refactor-skipped | picker acceptedは対象swatch、draft、previewだけを更新し、他fieldを維持する | regression | unit / integration | 4 fieldをparameterizeしgreen。既存set_color境界を再利用 |
| refactor-skipped | picker rejectedはdraft、preview、swatch、dirty stateを変更しない | regression / edge | integration | 4 fieldをgreen化。colorSelectedだけを更新境界とする既存接続で無変更を確認 |
| refactor-done | accessible name / descriptionとtooltipからfield名、hex値、操作を取得できる | new | integration | refresh境界でfield名、hex、Choose a colorを一括更新 |
| refactor-done | 白、黒、theme背景と同色のfillでもfocus / hover / border用の独立state propertyが設定される | new / edge | unit / integration | palette mid / highlightによる独立枠とsemantic property、StrongFocusを検証 |
| todo | dialog Cancelは複数swatch変更をrollbackし、Saveと再接続確認は既存の永続化契約を維持する | regression | integration | connected / disconnectedを含める |
| todo | 英語と日本語でrow labelとaccessible textが切り替わり、hex値自体は変わらない | new / regression | integration | unit_032に依存する |
| todo | Windows通常描画で各swatch、keyboard focus、light / dark fillの識別が不自然でない | new | manual | `$inspect-gui-states`でPNGを確認する |

## 7. 設計メモ

色の識別はrow labelが担い、buttonは色と操作対象を兼ねる。buttonのvisible textを空にしても、accessible nameを空にしてはならない。tooltipとaccessible descriptionにhex値を残し、正確な値が必要な利用者とUI testの観測経路を確保する。

fill colorを含むstylesheetでbutton全体のborderやfocusを上書きすると、白やtheme背景色で操作部の輪郭が消える。色は既存dialog内の標準`QPushButton`のpropertyまたはpalette roleへ保持し、border / focusは共通styleで分ける。専用Widgetは追加しない。受入testは特定OS themeのpixel値を固定せず、focus stateと描画領域が存在することを検証する。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/ui/dialogs/colors.py` | modify | 標準buttonによる無文字swatch、picker起動、accessibility、focus style |
| `src/demi/application/settings_editor.py` | modify | draft更新とrollback契約の維持 |
| `tests/integration/ui/test_colors_dialog.py` | modify | click、keyboard、picker、save / cancel、accessibility |
| `tests/unit/application/test_settings_editor.py` | modify | field単位更新とrollback回帰 |
| `spec/initial/configuration.md` | modify | color値と保存契約 |
| `spec/initial/requirements.md` | modify | 色見本操作とaccessibility受入 |
| `spec/initial/testing.md` | modify | swatch、focus、実描画確認 |
| `spec/initial/ui.md` | modify | Colors dialogの行構成 |
| `spec/wip/unit_036/COLOR_SWATCH_BUTTONS.md` | new | 作業境界と検証記録 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/unit/test_documentation.py tests/unit/test_work_unit_records.py` | pass | 3 passed、仕様作成時の文書構造を確認 |
| `uv run pytest tests/unit/application/test_settings_editor.py` | not run | 実装前の仕様作成段階 |
| `uv run pytest tests/integration/ui/test_colors_dialog.py` | not run | Qt event、picker、focus実装後に実行する |
| 標準gate | not run | settings保存とGUI変更後に実行する |
| `$inspect-gui-states`による代表状態の画像評価 | not run | default、白、黒、keyboard focusを確認する |

## 10. 先送り事項

- reset-to-default、palette preset、recent colorsは利用場面と保存形式を別unitで定義する。
- visible hex editorは正確な手入力要望が確認されるまで追加しない。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test Listを作成した
- [x] 実装検証が未実行である理由を記録した
- [x] visible textをなくした場合のaccessibility経路を定義した
- [ ] swatchのmouse / keyboard操作をgreenにした
- [ ] Save / Cancel / reconnectの回帰をgreenにした
- [ ] `$inspect-gui-states`で代表画面を評価した
