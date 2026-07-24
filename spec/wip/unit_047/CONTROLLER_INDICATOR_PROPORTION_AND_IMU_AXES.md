# コントローラーインジケータ比率とIMU軸表示の再調整 仕様書

## 1. 概要

### 1.1 目的

コントローラー上部の余白、ショルダーボタンの外付け感、ABXYの横長配置、外形比率、状態ラベル、IMU表示面積、加速度軸投影を見直す。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user request | ショルダーボタンを外形内へ収め、ABXYを等角配置にし、外形を約2:1へ直す | conversation |
| user request | マウス入力ラベルからF5を除去し、IMU領域を拡大する | conversation |
| user reference | Switch IMU軸定義と右Joy-Conの軸画像に沿って加速度投影を直す | `https://github.com/dekuNukem/Nintendo_Switch_Reverse_Engineering/blob/master/imu_sensor_notes.md#axes-definition` |
| visual baseline | unit_046完了時の既定、複合入力、800x520表示 | `tmp/gui-audit/unit_046-final-actual-minimum/` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| 利用者 / コントローラー外形 | 通常表示 | ショルダーボタンが連続した上部外形内にあり、全体を約2:1のシルエットとして読める | 上部余白を減らす |
| 利用者 / ABXY | 通常または押下 | 上下と左右の中心間隔が等しい菱形として読める | 円形と押下表示を維持する |
| 利用者 / マウス入力状態 | ONまたはOFF | 状態名と有効・無効だけを表示し、F5を表示しない | F5操作自体は変更しない |
| 利用者 / IMU表示 | 複数軸入力 | ジャイロ棒と加速度ベクトルが現在より大きい領域で読める | tooltipの数値契約を維持する |
| 利用者 / 加速度軸 | X、Y、Z単独入力 | +Xは右上、+Yは右下、+Zは下へ伸びる | 右Joy-Con軸画像の画面投影に合わせる |

## 2. 対象範囲

- ショルダーボタンを内包する上部外形と縦方向配置。
- コントローラー外形の描画上の幅・高さ比。
- ABXY中心間隔。
- マウス入力状態バッジの可視文言。
- ジャイロ、加速度の描画領域。
- 加速度3軸の2次元投影。
- 各修正後のWindows Qt通常描画による画像監査。

## 3. 対象外

- F5による入力切替動作。
- IMU値の生成、校正、Bluetooth送信、座標値そのもの。
- ジャイロ軸の意味と棒の正負方向。
- 公式画像やロゴの製品組み込み。
- ピクセル完全一致の画像試験。

## 4. 関連 docs

- `spec/initial/ui.md`
- `spec/initial/input.md`
- `spec/complete/unit_046/CONTROLLER_INDICATOR_AUDIT_FIXES.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| 上部外形 | ニュートラル、肩ボタン押下 | 幅広いフェイスプレート上段が各ボタン全体を含む | 外形上端を描画領域上側へ寄せる |
| 外形比率 | 960x640、800x520 | ショルダー収納部とグリップを含む外接矩形が1.9:1から2.1:1に収まる | Qt論理座標で検査する |
| ABXY配置 | 通常表示 | X-Bの上下距離とY-Aの左右距離が等しい | 各円の中心で比較する |
| 状態文言 | ON、OFF | `Mouse input: On/Off` または対応する日本語だけを描く | `(F5)`を含めない |
| IMU面積 | 800x520 | ジャイロと加速度がそれぞれ90px以上の高さを持つ | 状態バッジとの非交差を維持する |
| 加速度投影 | 軸ごとの正入力 | +X右上、+Y右下、+Z下 | 指定資料の右Joy-Con画像を根拠にする |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-done | Shoulder buttons are enclosed by a continuous upper faceplate and the complete silhouette stays near a 2:1 ratio | regression | unit | 箱状ツノを廃止し、上段を連続した外形へ変更 |
| refactor-skipped | ABXY centers use equal horizontal and vertical spacing | regression | unit | 縦横48px、追加整理は不要 |
| todo | Mouse input status text omits the F5 shortcut in English and Japanese | regression | unit / integration | F5動作は対象外 |
| todo | Gyro and acceleration regions have at least 90px height in the minimum window | regression | unit | 状態領域との非交差 |
| todo | Positive acceleration axes project to +X upper-right, +Y lower-right, and +Z downward | regression | unit | 右Joy-Con軸画像 |

## 7. 設計メモ

- ショルダーボタンは幅広いフェイスプレート上段へ内包し、外形の外へ浮かせない。
- 描画領域の8:5比は維持し、コントローラー図形の外接矩形だけを約2:1へ調整する。
- 外形を上へ寄せて生じる下部余白をIMUへ配分する。
- 加速度投影は3次元軸を画面へ模式投影するものであり、センサー値の座標変換は行わない。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/ui/preview_layout.py` | modify | 外形、操作部、状態、IMU領域 |
| `src/demi/ui/controller_preview.py` | modify | 上部外形、状態文言、加速度投影 |
| `tests/unit/ui/test_preview_layout.py` | modify | 最小領域と配置 |
| `tests/unit/ui/test_controller_preview.py` | modify | 外形比率、ABXY、文言、軸投影 |
| `tests/integration/package/test_translation_catalog.py` | modify | 必要な場合のみ翻訳実行時検査 |
| `spec/initial/ui.md` | modify | 修正後のUI契約 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/unit/ui/test_controller_preview.py -q -p no:cacheprovider --basetemp tmp/pytest-unit047-silhouette-red` | red | ショルダーがフェイスプレート外にあることを確認 |
| `uv run pytest tests/unit/ui/test_controller_preview.py tests/unit/ui/test_preview_layout.py -q -p no:cacheprovider --basetemp tmp/pytest-unit047-silhouette-green-attempt2` | pass | 45 passed |
| `uv run python .agents/skills/inspect-gui-states/scripts/capture_gui.py --scenario tmp/gui-audit/controller-indicator-review-20260725-005724/scenario.py --output tmp/gui-audit/unit_047-silhouette-green` | fail | 左右の箱状ツノと上部操作部の空白が残るため不採用 |
| `uv run pytest tests/unit/ui/test_controller_preview.py tests/unit/ui/test_preview_layout.py -q -p no:cacheprovider --basetemp tmp/pytest-unit047-silhouette-green-attempt3` | pass | 45 passed、連続した上部外形で全操作部を内包 |
| `uv run pytest tests/unit/ui/test_controller_preview.py tests/unit/ui/test_preview_layout.py -q -p no:cacheprovider --basetemp tmp/pytest-unit047-abxy-red` | red | ABXY中心間隔が横62.4px、縦48pxで不一致 |
| `uv run pytest tests/unit/ui/test_controller_preview.py tests/unit/ui/test_preview_layout.py -q -p no:cacheprovider --basetemp tmp/pytest-unit047-abxy-green` | pass | 45 passed、ABXY中心間隔は縦横48px |
| `uv run python .agents/skills/inspect-gui-states/scripts/capture_gui.py --scenario tmp/gui-audit/controller-indicator-review-20260725-005724/scenario.py --output tmp/gui-audit/unit_047-abxy-green` | pass | 通常幅と最小幅で箱状ツノの解消、上部余白の削減、ABXY等間隔を確認 |
| standard gate | not run | 完了前に実行する |

## 10. 先送り事項

- none

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [ ] TDD Test Listを更新した
- [ ] 検証結果または未実行理由を記録した
- [x] package / release / public APIは変更対象外であることを確認した
