# 捕捉中の接続ショートカット 仕様書

## 1. 概要

### 1.1 目的

排他マウスによってツールバーへのクリックが抑止されている入力捕捉中でも、Ctrl+Enter から保存済み接続を開始できるようにする。これにより、`ACCEL:ZERO` などの診断入力を保持したまま接続初期フレームの挙動を検証できる。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user request | Ctrl+Enter で接続できる経路を、診断入力とは別の作業ブランチで追加する | 作業依頼 |
| reproduced behavior | Windows の排他マウス捕捉中は左クリックが低水準フックで抑止され、接続ボタンへ届かない | `src/demi/platform/windows_mouse_hook.py` |
| completed diagnostic input | 捕捉中0Gの最新フレームを接続初期加速度へ反映する | `spec/complete/unit_026/CONFIGURABLE_IMU_DIAGNOSTICS.md` |
| input priority | ローカル操作は捕捉中の profile binding より優先する | `spec/initial/input.md` |
| hardware verification | 入力捕捉中の Ctrl+Enter が実機の接続経路として動作した | 利用者報告（2026-07-17） |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| 利用者 | 保存済み接続が可能な状態で入力捕捉し、O を保持して Ctrl+Enter を押す | 捕捉と0Gフレームを維持したまま接続要求が1回発行される | 排他マウスは解除しない |
| Qt キー入力 | 主キーボードの Return またはテンキー Enter を Ctrl と同時に押す | どちらも同じ接続操作を実行する | Qt の2種類の Enter を区別して登録する |
| 設定読込 | `connection` ローカル操作がない既存 `demi.settings/v1` を読む | Ctrl+Return / Ctrl+Enter を既定値として補う | schema version は変更しない |

## 2. 対象範囲

- `CTRL+RETURN` と `CTRL+ENTER` を接続・切断のローカル操作として追加する。
- Qt の接続 `QAction` へ2つのショートカットを設定し、既存の application router を通して実行する。
- 入力捕捉中もショートカットを有効とし、捕捉状態と保持済み診断入力を変更しない。
- `LocalActions`、TOML codec、割り当て競合検査へ接続操作を追加する。
- 既存設定の `local_actions.connection` 欠落を既定値で補う。

## 3. 対象外

- 排他マウスのクリック抑止を弱めること。
- 接続、切断、ペアリング、接続初期0Gの runtime 処理を変更すること。
- Ctrl+Enter 以外の接続ショートカットを初期値へ追加すること。
- ローカル操作をGUIから編集する画面。
- ダイアログ表示中やフォーカス喪失中に接続操作を受け付けること。
- 実機での接続初期0G比較。

## 4. 関連 docs

