# SDL ゲームパッド入力 仕様書

## 1. 概要

### 1.1 目的

SDL GameController 対応機器を、既存のキーボード・マウス入力と同じ評価 tick で仮想 Pro Controller 入力へ反映する。SDL のウィンドウ、映像、音声、独自メインループは使用しない。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| GitHub issue #54 | SDL GameController 入力、標準配置、接続管理、縮退動作 | `https://github.com/niart120/demi-controller/issues/54` |
| user request | `pysdl2-dll` を通常依存として採用する | 対話 2026-07-25 |
| input design | 入力の状態、評価、ライフサイクル | `spec/initial/input.md` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| XInput または SDL GameController 利用者 | 対応機器を接続してアプリを起動する | 標準配置に従う Pro Controller frame が既存 tick で送られる | 機器選択はしない |
| 利用者 | 機器を切断、または SDL 初期化に失敗する | ゲームパッド成分は中立になり、キーボード・マウスは継続する | アプリは終了しない |
| 配布利用者 | wheel または standalone artifact を使う | SDL2 ランタイムと通知への到達経路がある | 実機 OS 確認は別途記録する |

## 2. 対象範囲

- `PySDL2` と `pysdl2-dll` を通常依存へ追加する。
- SDL の値をドメインの `GamepadState` へ正規化し、`PhysicalInputState` に保持する。
- 固定デッドゾーン、Y 軸変換、トリガー閾値、SDL 標準配置を実装する。
- 既存の `CaptureCoordinator.evaluate()` でポーリングし、キーボード・マウスと合成する。
- 最初に認識した 1 台の接続、切断、再接続と終了時 close を扱う。
- Windows では XInput を優先し、XInput slot がない場合だけ SDL GameController を使う。
- パッケージング、ライセンス一覧、third-party notice を更新する。

## 3. 対象外

- 機器の選択・保存、GUID 保存、複数台の同時合成（#55）。
- `GAMEPAD:` source、任意割り当て、軸から軸への設定可能な変換（#56）。
- デッドゾーン、閾値、応答曲線の設定 UI。
- バックグラウンド入力、振動、ジャイロ、加速度、タッチパッド、LED。

## 4. 関連 docs

