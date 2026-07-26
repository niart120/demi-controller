# 外部ゲームコントローラーの選択と保存

## 1. 概要

### 1.1 目的

SDL GameController 対応機器を設定画面で一覧表示し、利用する 1 台を選択して保存する。保存済み GUID が接続中の機器を一意に指すときだけ復元し、見つからない、または同一 GUID が複数あるときは自動選択へ戻す。選択中の機器が切断された評価周期では、ゲームパッド入力を中立へ戻す。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| GitHub issue | GUI による SDL GameController の選択、GUID 保存復元、切断時中立化 | `https://github.com/niart120/demi-controller/issues/55` |
| 完了済み issue | SDL 入力の初期対応。最初に見つかった機器を自動選択する | `https://github.com/niart120/demi-controller/issues/54` |
| 現行実装 | SDL backend は最初の対応機器を開き、Windows では XInput 優先 backend がこれを覆う | `src/demi/platform/sdl_gamepad.py`, `src/demi/input/gamepad.py`, `src/demi/app.py` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| 利用者 / 設定画面 | 接続中の SDL 機器を開く | 名前と現在の選択を確認できる | device index を表示・保存しない |
| 利用者 / 設定保存 | 1 台または自動選択を指定する | GUID または `None` が設定へ保存され、次回起動時に反映される | 同一 GUID 複数台は復元対象にしない |
| 入力評価 | 選択中機器が切断される | その tick でゲームパッド状態が中立になる | キーボード・マウス入力は継続する |

## 2. 対象範囲

- `GamepadDevice` と `GamepadSelectionPort` を SDL 定数・ポインターを漏らさない入力境界として定義する。
- SDL backend が接続中の機器を列挙し、instance ID で実行中の選択を保持し、GUID で保存済み選択を照合する。
- 現行 Windows の XInput 優先合成を含め、GUI で選んだ機器が実際に入力として評価されるようにする。
- `InputSettings`、TOML codec、`SettingsEditor`、設定画面、翻訳を更新する。
- save / cancel、設定復元不能時の自動選択、切断時中立化を fake backend と Qt 統合試験で固定する。

## 3. 対象外

- 複数機器の同時合成。
- 機器ごとの割り当てプロファイル、軸から軸への任意変換（Issue #56）。
- raw joystick、振動、LED、バッテリー残量。
- 同一 GUID の複数機器を区別して復元するための独自識別子保存。

## 4. 関連 docs

- `spec/initial/requirements.md`
- `spec/initial/ui.md`
- `spec/initial/testing.md`
- `spec/complete/unit_054/STANDALONE_SDL_AND_USB_DIAGNOSTICS.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| 機器列挙 | SDL GameController 対応機器が接続中 | `name`、GUID、実行中だけの instance ID を持つ機器一覧を返す | device index は境界外へ出さない |
| 明示選択 | 保存済み GUID が接続中の 1 台に一致 | その機器を選び、poll はその入力だけを返す | instance ID は接続中の管理専用 |
| 自動選択 | 保存値が `None`、未接続、または GUID が重複 | 利用可能な最初の 1 台を選ぶ | 起動失敗にはしない |
| 切断 | 選択中 instance ID の機器が切断 | 当該 tick の `GamepadState` は neutral | キーボード・マウスの状態を消さない |
| 保存と取消 | 設定画面で選択変更後に保存または取消 | 保存だけが GUID / `None` を永続化し live backend へ適用する | device index を codec に書かない |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-skipped | 接続中 SDL 機器を名前・GUID・instance ID で列挙し、device index を公開しない | new | unit | platform / input boundary。red: `GamepadDevice` が未定義。green: `test_backend_lists_connected_devices_without_exposing_device_indexes` |
| refactor-done | 保存済み GUID が一意に一致するとその機器だけを poll し、未接続または重複では自動選択へ戻る | new | unit | platform。red: 明示 GUID でも index 0 を開いた。green: 一意一致は選択、未接続・重複は index 0 の自動選択。fixture 重複を `_install_devices` へ整理 |
| todo | 選択中機器の切断 tick はゲームパッド状態を中立へ戻す | regression | unit | platform / coordinator |
| todo | GUID または自動選択を設定 codec が往復し、device index を受理・出力しない | new | unit | domain / config |
| todo | draft editor の選択は保存時だけ live backend へ適用され、取消は変更しない | new | unit | application |
| todo | 設定画面が機器一覧、自動選択、現在選択を表示し、保存後に選択を反映する | new | integration | UI |
| todo | 日本語翻訳カタログが追加した設定画面の文言を持つ | new | integration | package |
| todo | Windows の XInput 優先経路でも明示選択が別機器の入力で覆われない | regression | integration | application |

## 7. 設計メモ

- 永続値は `str | None` の GUID とする。`None` は自動選択を表す。
- instance ID は SDL 接続中の handle と選択中機器の照合だけに使い、設定や GUI の保存値に使わない。
- 1 GUID に複数機器が一致したときは保存選択を使わず自動選択へ戻す。再接続は、同じ GUID が後で一意になった評価周期に再び選択できる。
- `GamepadSelectionPort` は列挙と選択だけを担い、`poll()` と入力評価の責務を混ぜない。
- 現行 `PreferredGamepadBackend` の優先規則は、明示選択を覆えないように再設計する。XInput 固有の永続識別は本 unit で導入しない。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/domain/settings.py` | modify | 保存するゲームパッド選択値 |
| `src/demi/config/codec.py` | modify | GUID / 自動選択の TOML codec |
| `src/demi/input/gamepad.py` | modify | 選択境界と backend 合成契約 |
| `src/demi/platform/sdl_gamepad.py` | modify | SDL 列挙、GUID 照合、instance ID 管理 |
| `src/demi/application/settings_editor.py` | modify | immutable draft 更新 |
| `src/demi/app.py` | modify | 保存後の live selection 適用 |
| `src/demi/ui/dialogs/` | modify / new | 機器選択 UI |
| `src/demi/i18n/demi_ja.ts` | modify | 追加 UI 文言の翻訳 |
| `tests/unit/` | modify / new | domain、codec、platform、application の振る舞い試験 |
| `tests/integration/ui/` | modify / new | 保存・取消と設定画面の回帰試験 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `gh api repos/niart120/demi-controller/issues/55` | passed | 2026-07-26 に issue の受入条件を取得 |
| `gh api repos/niart120/demi-controller/issues/54` | passed | 2026-07-26 に前提範囲と対象外を照合 |
| `uv run python -c "...PySDL2 API..."` | passed | 名前、joystick、GUID の各 API がインストール済み binding に存在 |
| `uv run pytest tests/unit/platform/test_sdl_gamepad.py -q -p no:cacheprovider` | passed | 6 passed。列挙と保存 GUID 選択の red / green、fixture refactor を確認 |
| 標準 gate | not run | 実装前 |
| SDL 実機の複数台・切断確認 | not run | 対象機器を接続後に別途実施 |

## 10. 先送り事項

- 同一 GUID の複数機器を区別して復元する識別方法は Issue #55 の対象外とし、複数時は自動選択へ戻す。
- SDL GameController 非対応の raw joystick は対象外。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を更新した
- [x] 検証結果または未実行理由を記録した
- [ ] package / release / public API に触れる場合の gate を記録した
