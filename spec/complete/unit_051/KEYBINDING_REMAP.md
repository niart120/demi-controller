# キー割り当て既定値と再割当 仕様書

## 1. 概要

### 1.1 目的

組み込み Default profile をこの開発機で実際に使っているキー割り当てへ合わせ、設定画面からマウスボタンを再割り当てできるようにする。同一入力を複数 target へ残す選択は、利用者が対象と既存 target を確認して明示的に選んだ場合だけ許可する。診断ジャイロ Y 軸の負方向を復元し、一覧は target 分類順に統一する。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user request | 現在の設定を既定値にし、マウス再割当と意図的な重複を扱う | conversation |
| user follow-up | ジャイロ Y 負方向の復元と Default 全体の並び順見直し | conversation |
| local settings | 既定値にする 35 件の binding | `C:\\Users\\train\\AppData\\Local\\Project_Demi\\settings.toml` |
| diagnosed implementation | 表領域のマウス押下を待受候補から一律に除外している | `src/demi/ui/dialogs/mapping.py` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| 初回利用者 / 組み込みプロファイル | 設定ファイルがない | 開発機で確認した 35 件の binding から開始する | 保存済み設定は変更しない |
| 利用者 / 再割当待受 | 表の「変更」後にマウスボタンを押して離す | 押したボタンが対象行の source になる | 「変更」を押したクリック自体は候補にしない |
| 利用者 / 重複候補 | 他行で使用中の source を選ぶ | 既存を置換、両方を保持、取消から選べる | 取消は draft を変更しない |

## 2. 対象範囲

- Default profile の source をローカル設定の binding 配列へ合わせ、`I → GYRO:Y_NEGATIVE` を復元する。
- Default profile を Buttons、Left stick、Right stick、Diagnostics の target 分類順へ並べる。同じ target の複数 source は隣接させる。
- マウスとキーボードの再割当イベントを、待受開始時点と発生元 widget を考慮して処理する。
- 重複 source の保持を明示選択として UI から可能にする。
- 関連する初期仕様と回帰試験を更新する。

## 3. 対象外

- 既存のユーザー設定ファイルの自動書換え。
- `F5` の予約解除、ローカル操作との競合解消、診断 target の優先規則変更。
- マウス移動、ホイール、タッチ入力の再割当。

## 4. 関連 docs

