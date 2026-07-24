# 入力割り当てとマウス入力切替 仕様書

## 1. 概要

### 1.1 目的

設定画面の小さな表示不整合を直し、IMU診断入力を現在の用途に合わせ、マウス入力の切替をF5へ統一する。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user request | Bindings、Colors、IMU診断入力、マウス入力切替の改修 | conversation |
| 初期入力設計 | 入力取得、診断入力、既定プロファイル | `spec/initial/input.md` |
| 初期UI設計 | 設定ダイアログとキーボード操作 | `spec/initial/ui.md` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| 利用者 / Bindings | 表を閲覧する | 削除列に見出しがなく、各行のゴミ箱操作は維持される | 表外の削除操作を作らない |
| 利用者 / IMU | U、O、Pを保持する | X正回転、Y負回転、物理ニュートラルIMUを出力する | `ACCEL:ZERO` は存在しない |
| 利用者 / メイン画面 | F5を押す | マウス入力が捕捉と解除で交互に切り替わり、状態が判別できる | Start mouseボタンとF4解除を残さない |

## 2. 対象範囲

- Remove列の見出しを空文字列にする。
- Colorsの色ボタンをフォームの余剰幅へ伸ばさない。
- `GYRO:X_POSITIVE => KEY:U`、`GYRO:X_NEGATIVE => KEY:O`、`IMU:NEUTRAL => KEY:P` を既定プロファイルへ追加する。
- `ACCEL:ZERO` targetとゼロG上書きを削除し、`IMU:NEUTRAL` がgyro `(0, 0, 0)` とaccel `(0, 0, 1)` を出力する。
- Start mouseツールバーactionとF4解除を削除し、F5で捕捉を切り替える。
- メイン画面でマウス入力の有効・無効を高コントラストな専用状態表示で示す。

## 3. 対象外

- F5以外のグローバルキーボードフック。
- マウスジャイロ設定値、Bluetooth接続、コントローラー描画の変更。
- 既存のユーザー設定ファイルを自動移行する処理。

## 4. 関連 docs

- `spec/initial/input.md`
- `spec/initial/ui.md`
- `spec/initial/testing.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| IMU既定割当 | Default profile | X正=U、X負=O、ニュートラル=P | ACCEL:ZEROなし |
| IMUニュートラル | Pを保持して捕捉中 | gyroが全軸0、accelがZ=1 | 他の診断入力より優先する |
| F5切替 | 設定ダイアログなし | 捕捉状態を反転する | 割り当て候補ではない |
| マウス状態表示 | IDLE/CAPTURED | 色と文言で有効状態を区別できる | ツールバーの開始ボタンを用いない |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-skipped | Default profile exposes X-positive=U, X-negative=O, and IMU-neutral=P without ACCEL:ZERO | regression | unit | mapping | red: enum absent; green: 2026-07-24 |
| refactor-skipped | Held IMU-neutral produces physical neutral IMU and overrides active diagnostic rotation | new | unit | input | green: 2026-07-24 |
| todo | Bindings table has a blank remove header and colors swatches keep their size hint at wider dialog widths | regression | integration | ui |
| todo | F5 toggles pointer capture, F4 has no capture side effect, and no Start mouse action exists | regression | integration | ui |
| todo | Main window visibly distinguishes enabled and disabled mouse input | new | integration | ui | visual review follows |

## 7. 設計メモ

- 変更はすべて振る舞い変更であり、F4・ACCEL:ZEROとの後方互換は保持しない。
- IMUニュートラルは姿勢をリセットせず、当該評価フレームだけを物理ニュートラルへ上書きする。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/domain/mapping.py` | modify | 診断targetと既定割当 |
| `src/demi/input/mapper.py` | modify | IMUニュートラルの評価 |
| `src/demi/input/qt_adapter.py` | modify | F5切替 |
| `src/demi/ui/toolbar.py` | modify | 開始ボタン削除と状態表示 |
| `src/demi/ui/dialogs/mapping.py` | modify | Remove見出しとキー待受 |
| `src/demi/ui/dialogs/colors.py` | modify | 色ボタン幅 |
| `spec/initial/input.md` | modify | 入力仕様の正本更新 |
| `spec/initial/ui.md` | modify | UI仕様の正本更新 |
| `spec/initial/testing.md` | modify | テスト観点更新 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/unit/domain/test_mapping.py tests/unit/input/test_publisher.py -q -p no:cacheprovider` | pass | 40 passed |
| `uv run ruff check src/demi/domain/mapping.py src/demi/input/mapper.py src/demi/input/publisher.py tests/unit/domain/test_mapping.py tests/unit/input/test_publisher.py` | pass | targeted static check |
| GUI state capture | not run | 実装後にWindows描画で確認 |
| standard gate | not run | 完了前に実行 |

## 10. 先送り事項

- none

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を更新した
- [ ] 検証結果または未実行理由を記録した
- [ ] package / release / public API に触れる場合の gate を記録した
