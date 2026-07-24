# コントローラーコンパクト配置 仕様書

## 1. 概要

### 1.1 目的

unit_047でショルダーボタンを収めた直線的な上面を、コントローラーとして自然に見える緩い曲線へ置き換える。L/R/ZL/ZRを同じショルダー列として扱い、側面からグリップまでの板状の印象も弱める。採用された曲線を維持しながら本体幅を約3:2まで縮め、主要操作群と小型操作部の間にある不要な横方向の空間を減らす。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user feedback | 箱状のツノを廃止した後も、直線的な上面と側面が不格好に見える | conversation |
| user decision | 緩い弧を描くB案を基準に試作し、実画像を見ながら調整する | conversation |
| user confirmation | 試作2のショルダー部分を採用する | conversation |
| user feedback | 本体を約3:2へ縮め、Minus/Plus/Home/Captureを小円化し、主要操作群の横間隔を狭める | conversation |
| user feedback | 3:2化後のD-pad位置を下段の左右バランスに合わせて直す | conversation |
| visual baseline | unit_047完了時の既定、複合入力、最小表示 | `tmp/gui-audit/unit_047-final/` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| 利用者 / コントローラー外形 | 既定または複合入力 | 上面中央が浅く下がる連続曲線と、グリップへつながる側面として読める | 深い中央凹みや独立したツノを作らない |
| 利用者 / ショルダー列 | L/R/ZL/ZRの通常・押下状態 | 4ボタンが同じ高さのショルダー列として外形内に収まる | L/Rだけをフェイス側へ下げない |
| 利用者 / 本体と主要操作群 | 既定または複合入力 | 約3:2の外形内で左スティック、misc、ABXYが近いまとまりとして読める | 操作部同士を重ねない |
| 利用者 / misc操作部 | Minus、Plus、Home、Captureの通常・押下状態 | ABXYより一回り小さい4つの円として浅いV字に並ぶ | 記号と押下表示を維持する |
| 利用者 / D-pad | 方向入力 | 左スティックの右下にあり、右スティックと下段の左右バランスが取れる | 十字形状と押下表示を維持する |
| 利用者 / 最小表示 | 800x520ウィンドウ | ラベル、外形、操作部が切れず、約3:2の全体比率を維持する | IMU領域を縮小しない |

## 2. 対象範囲

- フェイスプレート上面の連続曲線。
- 上側面からグリップへ向かう輪郭。
- L/R/ZL/ZRの同一行配置。
- 約3:2へ縮める本体とグリップの横幅。
- 左スティック、右スティック、ABXYの横方向配置。
- Minus、Plus、Home、Captureの小円化と浅いV字配置。
- D-padの横方向配置。
- 通常幅と最小幅のWindows Qt通常描画による反復調整。

## 3. 対象外

- 十字キーの形状と縦方向配置。
- ABXYの等角配置。
- マウス入力状態とIMU表示。
- 色、押下表現、入力処理。
- 公式製品の外形模倣とピクセル一致試験。

## 4. 関連 docs

