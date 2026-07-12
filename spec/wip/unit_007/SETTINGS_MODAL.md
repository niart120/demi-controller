# 設定 modal 仕様書

## 1. 概要

### 1.1 目的

Unit 002 の immutable settings / TOML repository と Unit 003 の binding model を、mapping、connection、colors の設定 modal へ接続する。編集中は draft として扱い、競合警告と検証を通過した値だけを atomic save する。modal を開く瞬間に入力捕捉を停止し、ControllerView を neutral 状態へ戻す。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| roadmap | Unit 007 の成果と完了条件 | `spec/initial/roadmap.md` |
| UI design | mapping、connection、colors modal、dialog 管理 | `spec/initial/ui.md` |
| lifecycle | modal 開始時の neutral、capture state、色再接続 | `spec/initial/lifecycle.md` |
| requirements | FR-010〜FR-014、NFR-005、NFR-006 | `spec/initial/requirements.md` |
| testing | mapping conflict、settings I/O、state transition | `spec/initial/testing.md` |
| completed settings | immutable domain、TOML codec、atomic repository | `spec/complete/unit_002/DOMAIN_AND_SETTINGS.md` |
| completed UI | toolbar、AppState、CaptureCoordinator | `spec/complete/unit_004/UI_AND_PYGLET.md` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| user | IDLE / CAPTURED で設定を開く | modal が1つだけ開き、capture を停止して neutral frame を出す | 接続 I/O は modal open で実行しない |
| mapping editor | 次の key / mouse source、target、inverted | draft binding が更新され、重複と local action 競合を警告する | `F12` は予約済みで変更不可 |
| connection editor | adapter、bond slot、timeout、reconnect、diagnostic level | validated `ConnectionSettings` draft を保持する | controller type は Pro Controller 固定 |
| color editor | 4個の `#RRGGBB` | preview 用 draft を即時更新する | 接続中の保存は reconnect required を返す |
| user | 保存 / 取消 / 標準へ戻す | 保存は atomic repository、取消は元 settings 維持、reset は default profile を復元する | 不正 draft は保存しない |
| startup | repository が RECOVERED を返す | backup path を含む安全な通知モデルを作る | corrupt settings を上書きしない |

## 2. 対象範囲

- `SettingsEditor` に immutable `AppSettings` draft の binding / connection / color 編集を実装する。
- duplicate source、同一 source の複数 target、local action との競合を `BindingConflict` として返す。
- `KEY:F12` と release-capture action を予約操作として保護する。
- `DialogKind` / `DialogManager` で modal の同時 open を1つに制限する。
- `SettingsModalController` が CaptureCoordinator、SettingsRepository、SettingsEditor を束ねる。
- 保存成功時の `reconnect_required` を colors 差分と connected 状態から返す。
- `SettingsLoadResult.RECOVERED` と backup path を短い通知文へ変換する。
- display-free な application/UI model と fake window/publisher/repository で試験する。

## 3. 対象外

- pyglet の文字入力部品、スクロール領域、color picker の実描画。
- Bluetooth 接続、pairing、runtime command の実行。再接続は結果 flag を後続 coordinator が扱う。
- Unit 008 の実機受入、Unit 009 の OS 別 UI、Unit 010 の standalone packaging。
- 診断ログの収集・表示、swbt status / snapshot の変換。
- プロファイルの import/export と複数 controller type。0.1.0 は既存 profile / Pro Controller のみ。

## 4. 関連 docs

- `spec/initial/roadmap.md`
- `spec/initial/ui.md`
- `spec/initial/lifecycle.md`
- `spec/initial/requirements.md`
- `spec/initial/testing.md`
- `spec/complete/unit_002/DOMAIN_AND_SETTINGS.md`
- `spec/complete/unit_004/UI_AND_PYGLET.md`
- `AGENTS.md`
- `SKILLS.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| modal を開く | dialog none、IDLE または CAPTURED | kind を設定し、configuration state へ移り、capture-inactive neutral を publish する | 同時 open は false |
| modal を閉じる | open modal、cancel / save 完了 | kind none、AppState IDLE、draft 破棄または保存済みへ確定する | 自動 capture 再開なし |
| binding を変更する | index、source、target、amount、inverted | active profile の draft だけを置換する | source は domain validation を通す |
| binding conflict を調べる | draft bindings、local actions | duplicate source と local action collision を deterministic に返す | 同一 target への異なる source は許可 |
| F12 を扱う | `KEY:F12` の assign / local action変更 | `DomainValueError` とし、予約操作を維持する | mapping へ渡さない |
| standard reset | mapping modal の draft | active profile を `default_profile()` へ戻す | connection / colors は保持 |
| connection を編集する | adapter id、bond slot、timeout、flags | `ConnectionSettings` の domain validation を通した draft | invalid slot / timeout は保存不可 |
| color を編集する | field、`#RRGGBB` | 4色の preview draft を即時更新する | 色文字列は大文字正規化 |
| save を確定する | valid draft、connected flag | repository.save、modal close、保存結果を返す | colors 差分かつ connected なら reconnect required |
| corrupt recovery を通知する | `SettingsLoadResult.RECOVERED` | backup filename を含む通知を返す | backup がない場合も復旧結果を隠さない |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-done | SettingsEditor が immutable draft の binding / connection / color 編集と F12 保護を扱う | new / edge | unit | 2 tests green。default reset、inverted、domain validation を確認 |
| refactor-done | duplicate source と local action conflict を警告し、同一 target の複数 source を許可する | new / edge | unit | 1 test green。conflict order を固定 |
| refactor-done | DialogKind / DialogManager が modal を1つだけ開き、タイトルと状態を返す | new / regression | unit | 2 tests green。mapping、connection、colors、pairing confirmation を確認 |
| refactor-done | modal open / cancel が capture を neutralize し、configuration state と IDLE を遷移する | new / integration | integration | 1 test green。FakeWindow、FakePublisher、CaptureCoordinator で確認 |
| refactor-done | SettingsModalController が save / cancel / reset と color reconnect decision を束ねる | new / integration | integration | 2 tests green。repository save failure 時の modal / draft 保持を含む |
| refactor-done | RECOVERED / backup path が安全な復旧通知へ変換される | new / edge | integration | 2 tests green。backup 有無、corrupt file 内容や秘密値を通知へ入れない |
| refactor-done | settings modal の display-free model、全 gate、package smoke が通る | characterization | package | 2 tests green。unit、integration、build、wheel contents を確認 |

