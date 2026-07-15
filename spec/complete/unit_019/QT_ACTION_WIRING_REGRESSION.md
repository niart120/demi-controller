# Qt 操作配線の回帰修正 仕様書

## 1. 概要

### 1.1 目的

Windows 実 display 受入で判明した、割り当て、接続設定、コントローラーカラーの操作が何も表示しない不具合を修正する。3 操作は有効表示でも既定の起動構成では dialog factory が未設定であり、`MainWindow` が何もせず戻っていた。

本 unit は Qt の既定起動経路を `ApplicationSession`、`MainWindow`、標準 dialog へ結線し、保存、取消、再検索、pairing 確認、色 preview が既存の application 境界を経由するようにする。同じ composition root で呼び出し元がなかった接続・入力開始操作も、既存の session action へ結線する。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| Windows manual acceptance | 割り当て、接続設定、色を選んでも dialog が表示されない | 2026-07-15 の利用者報告 |
| 最小再現 | `ApplicationDependencies.default()` が作る window で3 action は enabled だが dialog が開かない | 2026-07-15 の headless Qt 再現 |
| UI contract | 設定 dialog は ApplicationCoordinator 経由で1つだけ開き、開く前に capture を解除する | `spec/initial/ui.md` |
| architecture | `app.py` が具象を組み立て、UI は application 境界だけを呼ぶ | `spec/initial/architecture.md` |
| prior work | unit_016 の標準 control / dialog と unit_017 の production composition の引き渡し | `spec/complete/unit_016/`, `spec/complete/unit_017/` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| desktop user | 割り当て、接続設定、色を選ぶ | 対応する Qt dialog が1つ表示される | dialog は session-owned draft を使う |
| desktop user | dialog を保存または取消する | 保存、取消、preview、再検索は application action を通り、toolbar state が復帰する | widget が repository / runtime を直接操作しない |
| desktop user | 接続設定で新規ペアリングを選ぶ | 明示確認 dialog へ遷移し、取消で編集 dialog に戻る | pairing command は確認後だけ発行する |
| desktop user | 接続または入力開始を選ぶ | 現在 state の application action が1回だけ発行され、表示が更新される | busy state では既存の enabled 制御を維持する |

## 2. 対象範囲

- `QtApplicationEventRouter.bind()` を起点に、既定の `MainWindow` へ toolbar callback と settings dialog factory を設定する。
- mapping、connection、colors dialog を `ApplicationSession.open_settings()` で作る draft と既存 callback へ結線する。
- dialog の保存、取消、再検索、色 preview / reconnect、pairing 確認後に session snapshot を画面へ反映する。
- connection と capture の toolbar action を既存 `ApplicationSession` の意味論へ結線する。
- Qt integration test で既定の router bind から利用者操作までを確認する。
- unit_018 の Windows 実 display acceptance をこの修正後にやり直す。

## 3. 対象外

- 設定 schema、repository の原子保存、controller command の意味、Bluetooth 実機操作の変更。
- dialog の視覚設計、Qt Widgets 以外の UI 技術、standalone packaging。
- macOS / Linux の実 display acceptance。unit_018 の既存記録を維持する。

## 4. 関連 docs

