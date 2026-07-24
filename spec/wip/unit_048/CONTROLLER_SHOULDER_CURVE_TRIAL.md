# コントローラー上面曲線の試作 仕様書

## 1. 概要

### 1.1 目的

unit_047でショルダーボタンを収めた直線的な上面を、コントローラーとして自然に見える緩い曲線へ置き換える。L/R/ZL/ZRを同じショルダー列として扱い、側面からグリップまでの板状の印象も弱める。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user feedback | 箱状のツノを廃止した後も、直線的な上面と側面が不格好に見える | conversation |
| user decision | 緩い弧を描くB案を基準に試作し、実画像を見ながら調整する | conversation |
| visual baseline | unit_047完了時の既定、複合入力、最小表示 | `tmp/gui-audit/unit_047-final/` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| 利用者 / コントローラー外形 | 既定または複合入力 | 上面中央が浅く下がる連続曲線と、グリップへつながる側面として読める | 深い中央凹みや独立したツノを作らない |
| 利用者 / ショルダー列 | L/R/ZL/ZRの通常・押下状態 | 4ボタンが同じ高さのショルダー列として外形内に収まる | L/Rだけをフェイス側へ下げない |
| 利用者 / 最小表示 | 800x520ウィンドウ | ラベル、外形、操作部が切れず、約2:1の全体比率を維持する | IMU領域を縮小しない |

## 2. 対象範囲

- フェイスプレート上面の連続曲線。
- 上側面からグリップへ向かう輪郭。
- L/R/ZL/ZRの同一行配置。
- 通常幅と最小幅のWindows Qt通常描画による反復調整。

## 3. 対象外

- ABXY、スティック、十字キーの相対配置。
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
| 外形比率 | 同上 | ショルダーとグリップを含む外接矩形が1.9:1から2.1:1に収まる | unit_047の契約を維持する |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-skipped | All four shoulder buttons share one row and remain enclosed at normal and minimum sizes | regression | unit | L/Rを含む、追加整理は不要 |
| refactor-done | The upper outline uses a shallow center dip instead of a full-width flat edge | regression | unit | 深さ5.5%へ調整 |
| refactor-done | The upper side outline curves inward instead of continuing as a vertical slab edge | regression | unit | 試作1の6〜7%から2.5〜3%へ縮小 |
| refactor-skipped | The complete silhouette remains near 2:1 and all controls remain enclosed | regression | unit | unit_047契約を維持、追加整理は不要 |
| green | Default, mixed-input, and minimum states visually read as one controller body | visual | integration | 試作2を提示案として採用、ユーザ確認待ち |

## 7. 設計メモ

- 4つのショルダーボタンは同じ上端、同じ高さ、同じ角丸を使う。
- 上面は肩側から中央へ滑らかに下がり、中央で折れ線や深い谷を作らない。
- 上側面はわずかに内側へ入り、グリップの外側曲線と合わせて長方形感を弱める。
- 視覚調整は通常幅だけで決めず、最小表示も同じ反復で確認する。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/ui/controller_preview.py` | modify | フェイスプレート外形 |
| `src/demi/ui/preview_layout.py` | modify | 必要な場合のみショルダー列の縦位置 |
| `tests/unit/ui/test_controller_preview.py` | modify | 曲線、内包、比率 |
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
| standard gate | not run | 完了前に実行する |

## 10. 先送り事項

- 試作2のユーザ確認後、採用する場合は `spec/initial/ui.md` へ曲線契約を反映してunit_048を完了する。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test Listを更新した
- [x] 検証結果または未実行理由を記録した
- [x] package / release / public APIは変更対象外であることを確認した