- `spec/initial/input.md`
- `spec/initial/architecture.md`
- `spec/initial/testing.md`
- `packaging/LICENSES.md`
- `src/demi/THIRD_PARTY_NOTICES.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| 正規化 | SDL の signed 16-bit stick と trigger | stick は `-1.0..1.0`、trigger は `0.0..1.0` に clamp される | Y はドメイン座標へ 1 箇所で反転する |
| デッドゾーン | stick 値が 0.15 以下 | 0.0 になる | 範囲外は連続的に再スケールする |
| 標準配置 | GamepadState | 同じ物理位置の `LogicalButton` と stick が frame へ加わる | trigger は 0.5 以上で ZL/ZR |
| 合成 | profile 入力と gamepad 入力 | button は和集合、各 stick 方向は成分別最大値で合成する | 円形制限は合成後に適用する |
| ライフサイクル | 未接続、切断、初期化失敗、close | gamepad 成分は中立、他の入力を妨げない | close は idempotent |
| backend 選択 | Windows の XInput slot と SDL GameController | XInput 接続中は XInput を固定選択し、切断後に再選択する | SDL は fallback |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-skipped | GamepadState は中立値と正規化範囲を保持する | new | unit | SDL 型を漏らさず、`tests/unit/domain/test_gamepad_state.py` で確認。追加の構造変更は不要 |
| refactor-skipped | stick の dead zone、再スケール、Y 軸変換、trigger clamp を正規化する | new | unit | `tests/unit/input/test_gamepad.py` で確認。追加の構造変更は不要 |
| refactor-skipped | 標準配置は face、d-pad、shoulder、trigger、stick click を Pro ボタンへ変換する | new | unit | guide は HOME として取得できた場合だけ変換する。追加の構造変更は不要 |
| refactor-skipped | profile の方向入力と gamepad stick を定義済み規則で合成する | new | unit | `tests/unit/input/test_publisher.py` で確認。circular limit は合成後に適用する |
| refactor-skipped | coordinator の評価 tick は fake gamepad を一度 poll して frame に反映する | new | integration | `tests/unit/application/test_coordinator.py` と既存 timer integration で確認。新規 timer は追加していない |
| refactor-skipped | focus、設定、shutdown、切断で gamepad 成分を残留させず backend を close する | new | integration | `PhysicalInputState.clear()` と shutdown close を unit / integration suite で確認 |
| refactor-skipped | SDL backend は最初の対応機器を開き、切断後に再接続する | new | unit | `tests/unit/platform/test_sdl_gamepad.py` の SDL function fake で確認 |
| refactor-skipped | Windows XInput backend は接続 slot を選択し、buttons、sticks、triggers を正規化する | regression | unit | `tests/unit/platform/test_windows_xinput.py` で確認。実機で XInput button と thumb stick の変化を確認 |
| refactor-skipped | XInput 接続中は SDL fallback へ切り替えず、切断後に再選択する | regression | unit | `tests/unit/input/test_gamepad.py` で確認 |
| refactor-skipped | package metadata、lock、PyInstaller、notice は両 runtime dependency を含む | new | package | `tests/unit/test_packaging.py`、`uv lock --check`、`uv build` で確認 |
| deferred | 開発環境の実機で接続、切断、再接続を確認する | new | manual | 対象機器がないため未実行 |

## 7. 設計メモ

- `GamepadInputPort` は `poll() -> GamepadState` と `close() -> None` のみを公開する。
- `CaptureCoordinator` が `evaluate()` の直前に port を poll し、失敗時は中立を保存する。SDL と XInput の詳細は `platform` 層に閉じる。
- `pysdl2-dll` は PySDL2 が SDL2 共有ライブラリーを解決できるようにする通常依存である。PyInstaller では両配布物を収集対象にする。
- Windows の Azeron Keypad では SDL raw joystick が trigger axes だけを返し、XInput は buttons と thumb stick を返した。Windows では XInput を優先する。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `pyproject.toml` | modify | PySDL2 と pysdl2-dll の runtime dependency |
| `uv.lock` | modify | 解決済み依存 |
| `src/demi/domain/gamepad.py` | new | 正規化済みゲームパッド型 |
| `src/demi/domain/physical_input.py` | modify | gamepad 状態の保持 |
| `src/demi/input/gamepad.py` | new | port と標準配置の純粋変換 |
| `src/demi/platform/sdl_gamepad.py` | new | SDL2 backend |
| `src/demi/platform/windows_xinput.py` | new | Windows XInput backend |
| `src/demi/application/coordinator.py` | modify | tick と close の統合 |
| `src/demi/app.py` | modify | production composition |
| `packaging/` | modify | SDL2 の収集と license inventory |
| `src/demi/THIRD_PARTY_NOTICES.md` | modify | SDL2 notice 導線 |
| `tests/` | modify | unit、integration、package regression |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/unit -q` | failed | 終了時に既存 `.pytest_cache` のアクセス拒否で失敗したため、cache provider を無効化した同一 suite を実行 |
| `uv run pytest tests/unit -q -p no:cacheprovider --basetemp=tmp/pytest-xinput-unit` | passed | 340 passed |
| `uv run pytest tests/integration -q` | failed | 終了時に既存 `.pytest_cache` のアクセス拒否で失敗したため、cache provider を無効化した同一 suite を実行 |
| `uv run pytest tests/integration -q -p no:cacheprovider --basetemp=tmp/pytest-xinput-integration` | passed | 133 passed |
| `uv run ruff format --check .` | passed | 152 files already formatted |
| `uv run ruff check .` | passed | All checks passed |
| `uv run ty check --no-progress` | passed | All checks passed |
| `uv lock --check` | passed | lockfile は metadata と一致 |
| `uv build` | passed | source distribution と wheel を生成 |
| `git diff --check` | passed | whitespace error なし |

## 10. 先送り事項

- Windows 11 で Azeron Keypad の XInput button と thumb stick の直接取得は確認済み。Project_Demi の実行中に Pro Controller frame まで反映される手動確認、USB / Bluetooth の切断・再接続は未実行。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を更新した
- [x] 検証結果または未実行理由を記録した
- [x] package / release / public API に触れる場合の gate を記録した