- `spec/initial/ui.md`
- `spec/initial/lifecycle.md`
- `spec/initial/architecture.md`
- `spec/initial/testing.md`
- `spec/complete/unit_016/QT_STANDARD_CONTROLS_AND_DIALOGS.md`
- `spec/complete/unit_017/QT_RUNTIME_AND_LIFECYCLE_INTEGRATION.md`
- `spec/wip/unit_018/QT_QUALITY_AND_OS_ACCEPTANCE.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| 設定 dialog を開く | `IDLE` で3つの設定 action のいずれかを選ぶ | session が対応する draft を開き、対応する dialog が window modal で表示される | action は dialog 表示中に無効になる |
| 設定 dialog を閉じる | Save / Cancel / Esc | session の draft を保存または破棄し、window の active dialog と toolbar state が復帰する | 自動 capture はしない |
| connection 設定を処理する | 再検索、保存接続、新規 pairing | 既存 session action が command / confirmation を所有する | widget は runtime を直接呼ばない |
| colors を処理する | draft 色の変更、取消、保存後の再接続選択 | preview と保存済み色、reconnect state が既存 session と同期する | 色 dialog は既存の `QColorDialog` を使う |
| 通常 toolbar を処理する | 接続 / 切断、入力開始 / 解除 | enabled action が session action を1回呼び、snapshot が直ちに更新される | 既存 state machine を変えない |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-skipped | 既定の router bind 後、割り当て・接続設定・色の各 action は session-owned draft を開き、Cancel 後に次の action を開ける | regression | integration | redでは3 caseとも`active_settings_dialog is None`で失敗。greenではrouterが3 factoryを設定し、`MainWindow`がactive dialogを保持して取消後にsnapshotからtoolbarを復帰する。共通のsession-to-dialog配線以外に、このitem内で分ける構造変更はない |
| refactor-skipped | connection dialog の再検索、保存接続、pairing 確認 / 取消は既存 session action を通り、画面状態を更新する | regression | integration | `DiscoverAdapters`、pairing confirmationから編集dialogへの復帰、`ConnectSaved`をrouter bind経路で確認した。dialog factoryとsession callbackの構造は前itemで確定しており、追加refactorは不要 |
| refactor-skipped | colors dialog の preview、取消、保存後の再接続選択は session と preview widget を同期する | regression | integration | previewへ`#ABCDEF`を反映し、取消で保存色へ戻す。接続中の保存後に「後で」はreconnect保留を解除し、「再接続する」は`RecreateWithColors`を発行する。前itemのfactory callbackで完結しており、追加refactorは不要 |
| refactor-skipped | 接続と入力開始の toolbar action は既定の router bind から session action を呼び、snapshot を更新する | regression | integration | 接続済み設定では`ConnectSaved` / `Disconnect`、入力開始ではcapture stateとtoolbar checked stateを確認した。未設定の接続操作ではsessionが作ったconnection draftを既存factoryが再利用してdialogを表示し、Cancel後に状態を閉じる。callback配線以外の構造変更は不要 |
| refactor-skipped | 修正後の source GUI で設定 dialog を実 Windows display から開閉し、Tab / Enter / Space / Esc を記録する | manual | manual | 2026-07-15のWindows source GUIで、割り当てはTabからCancelを選びSpace、接続設定はTabからCancelを選びEnter、色はTab後Escで閉じ、3 dialogとも表示を確認した。visual designの妥当性とY軸反転要件は本unitの対象外として`spec/dev-journal.md`へ分離した |

## 7. 設計メモ