- `spec/initial/input.md`
- `spec/initial/ui.md`
- `spec/initial/configuration.md`
- `spec/initial/requirements.md`
- `spec/initial/testing.md`
- `spec/complete/unit_023/WINDOWS_EXCLUSIVE_MOUSE.md`
- `spec/complete/unit_026/CONFIGURABLE_IMU_DIAGNOSTICS.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| 接続を要求する | `READY`、`CAPTURED`、Ctrl+Return または Ctrl+Enter | `ConnectSaved` を1回発行し、接続状態を `CONNECTING` にする | ツールバー接続操作と同じ経路 |
| 診断入力を維持する | `ACCEL:ZERO` を保持してショートカットを実行 | 捕捉を解除せず、最新フレームの0Gを維持する | 接続初期0Gの前提を保持 |
| busy中の重複を防ぐ | `CONNECTING` または `DISCONNECTING` でショートカットを押す | 接続・切断要求を追加しない | `QAction` の enabled state を利用 |
| 接続済みで切断する | `CONNECTED` でショートカットを押す | 既存の接続アクションと同じ切断処理を実行 | 状態依存actionの意味を維持 |
| ローカル操作競合を表示する | profile binding が `KEY:CTRL+RETURN` または `KEY:CTRL+ENTER` を使う | 割り当て競合として対象ローカル操作を表示 | controller入力との二重利用を警告 |
| 既存設定を読む | `local_actions.connection` がない現行schema | `CTRL+RETURN` と `CTRL+ENTER` を補完して読み込む | 明示保存後は項目を出力 |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-skipped | 既定設定は Ctrl+Return / Ctrl+Enter を接続ローカル操作として保存・復元し、旧設定の項目欠落を補完して profile binding との競合を報告する | new / regression | unit | red は5 failed、22 passed。green は27 passed。責務が既存設定境界に収まるため追加refactor不要 |
| refactor-skipped | 捕捉中に0Gを保持したまま Ctrl+Return または Ctrl+Enter を押すと、排他マウスを維持して保存済み接続を1回要求する | new / regression | integration | red は2 failed。green は2 passed、関連44 passed。既存actionへのshortcut配線だけで完結したため追加refactor不要 |
| refactor-skipped | 初期仕様は接続ショートカット、入力優先順位、既存設定補完、結合試験を説明する | docs | docs | 5文書を更新しdocs 3 passed。実機比較をnot runとして維持 |

## 7. 設計メモ

Qt は主キーボードの Enter を `Key_Return`、テンキー Enter を `Key_Enter` として区別する。利用者の「Ctrl+Enter」をキーボード配置に依存させないため、設定上は `CTRL+RETURN` と `CTRL+ENTER` の2つを登録する。

ショートカットは新しい接続処理を作らず、状態に応じて接続・切断を選ぶ既存の `connection_action` を起動する。これにより busy 中の無効化、adapter 未設定時の設定ダイアログ、接続済みの切断をツールバーと一致させる。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/domain/settings.py` | modify | 接続ローカル操作の既定値 |
| `src/demi/config/codec.py` | modify | TOML 保存・復元と項目欠落時の補完 |
| `src/demi/application/settings_editor.py` | modify | profile binding との競合検査 |
| `src/demi/ui/toolbar.py` | modify | 接続 `QAction` の複数shortcut設定 |
| `src/demi/ui/application.py` | modify | session設定からtoolbarへshortcutを渡す |
| `tests/unit/` | modify | 設定、codec、競合、toolbarの試験 |
| `tests/integration/ui/test_qt_runtime_events.py` | modify | 捕捉・0G・接続shortcutの結合試験 |
| `spec/initial/*.md` | modify | 入力、UI、設定、要件、試験の整合 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/unit/domain/test_settings.py tests/unit/config/test_codec.py tests/unit/application/test_settings_editor.py -q -p no:cacheprovider` | failed as expected | red: 接続ローカル操作が未定義のため5 failed、22 passed |
| `uv run pytest tests/unit/domain/test_settings.py tests/unit/config/test_codec.py tests/unit/application/test_settings_editor.py -q -p no:cacheprovider` | passed | green: 27 passed |
| `$env:QT_QPA_PLATFORM='offscreen'; uv run pytest tests/integration/ui/test_qt_runtime_events.py::test_connection_shortcut_preserves_captured_zero_g_until_connect -q -p no:cacheprovider` | failed as expected | red: Ctrl+Return / Ctrl+Enter のどちらも接続commandを発行せず2 failed |
| `$env:QT_QPA_PLATFORM='offscreen'; uv run pytest tests/integration/ui/test_qt_runtime_events.py::test_connection_shortcut_preserves_captured_zero_g_until_connect -q -p no:cacheprovider` | passed | green: 2 passed。捕捉、O保持、0G、排他マウスを維持 |
| `$env:QT_QPA_PLATFORM='offscreen'; uv run pytest tests/unit/domain/test_settings.py tests/unit/config/test_codec.py tests/unit/application/test_settings_editor.py tests/unit/ui/test_toolbar.py tests/integration/ui/test_toolbar_actions.py tests/integration/ui/test_qt_runtime_events.py -q -p no:cacheprovider` | passed | related regression: 44 passed |
| `uv sync --dev` | passed | 77 packages resolved、74 packages checked |
| `uv lock --check` | passed | 77 packages resolved |
| `uv run ruff format --check .` | passed | 129 files already formatted |
| `uv run ruff check .` | passed | All checks passed |
| `uv run ty check --no-progress` | passed | All checks passed |
| `uv run pytest tests/unit -q -p no:cacheprovider` | passed | 228 passed |
| `$env:QT_QPA_PLATFORM='offscreen'; $env:PYTHONUTF8='1'; uv run pytest tests/integration -q -p no:cacheprovider --basetemp .pytest-tmp-unit027` | failed (environment) | 75 passed、2 failed。sandboxのPyPI接続制限でisolated build backendを取得できなかった |
| `$env:QT_QPA_PLATFORM='offscreen'; $env:PYTHONUTF8='1'; uv run pytest tests/integration -q -p no:cacheprovider --basetemp .pytest-tmp-unit027-net` | passed | 通信許可と新規basetempで77 passed |
| `uv build` | passed | sdistとwheelを生成 |
| `uv run pytest tests/unit/test_documentation.py tests/unit/test_work_unit_records.py -q -p no:cacheprovider` | passed | 3 passed |
| docs-quality review | passed | 文書の役割、事実と未検証、仮テキスト、会話依存語を確認。該当なし |
| type-boundary review | passed | `tuple[str, ...]`、codec復元型、既存位置引数順を確認。新規 `Any`、ignore、castなし |
| docstring review | passed | package rootのexport変更なし。`LocalActions`の既存説明と追加fieldに矛盾なし |
| agentic self-review | passed | Intent Delta、non-goals、設定後方互換、Qt経路、capture / 0G維持、diff、gateを照合 |
| `git diff --check` | passed | whitespace errorなし |
| 実機での捕捉中 Ctrl+Enter 接続 | passed (user reported) | 2026-07-17。機材構成と実行ログは未提供 |
| 実機での接続初期0G比較 | not run | 本unitの対象外 |

## 10. 先送り事項

- 捕捉中の Ctrl+Enter 接続経路は実機で動作した。途中0Gと接続初期0Gの挙動差は結果未報告のため、原因判断を別作業単位へ先送りする。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を更新した
- [x] 検証結果または未実行理由を記録した
- [x] 公開型境界、package gate、利用者向け仕様の整合を確認した