- `spec/initial/configuration.md`
- `spec/initial/input.md`
- `spec/initial/ui.md`
- `spec/initial/testing.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| Default profile | 新規 `AppSettings.default()` | `I → GYRO:Y_NEGATIVE` を含む 36 件 | source と target の順序を固定する |
| Default 表示順 | 新規 `AppSettings.default()` | Buttons、Left stick、Right stick、Diagnostics の順。同じ target の複数 source は隣接する | 診断は X+、X-、Y-、Y+、Z+、Z-、neutral |
| マウス再割当 | 表の行が待受中、表領域で対応マウスボタンを押して離す | `MOUSE:...` を候補として処理する | release 後に確定して操作セルのクリックを優先する |
| 重複の保持 | 使用中 source を別 target に指定し「両方を保持」を選ぶ | 両行の source を保存前 draft に残す | 保存時の全体競合確認は維持する |
| 重複の置換・取消 | 同じ候補で既存を置換または取消する | 置換は既存行を未割当にし、取消は draft 不変 | 既存動作を維持する |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-skipped | 新規 Default profile がローカル設定と同じ 35 件の binding を順序どおりに持つ | regression | unit | binding 配列だけの変更で構造整理は不要 |
| refactor-skipped | 表領域で待受後に押したマウスボタンを source として確定し、反転、変更、削除の操作セルを優先する | regression | integration | release 後に処理を遅延し、checkbox 編集時は待受を解除するため追加の構造整理は不要 |
| refactor-skipped | 重複 source の確認で明示的な保持を選ぶと両 target を draft に残す | new | integration | 確認 button の分岐だけで完了 |
| refactor-skipped | Default profile は Y 負方向を含む 36 件で、target 分類順に表示される | regression | unit | binding 配列の順序だけを整理し、追加の構造変更は不要 |

## 7. 設計メモ

- キーボードは `QKeyEvent`、マウスは `QMouseEvent` として同じ application event filter へ届く。待受中の mouse press を記録し、release 後に `mouse_source_for_event()` の結果を確定することで、操作セルのクリックを Qt へ先に渡す。
- 重複確認は置換と保持を別 button にし、既存 target と変更先を同じ確認ダイアログで示す。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/domain/mapping.py` | modify | Default profile |
| `src/demi/ui/dialogs/mapping.py` | modify | マウス待受と重複確認 |
| `tests/unit/domain/test_mapping.py` | modify | Default profile 回帰 |
| `tests/unit/ui/test_mapping_model.py` | modify | 行数と末尾マウス表示 |
| `tests/integration/ui/test_mapping_dialog.py` | modify | マウス待受と重複保持 |
| `tests/integration/ui/test_localization.py` | modify | 中央マウス行の表示 |
| `spec/initial/configuration.md` | modify | 既定値と重複確認契約 |
| `spec/initial/input.md` | modify | 既定値と待受契約 |
| `spec/initial/ui.md` | modify | 重複保持の操作契約 |
| `spec/initial/testing.md` | modify | UI 回帰観点 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/unit/domain/test_mapping.py tests/unit/ui/test_mapping_model.py -q -p no:cacheprovider --basetemp tmp/pytest-unit051-default-red` | red | Default profile が旧 34 件のため 2 failed |
| `uv run pytest tests/integration/ui/test_mapping_dialog.py -q -p no:cacheprovider --basetemp tmp/pytest-unit051-remap-red` | red | table viewport のマウス待受と重複保持が未実装で 2 failed |
| `uv run pytest tests/unit/domain/test_mapping.py tests/unit/ui/test_mapping_model.py -q -p no:cacheprovider --basetemp tmp/pytest-unit051-default-green` | pass | 18 passed |
| `uv run pytest tests/integration/ui/test_mapping_dialog.py tests/integration/ui/test_localization.py -q -p no:cacheprovider --basetemp tmp/pytest-unit051-remap-green2` | pass | 20 passed |
| `uv run pytest tests/integration/ui/test_mapping_dialog.py::test_mapping_dialog_keeps_an_inverted_checkbox_click_as_a_table_edit -q -p no:cacheprovider --basetemp tmp/pytest-unit051-checkbox-red` | red | checkbox 編集後も待受が残り、期待した反転が適用されず 1 failed |
| `uv run pytest tests/integration/ui/test_mapping_dialog.py -q -p no:cacheprovider --basetemp tmp/pytest-unit051-checkbox-green` | pass | 19 passed |
| `uv sync --dev` | pass | 77 packages resolved、74 packages checked |
| `uv lock --check` | pass | lockfile変更なし |
| `uv run ruff format --check .` | pass | 146 files already formatted |
| `uv run ruff check .` | pass | All checks passed |
| `uv run ty check --no-progress` | pass | All checks passed |
| `uv run pytest tests/unit -q -p no:cacheprovider --basetemp tmp/pytest-unit051-all-unit-green` | pass | 327 passed |
| `uv run pytest tests/integration -q -p no:cacheprovider --basetemp tmp/pytest-unit051-final2-integration` | pass | 132 passed |
| `uv build` | pass | sdist と wheel を生成 |
| `git diff --check` | pass | whitespace errorなし |
| `docs-quality-review` | pass | 初期仕様と本仕様の契約、仮テキスト、未検証表示を確認 |

## 10. 先送り事項

- none

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を更新した
- [x] 検証結果または未実行理由を記録した
- [x] package / release / public API は変更対象外であることを確認した
