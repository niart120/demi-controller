# コントローラープレビュー再設計 仕様書

## 1. 概要

### 1.1 目的

描画後のコントローラープレビューを、入力状態を一目で把握できる配置へ再設計する。ボタンの重なりと描画漏れをなくし、ジャイロ・加速度を数値列ではなく方向と大きさを読み取れる図形として表示する。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user review | 描画後のボタンが重なり、ショルダーボタンなどが欠落している | 対話、2026-07-19 |
| user review | ジャイロ・加速度の数値表示だけでは状態を理解しにくい | 対話、2026-07-19 |
| GUI review | 絶対座標に依存した描画と省略表記により、サイズ変更時の可読性と入力同定が弱い | `src/demi/ui/controller_preview.py` |
| initial design | 接続前も全ボタン、stick、gyro、accel の入力確認を可能にする | `spec/initial/ui.md` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| user | default size で preview を見る | すべての操作部が重ならず、左右と前後の位置関係を判別できる | controller の実機写真を再現する必要はない |
| user | L / R / ZL / ZR を個別に押す | 対応する shoulder control だけが明確に強調される | 4入力を省略しない |
| user | D-pad の上・右などを入力する | 文字の先頭ではなく、対応方向の形状が強調される | 同時入力も区別する |
| user | gyro を正負各軸へ入力する | 軸、回転方向、大きさを弧または回転矢印で読み取れる | 絶対姿勢として表示しない |
| user | accel を傾ける | 中心から伸びる3軸vectorで方向と大きさを読み取れる | 重力から姿勢を断定しない |
| tester | minimum / default / large size を描画する | control bounds が canvas 内に収まり、相互に重ならない | pixel完全一致を受入条件にしない |

## 2. 対象範囲

- preview canvas 内の相対layout modelを導入し、Widget sizeから各control boundsを計算する。
- A / B / X / Y、L / R、ZL / ZR、Plus / Minus / HOME / Capture、D-pad 4方向、左右stick、左右stick clickを個別に描画する。
- shoulder controlを本体上端の専用領域に置き、face buttonやstatus表示と重ねない。
- D-padを方向ごとの形状で描画し、方向名の省略文字に依存しない。
- analog stickは中心、可動範囲、現在位置を表示し、stick clickは独立した押下状態として示す。
- gyroは signed 3-axis rotation、accelは signed 3-axis vectorとして図形化する。
- sensorの正規化範囲、clamp、dead zoneを表示model側で明示し、入力範囲外でもcanvasを破綻させない。
- 数値値は主表示から外し、tooltip、accessible description、診断用の補助表示から確認可能にする。
- pointer capture状態とkeyboard入力可能状態を別のstatusとして表示する。
- minimum size、default size、拡大時のbounds、重なり、label欠落をmodel testで確認する。
- Windows通常描画のPNGを取得し、可読性と情報階層を`$inspect-gui-states`で確認する。
- `spec/initial/ui.md`、`spec/initial/requirements.md`、`spec/initial/testing.md`を更新する。

## 3. 対象外

- 起動直後にcontroller frameが届くまでの空表示。短い待機後に描画される現状は変更しない。
- 実機controllerの写真、3D model、texture、animation engineの導入。
- gyro積分による絶対姿勢推定、accelだけを使った傾斜角推定、sensor fusion。
- calibration UI、sensor履歴graph、recording、export。
- pixel単位のgolden image test。構造testと代表画面の目視確認を使う。
- controller themeを利用者が編集する機能。

## 4. 関連 docs

