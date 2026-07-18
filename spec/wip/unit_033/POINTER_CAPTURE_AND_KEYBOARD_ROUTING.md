# マウス捕捉と常時キーボード入力 仕様書

## 1. 概要

### 1.1 目的

現在の「入力捕捉」をマウスの排他捕捉へ限定し、メインウィンドウが操作可能かつフォーカスを持つ間は、マウス捕捉の有無にかかわらずキーボード割り当てを評価する。マウス捕捉解除を `F12` から `F4` へ変更し、既定の HOME 割り当てを `Escape` から `F1` へ移す。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user request | capture on / off をマウスへ限定し、キーボード入力は常時受け入れる | 対話、2026-07-19 |
| user request | マウス捕捉解除を `F4`、HOME の既定割り当てを `F1` とする | 対話、2026-07-19 |
| current implementation | `CAPTURED` と `capture_active` が keyboard / mouse / runtime を一括で切り替える | `src/demi/application/coordinator.py`, `src/demi/input/publisher.py` |
| current safety | `F12`、focus loss、dialog、shutdown が排他マウスと全保持入力を解除する | `spec/complete/unit_015/QT_INPUT_AND_CONTROLLER_PREVIEW.md`, `spec/complete/unit_023/WINDOWS_EXCLUSIVE_MOUSE.md` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| user | main window に focus があり、マウス捕捉を開始せず `F` を押す | A の keyboard binding を preview と接続先へ送る | mouse button / motion は controller 入力にしない |
| user | toolbar からマウス捕捉を開始する | exclusive mouse、mouse button、relative motion を有効にする | keyboard mapping は開始前後で継続する |
| user | マウス捕捉中に keyboard を保持して `F4` を押す | mouse capture と mouse state だけを解除し、`F4` 自体を mapping へ流さない | 保持中の別 keyboard source は維持する |
| user | focus loss、dialog、shutdown を行う | keyboard / mouse の両方を neutralize する | focus 復帰後に mouse capture を自動再開しない |
| existing user | legacy default profile と `release_capture = ["F12"]` を読み込む | HOME を F1、release を F4 へ既定移行する | custom binding / shortcut は勝手に置換しない |

## 2. 対象範囲

- operational keyboard routing と pointer capture を別の状態として表現する。
- `IDLE` と pointer-captured 状態の両方で keyboard binding を評価する。
- pointer capture 外では mouse button、wheel、relative motion、mouse gyro を controller mapping へ流さない。
- toolbar action と既存 toggle shortcut の意味を pointer capture on / off へ変更する。
- pointer capture の表示文言、状態バー、preview flag を mouse 固有の表現へ変更する。
- `F4` を pointer capture release の優先 local action とし、mapping 候補から除外する。
- `F12` を固定予約から外し、通常の binding source として使用可能にする。
- built-in Default profile の HOME source を `KEY:F1` とする。
- legacy built-in Default profile の `KEY:ESCAPE → BUTTON:HOME` だけを `KEY:F1` へ移行する。custom profile と変更済み HOME binding は保持する。
- legacy の既定 `release_capture = ["F12"]` だけを `F4` へ移行し、明示的な custom 値は保持する。
- focus loss、settings dialog、shutdown の全入力 neutralization 契約を維持する。
- Windows exclusive mouse hook、Raw Input、Qt fallback の開始・停止を pointer capture state へ結び直す。
- `spec/initial/input.md`、`spec/initial/lifecycle.md`、`spec/initial/requirements.md`、`spec/initial/ui.md`、`spec/initial/testing.md` を更新する。

## 3. 対象外

- global keyboard hook と background keyboard input。
- focus のない window、editable dialog、shutdown 中の keyboard mapping。
- `Ctrl+C` 以外への pointer capture toggle shortcut 変更。既存 shortcut は意味だけを mouse 固有へ変更する。
- Windows 以外での排他 mouse 保証拡大。
- keyboard source と mouse source を別 profile に分割すること。
- pointer capture 解除時に共有 yaw / pitch 姿勢を強制的に水平へ戻すこと。mouse delta と resampler は消去するが、keyboard 診断由来の姿勢は operational input の状態として維持する。

