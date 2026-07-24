# miscボタン物理配置修正 仕様書

## 1. 概要

### 1.1 目的

コントローラープレビューの下段miscボタンを、左にCapture、右にHomeとなる物理配置へ修正する。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user feedback | HomeとCaptureの左右配置が実機と逆に見える | conversation |
| diagnosed layout | 下段左へHome、右へCaptureを割り当てている | `src/demi/ui/preview_layout.py` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| 利用者 / コントローラープレビュー | 既定または入力中 | Captureが中央左、Homeが中央右に表示される | 小円、浅いV字、押下対応を維持する |

## 2. 対象範囲

- HomeとCaptureの横方向の配置。
- 物理配置を固定する回帰試験。
- 通常表示と最小表示のWindows Qt通常描画。

## 3. 対象外

- PlusとMinusの配置。
- miscボタンの大きさと縦位置。
- 論理ボタン、入力割り当て、送信値。
- コントローラー外形とIMU配置。

## 4. 関連 docs

- `spec/initial/ui.md`
- `spec/complete/unit_048/CONTROLLER_COMPACT_LAYOUT.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| 下段misc配置 | 960x600、800x475のプレビュー領域 | Captureの中心がHomeの中心より左にある | Minus < Capture < Home < Plus |
| 押下表示 | HomeまたはCapture押下 | 物理位置と論理ボタンが一致して強調される | 描画IDとラベル対応は変更しない |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| todo | Capture appears to the left of Home while the misc controls keep a symmetric shallow V | regression | unit | 既存の逆向き期待値を修正する |
| todo | Default, mixed-input, and minimum states show C left of H | visual | integration | `inspect-gui-states` |

## 7. 設計メモ

- 診断では論理ボタンから描画IDへの変換とラベル対応は正しく、座標割り当てだけが逆だった。
- `home`と`capture`の相対x座標だけを交換する。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/ui/preview_layout.py` | modify | HomeとCaptureのx座標 |
| `tests/unit/ui/test_controller_preview.py` | modify | 下段miscの物理順序 |
| `spec/initial/ui.md` | modify | 左右配置契約 |

## 9. 検証

| command | result | notes |
|---|---|---|
| targeted pytest | not run | redから記録する |
| `inspect-gui-states` capture | not run | 修正後に3状態を確認する |

## 10. 先送り事項

- none

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test Listを更新した
- [ ] 検証結果または未実行理由を記録した
- [x] package / release / public APIは変更対象外であることを確認した