- 診断で確認した事実は、`MainWindow` の3 factory が初期値 `None` のままで、既定の composition root から `bind_settings_dialog_factories()` が呼ばれないことである。
- `QtApplicationEventRouter` は session と main window を同時に所有する既存の GUI-thread 境界である。この境界で callback と factory を結線すると、application package に Qt 型を入れずに session snapshot の再描画を一元化できる。
- pairing confirmation は connection dialog を閉じて draft を破棄してはならない。session の `DialogManager.replace()` に合わせ、編集 dialog と confirmation を明示的に置き換える。
- これは観測可能な振る舞いを追加する修正である。構造整理は各 green 後に別判断する。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/ui/application.py` | modify | router による toolbar / dialog factory / snapshot refresh の結線 |
| `src/demi/ui/main_window.py` | modify | dialog の安全な置換と active dialog 所有権 |
| `src/demi/ui/toolbar.py` | modify | capture action の application callback 境界 |
| `tests/integration/ui/test_qt_runtime_events.py` | modify | 既定 router bind の action-to-dialog 回帰試験 |
| `tests/integration/ui/test_application_lifecycle.py` | modify / verify | Qt event-loop と shutdown の既存契約を回帰確認 |
| `spec/wip/unit_019/QT_ACTION_WIRING_REGRESSION.md` | new / modify | TDD 状態、検証、Windows受入結果 |
| `spec/wip/unit_018/QT_QUALITY_AND_OS_ACCEPTANCE.md` | modify | 修正後の Windows manual acceptance を記録 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `QT_QPA_PLATFORM=offscreen uv run python -c ...` | failed as expected | 既定 dependencies の3 action は enabled だが dialog を開かないことを確認した。回帰testへ置換する |
| `uv run pytest tests/integration/ui/test_qt_runtime_events.py::test_router_binds_each_settings_action_to_a_session_owned_dialog -q -p no:cacheprovider` | failed as expected | mapping、connection settings、colorsの3 caseがいずれも`active_settings_dialog is None`で失敗し、未表示を再現した |
| `uv run pytest tests/integration/ui/test_qt_runtime_events.py::test_router_binds_each_settings_action_to_a_session_owned_dialog -q -p no:cacheprovider` | passed | 3 passed。router bindから対応するdialogの表示、session draft、取消後のactive dialog解除とaction復帰を確認した |
| `uv run ruff format --check src/demi/ui/application.py src/demi/ui/main_window.py tests/integration/ui/test_qt_runtime_events.py` | passed | 3 files already formatted |
| `uv run ruff check src/demi/ui/application.py src/demi/ui/main_window.py tests/integration/ui/test_qt_runtime_events.py` | passed | All checks passed |
| `uv run ty check --no-progress` | passed | All checks passed |
| `uv run pytest tests/integration/ui -q -p no:cacheprovider` | passed | 52 passed。既存のdialog、input、runtime event、lifecycle契約を回帰確認した |
| `uv run pytest tests/integration/ui/test_qt_runtime_events.py::test_router_routes_connection_dialog_actions_through_the_application_session -q -p no:cacheprovider` | passed | 1 passed。再検索、pairing取消、保存接続がruntime commandをwidgetではなくsession経由で発行することを確認した |
| `uv run ruff format --check tests/integration/ui/test_qt_runtime_events.py` / `uv run ruff check tests/integration/ui/test_qt_runtime_events.py` / `uv run ty check --no-progress` | passed | 1 file already formatted、All checks passed、All checks passed |
| `uv run pytest tests/integration/ui/test_qt_runtime_events.py::test_router_routes_colors_preview_cancel_and_reconnect_through_the_session -q -p no:cacheprovider` | passed | 1 passed。preview、取消、保存後の「後で」と「再接続する」がsessionと`RecreateWithColors`へ到達することを確認した |
| `uv run pytest tests/integration/ui/test_qt_runtime_events.py::test_router_binds_connection_and_capture_toolbar_actions_to_the_session tests/integration/ui/test_qt_runtime_events.py::test_router_opens_connection_settings_when_connection_is_not_configured -q -p no:cacheprovider` | passed | 2 passed。設定済み接続 / 切断、入力開始 / 解除、未設定接続時のconnection dialog表示とCancel後の状態復帰を確認した |
| `uv run ruff format --check src/demi/ui/application.py src/demi/ui/main_window.py src/demi/ui/toolbar.py tests/integration/ui/test_qt_runtime_events.py` / `uv run ruff check src/demi/ui/application.py src/demi/ui/main_window.py src/demi/ui/toolbar.py tests/integration/ui/test_qt_runtime_events.py` / `uv run ty check --no-progress` | passed | 4 files already formatted、All checks passed、All checks passed |
| `uv run pytest tests/integration/ui -q -p no:cacheprovider --basetemp .tmp-pytest` | passed | 56 passed。既定のWindows一時ディレクトリはアクセス拒否になるため、作業領域内の一時ディレクトリを明示した |
| `uv sync --dev` / `uv lock --check` | passed | 77 packages resolved、74 packages checked。lockfile の更新不要を確認した |
| `uv run ruff format --check .` / `uv run ruff check .` / `uv run ty check --no-progress` | passed | 127 files already formatted、All checks passed、All checks passed |
| `$env:PYTHONUTF8='1'; $env:QT_QPA_PLATFORM='offscreen'; uv run pytest tests/unit -q -p no:cacheprovider --basetemp "$env:TEMP\demi-pytest-unit-elevated"` | passed | 197 passed。既定の`pytest-of-train`は既存 ACL で利用できないため、隔離一時領域を明示した |
| `$env:PYTHONUTF8='1'; $env:QT_QPA_PLATFORM='offscreen'; uv run pytest tests/integration -q -p no:cacheprovider --basetemp "$env:TEMP\demi-pytest-full-elevated"` | passed | 66 passed。wheel smoke は通常の Windows 権限で隔離一時領域と uv cache を使用した |
| `uv build` / `git diff --check` | passed | source distribution と wheel を生成し、差分の空白エラーなしを確認した |
| Windows実 display acceptance | passed | 2026-07-15のsource GUIで、割り当て、接続設定、色の3 dialogが表示され、Tab / Space、Tab / Enter、Tab / Escで安全に閉じることを利用者が確認した |

## 10. 先送り事項

| 観測 | 先送り理由 | 後続の置き場 |
|---|---|---|
| macOS / Linux の実 display acceptance | この環境では対象 desktop がない | `spec/wip/unit_018/QT_QUALITY_AND_OS_ACCEPTANCE.md` |
| standalone artifact の Qt plugin / license / clean-environment smoke | source UI action 配線とは別の artifact 課題 | milestone 7 standalone packaging unit |
| 設定画面を含む視覚設計の妥当性とY軸反転の要件 | dialog表示の受入では、画面設計と入力意味論の要件を評価していない | `spec/dev-journal.md` の2026-07-15記録。次のwork unitで範囲を確定する |

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] 既定起動構成で未表示を再現した
- [x] TDD Test List を更新した
- [x] 全設定 action と通常 toolbar action の本番配線を確認した
- [x] targeted test と standard gate を記録した
- [x] Windows実 display acceptance を再実行した
