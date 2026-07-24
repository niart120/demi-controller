# コントローラーGUIのマウス入力状態 仕様書

## 1. 概要

### 1.1 目的

マウス入力状態をツールバーから除去し、コントローラーGUI内で明確に示す。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user correction | ツールバー表示を削除し、コントローラーGUI内へ移す | conversation |

## 2. 対象範囲

- ツールバーのマウス入力状態表示を削除する。
- コントローラーGUIへ、`pointer_capture_active` に対応するON/OFF表示を描画する。
- SettingsのMouseタブとマウスジャイロ設定は維持する。

## 3. 対象外

- F5の入力切替動作、設定値、コントローラー入力評価の変更。

## 4. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 |
|---|---|---|
| 表示位置 | メイン画面 | ツールバーにマウス入力の状態表示がない |
| コントローラーGUI | pointer capture有効 | 緑の高コントラストなON表示 |
| コントローラーGUI | pointer capture無効 | 赤の高コントラストなOFF表示 |

## 5. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-skipped | Toolbar exposes no mouse-input status widget | regression | unit | ui | green: 2026-07-24 |
| refactor-skipped | Preview model and rendered controller GUI distinguish pointer capture ON/OFF | new | unit | ui | Windows GUI capture green: 2026-07-24 |

## 6. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/ui/toolbar.py` | modify | 状態表示を削除 |
| `src/demi/ui/controller_preview.py` | modify | コントローラーGUI内の状態表示 |
| `tests/unit/ui/` | modify | 振る舞い検証 |

## 7. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/unit/ui/test_toolbar.py tests/unit/ui/test_controller_preview.py -q -p no:cacheprovider --basetemp tmp/pytest-unit_043` | pass | 11 passed |
| `uv run pytest tests/unit -q -p no:cacheprovider --basetemp tmp/pytest-unit_043` | pass | 303 passed |
| `uv run pytest tests/integration -q -p no:cacheprovider --basetemp tmp/pytest-integration-unit_043` | pass | 131 passed |
| `uv run python .agents/skills/inspect-gui-states/scripts/capture_gui.py --scenario tmp/gui-audit/unit_042/scenario.py --output tmp/gui-audit/unit_043` | pass | Windows Qt描画でON/OFFを確認 |

## 8. 先送り事項

- none

## 9. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を更新した
- [x] 検証結果を記録した
