# 実機試験と安定化 仕様書

## 1. 概要

### 1.1 目的

Unit 005/006 の controller runtime と swbt adapter を、接続喪失、停止、終了時の例外に対して安全に戻せる状態へ整える。Bluetooth ドングルと Switch 本体を使う受入試験の入口、マーカー、記録様式を用意し、実機試験を実行していない状態を確認済みと誤記しない。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user request | unit_010 まで進めるが、Bluetooth / Switch 本体の実機検証完了は対象外 | user request |
| roadmap | Unit 008 の受入シナリオ、安定化、hardware test log | `spec/initial/roadmap.md` |
| testing | `bumble` / `hardware` の分離、記録必須項目、停止安全性 | `spec/initial/testing.md` |
| lifecycle | 接続喪失時の ERROR -> READY、切断・終了の best effort | `spec/initial/lifecycle.md` |
| existing contract | runtime worker、adapter error category、neutral frame | `spec/complete/unit_005/CONTROLLER_RUNTIME.md`, `spec/complete/unit_006/SWBT_ADAPTER.md` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| controller runtime | 接続中の frame apply が `CONNECTION_LOST` で失敗 | error を発行し、接続を切断扱いにして ERROR -> READY へ戻る | 自動無限再接続をしない |
| controller runtime | neutral、disconnect、close のいずれかが失敗して終了要求が来る | 後続の cleanup と `RuntimeStopped` を試行し、worker thread が終了する | 例外1件で close を飛ばさない |
| test operator | `tests/hardware/test_pro_controller.py` を明示実行 | hardware 環境を明示しない場合は skip し、CI の通常試験へ混入しない | skip は実機結果を意味しない |
| maintainer | 実機試験を実行していない | `spec/hardware-test-log.md` に未実行理由と必須記録項目を残す | upstream の観測を Project_Demi の結果へ転記しない |

## 2. 対象範囲

- controller runtime の接続喪失後の状態遷移と worker-owned adapter cleanup を回帰テストで固定する。
- shutdown 中に neutral / disconnect が失敗しても adapter close と `RuntimeStopped` を試行する。
- pytest の `bumble` / `hardware` marker を登録し、手動受入試験の入口を `tests/hardware/test_pro_controller.py` に置く。
- 実機試験の実行条件、記録項目、未実行状態を `spec/hardware-test-log.md` に残す。

## 3. 対象外

- Bluetooth ドングル、Bumble、Switch 本体を使った新規 pairing、再接続、入力、gyro 調整、抜去試験。
- Windows 11 の受入結果を確認済みとすること。
- macOS / Linux の OS 別確認（Unit 009）。
- standalone packaging（Unit 010）。
- 自動再接続、OS の sleep 通知、接続状態を越えた新しい UI wiring。

## 4. 関連 docs