## 7. 設計メモ

- `SettingsEditor` は `AppSettings` を直接 mutate せず、`dataclasses.replace()` で新しい snapshot を作る。
- conflict は source の出現位置で並べる。duplicate source は `binding_indices` を2件以上、local action collision は該当 action を返す。競合は警告であり、F12 以外はユーザーが確認して保存できる。
- `CaptureCoordinator.open_configuration()` は CAPTURED なら `CONFIGURING` への neutral transition、IDLE なら capture-inactive frame を publish して state を変える。close 後は IDLE へ戻し、自動 capture はしない。
- `SettingsModalController.save()` は repository.save が成功するまで modal を閉じない。保存失敗は `SettingsPersistenceError` を呼び出し側へ返し、draft を保持する。
- `SettingsLoadResult.RECOVERED` の通知は backup file name だけを表示し、TOML 本文・bond・adapter metadata を含めない。
- pyglet の実部品は後続の dialog renderer が `DialogModel` と `SettingsEditor` を読む。Unit 007 の検証対象はその表示に必要な状態と操作契約である。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/application/coordinator.py` | modify | configuration state transition、neutral |
| `src/demi/application/dialogs.py` | new | DialogKind、DialogManager、DialogModel |
| `src/demi/application/settings_editor.py` | new | immutable settings draft、binding conflict、reset |
| `src/demi/application/settings_modal.py` | new | editor / repository / capture orchestration |
| `src/demi/ui/dialogs.py` | new | display-free modal presentation model |
| `tests/unit/application/test_settings_editor.py` | new | draft、conflict、F12、reset |
| `tests/unit/application/test_dialogs.py` | new | modal exclusivity |
| `tests/integration/ui/test_settings_modal.py` | new | neutral、save/cancel、reconnect decision、recovery notice |
| `spec/complete/unit_007/SETTINGS_MODAL.md` | new / modify | TDD 状態、検証、完了記録 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/unit/application/test_settings_editor.py` | not run | implementation 後に実行する |
| `uv run pytest tests/unit/application/test_settings_editor.py -q` | passed | 2 passed。draft 編集、default reset、F12 予約保護を確認 |
| `uv run pytest tests/unit/application/test_settings_editor.py -q` | passed | 3 passed。duplicate source、local action collision、同一 target の複数 source を確認 |
| `uv run pytest tests/unit/application/test_dialogs.py -q` | passed | 2 passed。modal 排他、title、idempotent close を確認 |
| `uv run pytest tests/unit/application/test_coordinator.py -q` | passed | 3 passed。configuration open の neutral、state transition、自動 recapture なしを確認 |
| `uv run pytest tests/integration/ui/test_settings_modal.py -q` | passed | 4 passed。save/reconnect decision、save failure 保持、recovery notice の backup 有無を確認 |
| `uv run pytest tests/unit/ui/test_dialogs.py -q` | passed | 2 passed。display-free view model と conflict warning を確認 |
| `uv run ruff format --check src/demi/application/settings_editor.py tests/unit/application/test_settings_editor.py` | passed | 2 files already formatted |
| `uv run ruff check src/demi/application/settings_editor.py tests/unit/application/test_settings_editor.py` | passed | All checks passed |
| `uv run ty check --no-progress` | passed | All checks passed |
| `uv run pytest tests/unit/application/test_dialogs.py` | not run | implementation 後に実行する |
| `uv run pytest tests/integration/ui/test_settings_modal.py` | not run | implementation 後に実行する |
| `uv run ruff format --check .` | not run | implementation 後に実行する |
| `uv run ruff check .` | not run | implementation 後に実行する |
| `uv run ty check --no-progress` | not run | implementation 後に実行する |
| `uv run pytest tests/unit` | not run | implementation 後に実行する |
| `uv run pytest tests/integration` | not run | implementation 後に実行する |
| `uv build` | not run | package gate として実行する |
| `git diff --check` | not run | implementation 後に実行する |

## 10. 先送り事項

- pyglet の実描画 widget、文字入力 focus、スクロール、color swatch は後続の UI renderer で扱う。
- connection modal の adapter list を runtime command へ送る wiring は後続の application assembly で扱う。
- colors 保存後の `RecreateWithColors` command 発行は結果 flag の consumer と同じ後続 wiring へ送る。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を作成した
- [ ] 検証結果または未実行理由を実装後に更新した
- [ ] package / release / public API に触れる場合の gate を記録した
