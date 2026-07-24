# swbt-python 0.5 移行 仕様書

## 1. 概要

### 1.1 目的

Project_Demi の実行時依存を `swbt-python>=0.5.1,<0.6.0` へ更新し、0.5.0 で削除された
`key_store_path` と新規ペアリング経路を、`profile_path` と
`DirectProController.create_profile()` へ移行する。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user request | このリポジトリが依存する swbt-python を 0.5.0 へ更新する | conversation |
| user request | protocol-ready待機を追加したswbt-python 0.5.1を反映し、GUI挙動を再確認する | conversation |
| upstream release | `key_store_path` を削除し、swbt プロファイルへ移行した | `swbt-python` v0.5.0 release notes |
| upstream release | 接続APIが初期subcommand応答とplayer割り当て完了まで待つ | `swbt-python` v0.5.1 release notes |
| current implementation | `DirectProController(..., key_store_path=...)` を生成している | `src/demi/controller/swbt_adapter.py` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| saved reconnect | Project_Demi の保存スロットに swbt 0.5 プロファイルがある | `profile_path` を渡した Direct controller が再接続する | pairing fallback を開始しない |
| explicit pairing | 利用者が未使用スロットまたは初回失敗後のスロットでペアリングを確認する | 未使用なら `create_profile()`、既存なら profile constructor と `connect(allow_pairing=True)` でペアリングする | CSR アドレスを Project_Demi 側で生成しない |
| color reconnect | 接続済みプロファイルと色設定がある | 同じ `profile_path` で controller を再生成して再接続する | profile 内容を解釈しない |
| package consumer | Project_Demi を導入する | swbt-python 0.5 系が解決される | 0.4 系を許容しない |

## 2. 対象範囲

- `swbt-python` 依存範囲を `>=0.5.1,<0.6.0` へ更新する。
- lock を swbt-python 0.5.1 へ更新する。
- 保存済み接続で `profile_path` を使う。
- 新規ペアリングで `DirectProController.create_profile()` を使う。
- 0.5.1 の公開 Direct API、protocol-ready待機、物理単位 API、例外境界を検証する。
- 0.5.1更新後のGUIからSwitchへペアリングし、接続と通常入力を目視確認する。
- `spec/initial/swbt-integration.md` とライフサイクル記述を現行契約へ合わせる。

## 3. 対象外

- Project_Demi の `bond_slot` 設定名、command field、保存ディレクトリの改名。
- swbt 0.4 の key-store JSON から 0.5 プロファイルへの自動移行。
- 利用者管理 Bluetooth アドレスの入力 UI。
- swbt-python 自体の実装変更。
- 接続要求時の入力捕捉解除、接続待ちフレーム破棄、初期入力内容の変更。

## 4. 関連 docs