- `spec/initial/roadmap.md`
- `spec/initial/testing.md`
- `spec/initial/lifecycle.md`
- `spec/initial/README.md`
- `spec/complete/unit_005/CONTROLLER_RUNTIME.md`
- `spec/complete/unit_006/SWBT_ADAPTER.md`
- `spec/hardware-test-log.md`
- `AGENTS.md`
- `SKILLS.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| 接続喪失を扱う | CONNECTED、frame apply が `CONNECTION_LOST` | `ControllerError(CONNECTION_LOST)` を発行し、adapter を切断・解放して ERROR -> READY へ遷移する | 後続の active frame は送信しない |
| watchdog neutral の失敗を扱う | CONNECTED、neutral apply が `CONNECTION_LOST` | error を発行し、接続喪失処理へ進む | 同じ epoch の再送を続けない |
| 停止 cleanup を継続する | rest または disconnect が例外 | close を試行し、`RuntimeStopped` を発行して thread を終了する | cleanup の最初の例外で後続処理を中断しない |
| hardware marker を選ぶ | 通常の pytest、`-m hardware`、`-m bumble` | 通常試験では対象外、明示実行では専用試験だけが選択される | strict marker で収集エラーにしない |
| hardware 実行条件を満たさない | `DEMI_HARDWARE=1` 未指定 | hardware test は skip され、合格結果とは扱わない | 実機なしの偽陽性を作らない |
| hardware 記録を開始する | 試験未実行または実行済み | commit、依存、OS、USB、対象機器、結果を記録できる | bond 内容や秘密診断値は記録しない |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| todo | 接続中の frame apply が接続喪失したとき、error と ERROR -> READY、cleanup を発行する | regression / edge | integration | adapter unplug 相当を fake adapter で再現する |
| todo | 接続喪失後の frame を再送せず、再接続要求を待機できる | regression | integration | 自動再接続をしない契約を確認する |
| todo | shutdown の neutral / disconnect 失敗後も close、RuntimeStopped、thread 終了まで進む | regression / edge | unit | cleanup の best effort を確認する |
| todo | `bumble` / `hardware` marker と hardware test entrypoint が通常試験から分離される | new | package | 未設定環境では skip、実機結果を生成しない |
| todo | hardware test log が必須環境情報と未実行理由を保持する | new | docs | Project_Demi 自身の試験結果だけを記録する |
| todo | unit / integration / marker 選択 / package gate が通る | characterization | package | build と wheel smoke を含める |

## 7. 設計メモ

- `ControllerRuntime` の adapter 所有境界は維持し、main thread へ adapter object や lower-level exception を返さない。
- 接続喪失時は error event を発行したあと、可能な範囲で adapter を切断・解放する。解放処理の失敗は別の `SHUTDOWN_FAILED` として記録するが、後続 cleanup を止めない。
- hardware test は自動的な Bluetooth 操作を実装しない。`DEMI_HARDWARE=1` がない実行は skip とし、実機試験の結果を自動生成しない。
- 初期設計の「Unit 008 受入シナリオ通過」は、ユーザー指定により今回の実行対象から除外する。完了記録には未実行理由を残し、Windows 11 や Switch 本体を確認済みとは記載しない。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/controller/runtime.py` | modify | connection loss と shutdown cleanup の安定化 |
| `tests/integration/controller/test_runtime_commands.py` | modify | 接続喪失後の状態、frame 抑止、cleanup 回帰 |
| `tests/unit/controller/test_runtime.py` | modify | shutdown cleanup の best effort 回帰 |
| `tests/hardware/test_pro_controller.py` | new | 明示実行用 hardware / bumble test entrypoint |
| `pyproject.toml` | modify | pytest marker 登録 |
| `spec/hardware-test-log.md` | modify | Unit 008 の実機未実行記録 |
| `spec/complete/unit_008/HARDWARE_STABILITY.md` | new | 完了記録 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/integration/controller/test_runtime_commands.py -q` | not run | TDD 実装前 |
| `uv run pytest tests/unit/controller/test_runtime.py -q` | not run | TDD 実装前 |
| `uv run pytest tests/hardware -q` | not run | 実機試験はユーザー指定により対象外 |
| `uv sync --dev` | not run | package / marker 変更後に実行する |
| `uv lock --check` | not run | 依存変更は予定しないが標準 gate として実行する |
| `uv run ruff format --check .` | not run | 実装後に実行する |
| `uv run ruff check .` | not run | 実装後に実行する |
| `uv run ty check --no-progress` | not run | 実装後に実行する |
| `uv run pytest tests/unit` | not run | 実装後に実行する |
| `uv run pytest tests/integration` | not run | 実装後に実行する |
| `uv build` | not run | package smoke とともに実行する |
| `git diff --check` | not run | 実装後に実行する |

## 10. 先送り事項

- Windows 11 と Switch 本体を使う Unit 008 acceptance は、ユーザー指定により未実行。実行時は `spec/hardware-test-log.md` の必須項目を埋める。
- macOS / Linux の起動・UI・可能な実機接続は Unit 009 へ送る。
- standalone package の clean environment 起動は Unit 010 へ送る。

## 11. チェックリスト

- [ ] 対象範囲と対象外を確認した
- [ ] TDD Test List を更新した
- [ ] 検証結果または未実行理由を実装後に更新した
- [ ] 実機未実行を `spec/hardware-test-log.md` に記録した
- [ ] package / release / public API に触れる場合の gate を記録した