- `spec/initial/ui.md`
- `spec/complete/unit_047/CONTROLLER_INDICATOR_PROPORTION_AND_IMU_AXES.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| ショルダー列 | 960x600、800x475のプレビュー領域 | L/R/ZL/ZRの上端と高さが一致し、全体がフェイスプレート内にある | 左はZL/L、右はR/ZRの順 |
| 上面曲線 | 同上 | 中央上端が肩側より浅く下がり、中央の凹みは本体高さの10%以内で内側へ戻る | 独立した角や矩形収納部を作らない |
| 上側面 | 同上 | 上側面が垂直線ではなく内側へ緩く入り、下側でグリップへ連続する | 操作部と交差しない |
| 外形比率 | 同上 | ショルダーとグリップを含む外接矩形が1.45:1から1.60:1に収まる | 高さを増やさず横幅を縮める |
| 主要操作群 | 同上 | 左スティックとmisc、miscとABXYの横方向の空白がそれぞれ描画領域幅の7%以内に収まる | 各群の外接矩形で比較する |
| misc形状 | 同上 | Minus、Plus、Home、Captureが同径の円になり、直径がABXYの80%以下になる | 最小ラベルサイズを維持する |
| misc配置 | 同上 | MinusとPlusを上側外寄り、HomeとCaptureを下側内寄りへ置く | 左右対称の浅いV字 |
| D-pad配置 | 同上 | D-pad中心を左スティック中心より描画領域幅の4%以上内側へ置き、D-padと右スティックの中点を画面中央から2%以内に収める | 下段の縦中心差も描画領域高さの2%以内 |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-skipped | All four shoulder buttons share one row and remain enclosed at normal and minimum sizes | regression | unit | L/Rを含む、追加整理は不要 |
| refactor-skipped | The upper outline uses a shallow center dip instead of a full-width flat edge | regression | unit | 深さ5.5%、追加整理は不要 |
| refactor-skipped | The upper side outline curves inward instead of continuing as a vertical slab edge | regression | unit | 絞り2.5〜3%、追加整理は不要 |
| refactor-skipped | The complete silhouette stays near 3:2 and all controls remain enclosed | regression | unit | 比率1.519、追加整理は不要 |
| refactor-skipped | Left stick, misc controls, and ABXY use compact horizontal spacing | regression | unit | 各空白7%以内、追加整理は不要 |
| refactor-skipped | Minus, Plus, Home, and Capture are equal circles smaller than ABXY | regression | unit | 直径80%以下、追加整理は不要 |
| refactor-skipped | Misc controls form a symmetric shallow V | regression | unit | 上外側にMinus/Plus、下内側にHome/Capture |
| refactor-skipped | The directional pad sits inward from the left stick and balances the right stick | regression | unit | 描画幅36%の位置、追加整理は不要 |
| refactor-skipped | Default, mixed-input, and minimum states visually read as one compact controller body | visual | integration | 3状態で確認、構造整理は対象外 |

## 7. 設計メモ

- 4つのショルダーボタンは同じ上端、同じ高さ、同じ角丸を使う。
- 上面は肩側から中央へ滑らかに下がり、中央で折れ線や深い谷を作らない。
- 上側面はわずかに内側へ入り、グリップの外側曲線と合わせて長方形感を弱める。
- 3:2化は本体を高くせず、本体、グリップ、操作部を左右から内側へ寄せる。
- misc操作部は2行2列の矩形をやめ、中央へ向かう浅いV字の小円にする。
- D-padは左スティックの真下ではなく右下へ置き、右スティックと下段の重心を揃える。
- 視覚調整は通常幅だけで決めず、最小表示も同じ反復で確認する。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/ui/controller_preview.py` | modify | フェイスプレート外形 |
| `src/demi/ui/preview_layout.py` | modify | 本体、グリップ、ショルダー、主要操作群、misc配置 |
| `tests/unit/ui/test_controller_preview.py` | modify | 曲線、内包、比率、misc形状と配置 |
| `spec/initial/ui.md` | modify | 採用した外形契約 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run python .agents/skills/inspect-gui-states/scripts/capture_gui.py --scenario tmp/gui-audit/controller-indicator-review-20260725-005724/scenario.py --output tmp/gui-audit/unit_048-baseline` | pass | 上面と上側面が長い直線になり、板状に見える基準状態を確認 |
| `uv run pytest tests/unit/ui/test_controller_preview.py::test_shoulder_row_sits_inside_a_shallow_curved_upper_shell -q -p no:cacheprovider --basetemp tmp/pytest-unit048-outline-red` | red | 中央上端と上側面が直線のため2 failed |
| `uv run pytest tests/unit/ui/test_controller_preview.py tests/unit/ui/test_preview_layout.py -q -p no:cacheprovider --basetemp tmp/pytest-unit048-outline-green-attempt1` | red | 新曲線は成立したが上端位置の既存契約で2 failed |
| `uv run pytest tests/unit/ui/test_controller_preview.py tests/unit/ui/test_preview_layout.py -q -p no:cacheprovider --basetemp tmp/pytest-unit048-outline-green-attempt2` | pass | 50 passed |
| `uv run python .agents/skills/inspect-gui-states/scripts/capture_gui.py --scenario tmp/gui-audit/controller-indicator-review-20260725-005724/scenario.py --output tmp/gui-audit/unit_048-curve-attempt1` | fail | 中央の谷と側面の絞りが深く、砂時計形に見えるため不採用 |
| `uv run pytest tests/unit/ui/test_controller_preview.py tests/unit/ui/test_preview_layout.py -q -p no:cacheprovider --basetemp tmp/pytest-unit048-outline-green-attempt3` | pass | 50 passed、浅くした曲線でも契約を維持 |
| `uv run python .agents/skills/inspect-gui-states/scripts/capture_gui.py --scenario tmp/gui-audit/controller-indicator-review-20260725-005724/scenario.py --output tmp/gui-audit/unit_048-curve-attempt2` | pass | 既定、複合入力、最小表示で緩い上面と側面の連続性を確認 |
| `uv run ruff format --check src/demi/ui/controller_preview.py src/demi/ui/preview_layout.py tests/unit/ui/test_controller_preview.py` | pass | 3 files already formatted |
| `uv run ruff check src/demi/ui/controller_preview.py src/demi/ui/preview_layout.py tests/unit/ui/test_controller_preview.py` | pass | lint errorなし |
| `uv run pytest tests/unit/ui/test_controller_preview.py tests/unit/ui/test_preview_layout.py -q -p no:cacheprovider --basetemp tmp/pytest-unit048-trial-gate-formatted` | pass | 50 passed |
| `git diff --check` | pass | whitespace errorなし |
| `uv run pytest tests/unit/ui/test_controller_preview.py::test_all_controls_stay_inside_a_three_to_two_silhouette_with_enclosed_shoulders -q -p no:cacheprovider --basetemp tmp/pytest-unit048-three-two-red` | red | 外形比率1.938のため2 failed |
| `uv run pytest tests/unit/ui/test_controller_preview.py tests/unit/ui/test_preview_layout.py -q -p no:cacheprovider --basetemp tmp/pytest-unit048-three-two-green-attempt1` | pass | 50 passed、通常幅と最小幅で外形比率1.519 |
| `uv run python .agents/skills/inspect-gui-states/scripts/capture_gui.py --scenario tmp/gui-audit/controller-indicator-review-20260725-005724/scenario.py --output tmp/gui-audit/unit_048-three-two-attempt1` | pass | 3:2外形と内側へ寄せた主要操作群を3状態で確認 |
| `uv run pytest tests/unit/ui/test_controller_preview.py::test_misc_controls_are_smaller_circles_in_a_symmetric_shallow_v -q -p no:cacheprovider --basetemp tmp/pytest-unit048-misc-red` | red | miscが57.6x36pxの矩形であるため1 failed |
| `uv run pytest tests/unit/ui/test_controller_preview.py tests/unit/ui/test_preview_layout.py -q -p no:cacheprovider --basetemp tmp/pytest-unit048-misc-green-attempt1` | pass | 51 passed、小円と浅いV字を確認 |
| `uv run python .agents/skills/inspect-gui-states/scripts/capture_gui.py --scenario tmp/gui-audit/controller-indicator-review-20260725-005724/scenario.py --output tmp/gui-audit/unit_048-compact-attempt2` | pass | 通常幅と最小幅でmisc記号、押下状態、操作群間隔を確認 |
| `uv run pytest tests/unit/ui/test_controller_preview.py::test_directional_pad_sits_inward_and_balances_the_right_stick -q -p no:cacheprovider --basetemp tmp/pytest-unit048-dpad-red` | red | D-pad中心が左スティック中心より9.6px外側にあるため1 failed |
| `uv run pytest tests/unit/ui/test_controller_preview.py tests/unit/ui/test_preview_layout.py -q -p no:cacheprovider --basetemp tmp/pytest-unit048-dpad-green-attempt1` | pass | 52 passed、D-padを描画幅36%へ移動 |
| `uv run python .agents/skills/inspect-gui-states/scripts/capture_gui.py --scenario tmp/gui-audit/controller-indicator-review-20260725-005724/scenario.py --output tmp/gui-audit/unit_048-dpad-attempt1` | pass | 通常幅と最小幅で左スティック右下と下段の左右バランスを確認 |
| `uv sync --dev` | pass | 77 packages resolved、74 packages checked |
| `uv lock --check` | pass | lock整合 |
| `uv run ruff format --check .` | pass | 148 files already formatted |
| `uv run ruff check .` | pass | lint errorなし |
| `uv run ty check --no-progress` | pass | 型エラーなし |
| `uv run pytest tests/unit -q -p no:cacheprovider --basetemp tmp/pytest-unit048-final-unit-gate` | pass | 329 passed |
| `$env:PYTHONUTF8='1'; uv run pytest tests/integration -q -p no:cacheprovider --basetemp tmp/pytest-unit048-final-integration-gate` | fail | 隔離環境のPyPI通信拒否によりpackage build 3件が失敗、その他129件は成功 |
| `$env:PYTHONUTF8='1'; uv run pytest tests/integration -q -p no:cacheprovider --basetemp tmp/pytest-unit048-final-integration-gate-network` | pass | 依存取得を許可して132 passed |
| `uv build` | pass | sdistとwheelを生成 |
| docs-quality-review residue scan | pass | 仮テキスト、会話依存語、未検証表現の残存なし |
| `git diff --check` | pass | whitespace errorなし |
| `uv run python .agents/skills/inspect-gui-states/scripts/capture_gui.py --scenario tmp/gui-audit/controller-indicator-review-20260725-005724/scenario.py --output tmp/gui-audit/unit_048-final` | pass | 既定、複合入力、最小表示で最終状態を確認 |

## 10. 先送り事項

- none

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test Listを更新した
- [x] 検証結果または未実行理由を記録した
- [x] package / release / public APIは変更対象外であることを確認した