## 4. 関連 docs

- `spec/initial/configuration.md`
- `spec/initial/input.md`
- `spec/initial/lifecycle.md`
- `spec/initial/requirements.md`
- `spec/initial/testing.md`
- `spec/initial/ui.md`
- `spec/complete/unit_003/INPUT_PIPELINE.md`
- `spec/complete/unit_015/QT_INPUT_AND_CONTROLLER_PREVIEW.md`
- `spec/complete/unit_016/QT_STANDARD_CONTROLS_AND_DIALOGS.md`
- `spec/complete/unit_023/WINDOWS_EXCLUSIVE_MOUSE.md`
- `spec/complete/unit_027/CAPTURED_CONNECTION_SHORTCUT.md`
- `spec/wip/unit_032/UI_LOCALIZATION_FOUNDATION.md`
- `spec/wip/unit_035/INLINE_KEY_MAPPING.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| keyboard を評価する | main window focused、dialog なし、pointer capture off | key press / release を保持し、keyboard binding を frame へ反映する | 未接続でも preview する |
| mouse を無視する | pointer capture off の mouse event / Raw Input | mouse binding、delta、gyroを変更しない | UI click は通常配送する |
| pointer capture を開始する | focused operational state、toggle action | exclusive mouse backend を開始し、mouse epoch を更新する | keyboard state は clear しない |
| pointer capture を解除する | pointer capture on、`F4` / toolbar | mouse button、delta、resampler、hook を解除する | keyboard held state は維持する |
| 全入力を解除する | focus loss、dialog open、shutdown | key / mouse / delta / pose を clear し、neutral frame を発行する | pointer capture も解除する |
| HOME の既定を作る | new settings | `KEY:F1 → BUTTON:HOME` | Escape は dialog / remap cancel に使える |
| release key を予約する | `F4` を binding へ設定 | editor validation で拒否し、UI は local action conflict を表示する | F12 は許可する |
| legacy default を移行する | exact legacy HOME と F12 release defaults | HOME F1、release F4 に置換する | custom profile / custom shortcut は保持する |
| runtime safety を判定する | keyboard active、pointer capture off、connected | keyboard frame の watchdog を有効に保つ | pointer flag と operational input flagを混同しない |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-skipped | focused operational stateではpointer capture offでもkeyboard bindingを評価し、mouse sourceはneutralのままとなる | new / regression | unit | publisher 26件green。既存callerのcombined boundaryを保ち、pointer指定時だけkeyboard-only評価するため追加の構造変更なし |
| refactor-skipped | pointer capture開始前後で保持keyboard入力を維持し、mouse buttonとrelative motionだけを追加評価する | new / regression | integration | 43件green。operational propertyとmouse-only clearで責務が明確なため追加の構造変更なし |
| todo | F4またはtoolbarでpointer captureを解除するとmouse stateだけが消え、保持keyboard bindingは次frameにも残る | new / edge | integration | F4 eventはmappingへ流さない |
| todo | focus loss、dialog、shutdownはpointer stateに関係なく全入力とposeをneutralizeする | regression | integration | safety boundaryは縮小しない |
| todo | built-in defaultはHOME=F1、release=F4となり、exact legacy defaultsだけを移行してcustom値を保持する | new / regression | unit | schema v1 migration fixtureを追加する |
| todo | F4は新規bindingを拒否し、F12は通常bindingとして保存・評価できる | regression | unit / integration | hard-coded F12 validationを除去する |
| todo | toolbar、status、previewはkeyboard activityではなくpointer captureのon/offを表示する | new / regression | unit / integration | unit_032後は英語source textを使う |
| todo | Windowsの通常描画と実mouseでF4解除後に外部windowへmouseが配送され、keyboard mappingは継続する | new | manual | `$inspect-gui-states` とWindows手動受入を分ける |

## 7. 設計メモ

`capture_active` という1つの bool では、runtimeへframeを送る条件と排他mouseの状態を表現できない。application state、publisher評価引数、preview modelには operational input と pointer capture を区別できる値を持たせる。名称は実装時に確定してよいが、1つの flag を再解釈して二重の意味を残さない。

pointer capture解除はmouse保持と未消費deltaを消去する。keyboard保持を消すのはfocus loss、dialog、shutdownなど、keyboard routing自体を停止する境界に限定する。設定画面では標準Widgetとremap入力を優先するため、「常時keyboard」はmain operational state内の契約である。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/application/state.py` | modify | operational input と pointer capture の状態表現 |
| `src/demi/application/coordinator.py` | modify | mouse-only capture lifecycle と全入力neutralization |
| `src/demi/domain/controller.py` | modify | operational input と pointer capture を分離したframe状態 |
| `src/demi/domain/settings.py` | modify | F4 release default とlocal action名称の整理 |
| `src/demi/domain/mapping.py` | modify | HOME F1 default |
| `src/demi/config/codec.py` | modify | legacy defaultの限定移行 |
| `src/demi/application/settings_editor.py` | modify | reserved F4 と F12許可 |
| `src/demi/input/qt_adapter.py` | modify | operational keyboard、captured mouse、F4 priority |
| `src/demi/input/mapper.py` | modify | source種類ごとの有効条件 |
| `src/demi/input/publisher.py` | modify | operational input と pointer capture のframe生成 |
| `src/demi/ui/main_window.py` | modify | pointer backend とfocus/dialog境界 |
| `src/demi/ui/toolbar.py` | modify | mouse capture action |
| `src/demi/ui/status_bar.py` | modify | mouse capture state表示 |
| `src/demi/ui/controller_preview.py` | modify | pointer capture flag表示 |
| `tests/unit/**` | modify | mapping、settings、publisher、coordinator回帰 |
| `tests/integration/ui/**` | modify | F4、focus、dialog、toolbar、Windows capture |
| `spec/initial/*.md` | modify | input mode、shortcut、requirements、testing、UI |
| `spec/wip/unit_033/POINTER_CAPTURE_AND_KEYBOARD_ROUTING.md` | new | 作業境界と検証記録 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/unit/test_documentation.py tests/unit/test_work_unit_records.py` | pass | 3 passed、仕様作成時の文書構造を確認 |
| `uv run pytest -p no:cacheprovider tests/unit/input/test_publisher.py -q` | pass | 26 passed。pointer capture offで`KEY:F`だけを評価し、mouse buttonとmotionをneutralに維持 |
| `uv run ruff check src/demi/input/publisher.py tests/unit/input/test_publisher.py` | pass | 指摘なし |
| `uv run ty check --no-progress` | pass | 型エラーなし |
| `uv run pytest -p no:cacheprovider tests/integration/input/test_pointer_capture_routing.py tests/unit/application/test_coordinator.py tests/unit/input/test_publisher.py tests/unit/input/test_physical_input.py -q` | pass | 43 passed。pointer開始前後のF保持、開始後のmouse buttonとrelative motion追加を確認 |
| `uv run ruff check src/demi/domain/physical_input.py src/demi/input/publisher.py src/demi/application/coordinator.py tests/integration/input/test_pointer_capture_routing.py tests/unit/input/test_publisher.py tests/unit/input/test_physical_input.py` | pass | 指摘なし |
| `uv run pytest tests/unit/input tests/unit/application tests/unit/config tests/unit/domain` | not run | 実装前の仕様作成段階 |
| `uv run pytest tests/integration/ui` | not run | keyboard / pointer state実装後に実行する |
| 標準 gate / `uv build` | not run | settings互換とframe契約変更のため実装時に必須 |
| Windows exclusive mouse手動受入 | not run | F4、keyboard継続、外部mouse配送を確認する |

## 10. 先送り事項

- pointer capture toggle の既定 `Ctrl+C` がcopy操作と競合する問題は、local action一覧全体を見直す別 unit で扱う。
- background keyboard、global shortcut、focus外入力は安全性とOS差が大きいため対象外を維持する。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を作成した
- [x] 実装検証が未実行である理由を記録した
- [x] settings / package gate を検証計画へ含めた
- [ ] operational keyboard と pointer capture を別状態にした
- [ ] HOME F1、release F4、F12許可の互換移行を確認した
- [ ] Windows実mouseで安全解除を確認した