- `spec/initial/swbt-integration.md`
- `spec/initial/lifecycle.md`
- `spec/initial/configuration.md`
- `spec/complete/unit_039/DIRECT_FRAME_SEND.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| 依存解決 | `uv lock` | swbt-python 0.5.1 を解決し、0.5.0以前を許容しない | Bumble 0.0.230 は upstream 制約に従う |
| 保存済み再接続 | `bond_path` として渡された Project_Demi の保存先 | `DirectProController(profile_path=...)` を生成し、`open()`、`reconnect()` を呼ぶ | Project_Demi 内部の field 名は維持 |
| 新規ペアリング | 未使用の保存先 | `DirectProController.create_profile(profile_path=..., local_address=None, pair_timeout=...)` を呼ぶ | 戻り値はprotocol-ready controller |
| ペアリング再試行 | 初回失敗後に残った保存先 | `DirectProController(profile_path=...)` を開き、`connect(allow_pairing=True)` を呼ぶ | 既存 profile を上書きしない |
| 色変更後の再接続 | 接続済み controller | close 後、同じ保存先を `profile_path` として再生成する | 新規 profile は作らない |
| 旧ファイル | swbt 0.4 の key-store JSON | 自動変換しない | 利用者は別スロットまたは旧ファイル削除後に再ペアリングする |
| Direct send | `send(state)` | Bumble の入力レポート enqueue 完了まで await する | HCI 完了や対象機器反映は待たない |
| 接続完了 | pairing / reconnectでHID channelが開く | 初期subcommand応答とplayer割り当てが完了するまで公開接続APIが復帰しない | Project_Demiの`CONNECTED`と通常入力は復帰後 |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| green | runtime dependency がswbt-python 0.5.1以上を解決し、必要な公開APIをimportできる | regression | package | version、constructor、create_profile |
| green | 保存済み接続が `profile_path` を渡し、従来どおり open/reconnect する | regression | unit / integration | `key_store_path` を渡さない |
| green | 新規ペアリングが profile creator を一度呼び、返された接続済み controller を所有する | new | unit / integration | open/connect の二重呼び出しをしない |
| green | 初回ペアリング失敗後に残った profile を同じスロットから再試行できる | regression | integration | constructor と `connect(allow_pairing=True)` を使う |
| green | 色変更後の再接続が同じ `profile_path` を再利用する | regression | integration | Direct constructor 経路 |
| green | swbt 0.5 の無効プロファイルを保存情報エラーとして分類する | edge | unit | 秘密情報や下位例外を露出しない |
| green | 既存 profile path への新規ペアリングをタイムアウトと誤分類しない | edge | unit / application | 別スロット選択または明示削除が必要 |
| green | wheel metadata が swbt-python 0.5 系の依存範囲を含む | regression | package | `uv build` で確認 |
| green | 公開仕様が profile、初回作成、enqueue 完了、旧形式非互換を正確に説明する | regression | docs | prose review。docs site は存在しない |

## 7. 設計メモ

- `bond_slot` は Project_Demi が所有する保存スロット名として維持する。swbt へ渡す境界では
  `profile_path` に写像する。
- 通常 constructor と初回 profile 作成は呼び出し形が異なるため、adapter へ
  `gamepad_factory` と `profile_creator` を別々に注入する。
- `create_profile()` の戻り値は初回ペアリングとprotocol初期化が完了済みであり、
  Project_Demiは`open()`や`connect()`を重ねて呼ばない。
- `local_address=None` を明示し、専用 USB Bluetooth ドングルの現在アドレスを使う。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `pyproject.toml` | modify | swbt-python 0.5 系へ更新 |
| `uv.lock` | modify | 0.5.1 を解決 |
| `src/demi/controller/swbt_adapter.py` | modify | profile constructor / creator 境界へ移行 |
| `src/demi/controller/events.py` | modify | profile path 競合の安全なエラー分類 |
| `src/demi/app.py` | modify | profile path 競合の利用者向け表示 |
| `tests/unit/controller/test_swbt_dependency.py` | modify | 0.5 公開契約 |
| `tests/unit/controller/test_swbt_adapter.py` | modify | constructor と creator の引数 |
| `tests/unit/controller/test_swbt_errors.py` | modify | profile error 分類 |
| `tests/unit/application/test_app.py` | modify | profile path 競合の安全な表示 |
| `tests/integration/controller/test_swbt_lifecycle.py` | modify | 保存再接続、初回作成、色再接続 |
| `spec/initial/README.md` | modify | 対象 swbt 版と Direct send 完了境界 |
| `spec/initial/architecture.md` | modify | profile 作成・再接続の構成 |
| `spec/initial/input.md` | modify | Direct send の enqueue 完了境界 |
| `spec/initial/risks.md` | modify | 0.5 系 dependency risk |
| `spec/initial/swbt-integration.md` | modify | 0.5 契約と移行制約 |
| `spec/initial/lifecycle.md` | modify | 初回 profile 作成経路 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv lock` | passed | swbt-python 0.4.0 から 0.5.0 へ更新 |
| `uv lock --upgrade-package swbt-python` / `uv sync --dev` | passed | swbt-python 0.5.0から0.5.1へ更新し、仮想環境でも0.5.1を確認 |
| `uv run pytest -p no:cacheprovider tests/unit/controller/test_swbt_dependency.py tests/unit/controller/test_swbt_adapter.py tests/unit/controller/test_swbt_errors.py tests/unit/application/test_app.py tests/integration/controller/test_swbt_lifecycle.py tests/integration/controller/test_runtime_commands.py tests/integration/ui/test_qt_runtime_events.py -q` | passed | 56 passed。0.5.1公開API、adapter lifecycle、エラー表示と既存の接続入力契約を確認 |
| `uv run pytest tests/unit/controller/test_swbt_dependency.py -q` | passed | red は 0.4.0 解決で version assertion が失敗、lock 更新後は `1 passed` |
| `uv run pytest tests/unit/controller/test_swbt_adapter.py::test_adapter_info_and_project_colors_cross_the_public_boundary -q` | passed | red は `profile_path` 不在、実装変更後は `1 passed` |
| `uv run pytest tests/unit/controller/test_swbt_adapter.py::test_new_pairing_uses_profile_creator_without_reopening_the_paired_gamepad -q` | passed | red は `profile_creator` 注入境界不在、実装後は `1 passed` |
| `uv run pytest tests/integration/controller/test_swbt_lifecycle.py -q` | passed | `2 passed`。保存再接続、初回 profile 作成、色再接続の呼び出し順を確認 |
| `uv run pytest tests/unit/controller/test_swbt_errors.py::test_invalid_swbt_profile_is_classified_as_saved_bond_error -q` | passed | red は `RECONNECT_FAILED`、分類追加後は `BOND_NOT_FOUND` で `1 passed` |
| `uv run pytest tests/integration/controller/test_swbt_lifecycle.py::test_pairing_retries_an_existing_profile_without_creating_it_again -q` | passed | red は creator を再呼び出し、既存 profile 分岐後は `1 passed` |
| `uv run pytest tests/unit/controller/test_swbt_errors.py::test_existing_profile_path_is_not_reported_as_pairing_timeout tests/unit/application/test_app.py::test_existing_pairing_profile_has_a_specific_safe_message -q` | passed | `2 passed`。path競合をタイムアウトと分離し、安全な表示を確認 |
| `uv sync --dev` | passed | 77 packageを解決し、74 packageを確認 |
| `uv lock --check` | passed | 77 packageを解決、lock差分なし |
| `uv run ruff format --check .` | passed | 146 files already formatted |
| `uv run ruff check .` | passed | All checks passed |
| `uv run ty check --no-progress` | passed | All checks passed |
| `uv run pytest tests/unit` | passed | 298 passed |
| `uv run pytest tests/integration` | passed | 124 passed |
| `uv build` | passed | sandbox内の初回はbuild isolationのnetwork拒否。承認付き再実行でwheel / sdist作成 |
| `uv run python -c "...wheel METADATA..."` | passed | 0.5.1更新後のwheelで`Requires-Dist: swbt-python>=0.5.1,<0.6.0`を確認 |
| 0.5.1更新後の標準gate | passed | `uv lock --check`、ruff format/check、ty、unit 298件、integration 124件、`uv build`、`git diff --check`が成功 |
| scope cleanup後の標準gate | passed | 調査中の接続入力変更を除去後、ruff format/check、ty、unit 298件、integration 124件、`uv build`、`git diff --check`が成功 |
| `uv run mkdocs build --strict` | not applicable | repoに`mkdocs.yml`とdocs dependencyがない |
| docs-quality-review | passed | 初回失敗後profileの再試行経路を追記。仮テキスト、会話依存語、未検証の断定なし |
| swbt-python 0.5.1 GUI / Switch確認 | observed-pass | 2026-07-24。GUIからのペアリング後、利用者が期待どおりの接続と入力動作を確認した。ログはWindows 11、Python 3.12.10、swbt 0.5.1を記録し、初期rest後の通常入力と正常終了を確認。対象機器画面の判定は利用者目視 |
| `git diff --check` | passed | whitespace errorなし。既存のLF/CRLF変換warningのみ |

## 10. 先送り事項

- `bond_slot` / `bond_path` と `profiles/` への用語・保存先移行は、利用者設定 migration を
  設計する別作業単位へ送る。
- swbt 0.4 key-store JSON の自動移行は upstream が互換経路を提供しないため実装しない。
- 別OS、別USB Bluetoothドングル、別対象機器での0.5.1実機互換性は未確認。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を更新した
- [x] 検証結果または未実行理由を記録した
- [x] package / release / public API に触れる場合の gate を記録した