- `spec/initial/input.md`
- `spec/initial/requirements.md`
- `spec/initial/testing.md`
- `spec/initial/ui.md`
- `spec/complete/unit_003/INPUT_PIPELINE.md`
- `spec/complete/unit_015/QT_INPUT_AND_CONTROLLER_PREVIEW.md`
- `spec/complete/unit_016/QT_STANDARD_CONTROLS_AND_DIALOGS.md`
- `spec/wip/unit_032/UI_LOCALIZATION_FOUNDATION.md`
- `spec/wip/unit_033/POINTER_CAPTURE_AND_KEYBOARD_ROUTING.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| layoutを計算する | supported sizeのresize | 全control boundsがcanvas内に収まり、意図しない交差がない | paint処理とgeometry計算を分離する |
| 全controlを表示する | neutral frame | 操作可能なbutton、stick、shoulderが定位置に見える | neutralでも存在を隠さない |
| digital inputを強調する | 個別または同時button press | 対応controlだけがpressed styleとなる | labelと位置の双方で同定できる |
| analog stickを表示する | x / y とstick click | knob位置が可動範囲内で移動し、clickは独立して強調される | 入力値はclampする |
| gyroを図形化する | signed x / y / z angular velocity | 軸ごとの弧と矢印方向、長さまたは濃さで符号と大きさを示す | controllerの絶対向きには変換しない |
| accelを図形化する | signed x / y / z acceleration | 共通原点から各軸vectorを描き、符号と大きさを示す | scaleの上限をlegendまたはtooltipで示す |
| statusを分離する | keyboard operational、pointer capture on / off | keyboardとmouse captureを別label / indicatorで表す | unit_033のstateを使用する |
| 補助値を公開する | sensor図形へhover / accessibility query | 軸名と現在値を取得できる | 常時表示の数値列は置かない |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-skipped | minimum、default、large sizeで全control boundsがcanvas内に収まり、許可していないcontrol同士が交差しない | new / regression | unit | 3件green。pure relative geometryへ分離済みで追加の構造変更なし |
| refactor-skipped | neutral frameにもA/B/X/Y、D-pad、L/R/ZL/ZR、Plus/Minus/HOME/Capture、両stickとclickがすべて含まれる | regression | unit | 6件green。layout正本のcontrol id集合をmodelへ渡すため追加の構造変更なし |
| refactor-skipped | 各digital inputと複数同時入力が対応controlのpressed stateだけを更新する | regression | unit | 3件green。LogicalButtonからcontrol IDへの単一変換で成立し追加の構造変更なし |
| refactor-skipped | analog stick値は可動範囲へclampされ、stick clickはaxis位置と独立して表示される | regression | unit | 9件green。pure clampと既存pressed ID変換で責務が明確なため追加の構造変更なし |
| refactor-skipped | gyroの正負3軸が互いに異なる回転方向としてmodel化され、値の大きさが表示量へ単調に反映される | new | unit | 4件green。signed axis共通modelへ分離済みで追加の構造変更なし |
| todo | accelの正負3軸がvector方向と長さへ変換され、上限を超える値でboundsを越えない | new / edge | unit | scale / clampを固定値として検証する |
| todo | pointer captureとkeyboard operational stateが独立した表示値としてpreviewへ渡る | new / regression | unit / integration | unit_033に依存する |
| todo | tooltipまたはaccessible descriptionからgyro / accelの軸名と数値を取得できる | new | integration | 図形だけに情報を閉じない |
| todo | Windows通常描画のneutral、全button代表、sensor正負、resize画面で重なりと不自然な余白がない | new | manual | `$inspect-gui-states`でPNGを比較する |

## 7. 設計メモ

現行の`QPainter` custom widgetは維持し、描画手段の置換ではなくgeometryの責務分離を行う。layout modelはcontrol idと矩形・中心点を返し、paint処理はその結果とframe stateだけを使う。これにより描画漏れと重なりを画像比較に頼らず検出できる。

gyroは角速度、accelは加速度として表示する。controllerの傾きを描く表現は直感的に見えても、積分やsensor fusionを行わない限り誤った絶対姿勢を示すため採用しない。主表示は方向と大きさに絞り、正確な値はtooltipとaccessibilityへ残す。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/ui/controller_preview.py` | modify | relative layout、全control、sensor図形、status表示 |
| `src/demi/ui/preview_layout.py` | new | sizeからcontrol boundsを作るpure model |
| `src/demi/ui/preview_sensor.py` | new | gyro / accelの表示modelとclamp |
| `src/demi/domain/controller.py` | modify | unit_033で分離したkeyboard / pointer状態のframe受け渡し |
| `tests/unit/ui/test_preview_layout.py` | new | bounds、交差、control inventory |
| `tests/unit/ui/test_preview_sensor.py` | new | signed axis、scale、clamp |
| `tests/unit/ui/test_controller_preview.py` | modify | frameから表示stateへの対応 |
| `tests/integration/ui/*` | modify | resize、tooltip、accessibility、state連携 |
| `spec/initial/requirements.md` | modify | 完全なcontrol表示とsensor可視化の受入条件 |
| `spec/initial/testing.md` | modify | geometry testと実描画確認 |
| `spec/initial/ui.md` | modify | preview layoutとsensor表現 |
| `spec/wip/unit_034/CONTROLLER_PREVIEW_VISUALIZATION.md` | new | 作業境界と検証記録 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/unit/test_documentation.py tests/unit/test_work_unit_records.py` | pass | 3 passed、仕様作成時の文書構造を確認 |
| `uv run pytest -p no:cacheprovider --basetemp tmp/pytest/unit034-layout tests/unit/ui/test_preview_layout.py -q` | pass | 3 passed。800x520、960x640、1440x900のboundsと交差を確認 |
| `uv run ruff check src/demi/ui/preview_layout.py tests/unit/ui/test_preview_layout.py` | pass | DomainValueErrorへ統一後、指摘なし |
| `uv run ty check --no-progress` | pass | 型エラーなし |
| `uv run pytest -p no:cacheprovider --basetemp tmp/pytest/unit034-inventory tests/unit/ui/test_controller_preview.py tests/unit/ui/test_preview_layout.py -q` | pass | 6 passed。neutral表示modelの全20 control IDを確認 |
| `uv run pytest -p no:cacheprovider --basetemp tmp/pytest/unit034-pressed tests/unit/ui/test_controller_preview.py -q` | pass | 3 passed。AとD-pad leftの同時入力が対応controlだけをpressedにすることを確認 |
| `uv run pytest -p no:cacheprovider --basetemp tmp/pytest/unit034-stick tests/unit/ui/test_preview_layout.py tests/unit/ui/test_controller_preview.py -q` | pass | 9 passed。stick軸clampとleft stick clickの独立pressed stateを確認 |
| `uv run pytest -p no:cacheprovider --basetemp tmp/pytest/unit034-gyro tests/unit/ui/test_preview_sensor.py -q` | pass | 4 passed。gyro正負3軸の方向、単調な表示量、上限clampを確認 |
| `uv run pytest tests/unit/ui/test_preview_layout.py tests/unit/ui/test_preview_sensor.py tests/unit/ui/test_controller_preview.py` | not run | 実装前の仕様作成段階 |
| `uv run pytest tests/integration/ui` | not run | resize、accessibility、state連携の実装後に実行する |
| 標準gate | not run | preview実装後に実行する |
| `$inspect-gui-states`による代表状態の画像評価 | not run | Windows通常描画で重なり、欠落、可読性を確認する |

## 10. 先送り事項

- sensor履歴graphとcalibrationは、現在値の図形表示が実機入力で妥当と確認できた後に別unitで扱う。
- controller themeとanimationは、状態同定に必要な情報を増やすものではないため対象外を維持する。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test Listを作成した
- [x] 実装検証が未実行である理由を記録した
- [x] 数値を隠す範囲とaccessibility経路を定義した
- [ ] 全control inventoryとgeometry testをgreenにした
- [ ] gyro / accel表示を実機入力で確認した
- [ ] `$inspect-gui-states`で代表画面を評価した
