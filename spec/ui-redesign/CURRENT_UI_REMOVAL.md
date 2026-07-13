# 現行 UI 撤去仕様

## 1. 目的

pyglet を前提にした UI と入力境界を初手で一括撤去し、PySide6 実装へ旧構造を持ち込まない。
旧 UI を残したまま新 UI との状態同期や互換 wrapper を作る方式は採用しない。

## 2. 現行依存の監査結果

### 2.1 runtime dependency

| dependency | 現行用途 | 移行判断 |
|---|---|---|
| `pyglet>=2.1,<2.2` | window、event loop、clock、drawing、keyboard、mouse | 削除 |
| `platformdirs` | 設定、data、log path | 維持 |
| `swbt-python` | Bluetooth HID controller adapter | 維持 |
| `tomli-w` | TOML 設定保存 | 維持 |
| `PySide6` | 未導入 | 追加 |

### 2.2 production code

| path | 現行責務 | 判断 |
|---|---|---|
| `src/demi/ui/window.py` | window factory、event loop、clock、input dispatch、toolbar/dialog描画 | 削除 |
| `src/demi/ui/controller_view.py` | pyglet shapes と label による controller preview | 削除 |
| `src/demi/ui/dialogs.py` | 独自 modal、field layout、paging、hit test、drawing | 削除 |
| `src/demi/ui/toolbar.py` | toolbar model と座標付き control | 削除 |
| `src/demi/ui/status_bar.py` | status text model | 削除 |
| `src/demi/ui/event_bridge.py` | queue を周期的に drain する worker event bridge | 削除 |
| `src/demi/input/pyglet_backend.py` | pyglet key/mouse event の正規化 | 削除 |
| `src/demi/app.py` | pyglet window と UI 具象クラスの組み立て | PySide6 用に再構成 |

`src/demi/ui` はファイル単位で残すかを判断せず、package 内の現行実装をすべて削除する。
PySide6 版で同名概念が必要でも、旧クラスを継承せず、新しい責務と API で作成する。

### 2.3 test code

次の test は pyglet 実装の契約を固定しているため削除し、PySide6 の観測可能な振る舞いを
確認する test へ置き換える。

- `tests/unit/test_pyglet_import_boundary.py`
- `tests/unit/input/test_pyglet_backend.py`
- `tests/unit/ui/test_pyglet_application.py`
- pyglet の window、drawing、key code、mouse code を前提にする UI test
- `tests/unit/application/test_app.py` 内の pyglet 具象型 assertion
- `tests/integration/lifecycle/test_application_lifecycle.py` 内の pyglet GUI factory fixture

次の振る舞いはライブラリ固有 test と一緒に削除せず、PySide6 版の回帰 test へ移す。

- CLI から GUI runner を一度だけ起動する。
- 初回起動と adapter 不在でも main window を表示する。
- 8ミリ秒周期で入力を評価し、表示は最大60 Hzとする。
- F12 と focus loss で capture を解除し neutral frame を発行する。
- worker event は GUI 主スレッドで application state へ反映する。
- `ControllerFrame` の同じ値を runtime と preview が参照する。
- 設定 dialog 中の文字入力を controller mapping へ流さない。
- 終了時に capture、runtime、settings、window を定義済み順序で閉じる。

### 2.4 package、CI、文書

| path | 必要な変更 |
|---|---|
| `pyproject.toml` | pyglet 削除、PySide6 追加、`ui` marker 文言更新 |
| `uv.lock` | dependency lock 更新 |
| `packaging/build.py` | runtime package と `--collect-all pyglet` を削除 |
| `packaging/LICENSES.md` | pyglet を除き、PySide6 / Qt の扱いを後続配布仕様へ送る |
| `.github/workflows/ci.yml` | Qt test が display を要求しない構成を検証 |
| `.github/workflows/package.yml` | UI 機能移行中は release gate から外し、後続で再検証 |
| `README.md` | standalone 対応状況と起動手順を実装状態に合わせる |
| `spec/initial/*.md` | pyglet 固有要件、構造、周期、診断項目、試験方針を更新 |

`spec/complete/unit_004` などの完了済み作業仕様は、当時の実装事実を示す履歴なので
書き換えない。現行仕様の検索で過去記録を誤って有効な設計と解釈しないよう、
`spec/initial` とこの設計パッケージを現行判断の入口にする。

## 3. 維持する境界

次は pyglet に依存しないため、原則として振る舞いを維持する。

| boundary | 維持する内容 | UI 再設計で許す変更 |
|---|---|---|
| `demi.domain` | controller、mapping、settings、physical input の値 | import 整理のみ |
| `demi.controller` | command、event、runtime、swbt adapter | event sink の具象差替え |
| `demi.config` | path、codec、migration、repository | 変更なし |
| `InputPublisher` | 物理入力から同一 `ControllerFrame` を生成する | Qt timer からの呼出し接続 |
| `YawPitchModel` | mouse delta から IMU 値を生成する | 変更なし |
| `CaptureCoordinator` | capture state、epoch、neutralization | window port 名を framework 非依存にする |
| `ApplicationSession` | settings、runtime command、presentation の判断 | UI 具象型への直接依存を除く |
| `ApplicationShutdownCoordinator` | 終了順序と冪等性 | Qt close event との接続 |

## 4. 撤去後に禁止するもの

- production dependency としての pyglet
- production source 内の `import pyglet` と `from pyglet ...`
- `PygletApplication`、`PygletInputBackend`、`PygletWindowPort`
- pyglet の key symbol や mouse button 値を domain/configへ保存する処理
- 座標付き独自 toolbar button と dialog button の hit test
- 独自 text field、combo box、color picker、scroll、tab order
- worker thread から Qt widget を直接操作する処理
- PySide6 型を domain、controller、config へ持ち込む処理
- 旧 UI と新 UI を実行時設定で切り替える fallback

## 5. 撤去直後の状態

旧 UI 撤去と PySide6 最小 shell の完成は別マイルストーンとする。撤去直後は GUI 起動が
一時的に利用不能でもよい。ただし、次を守る。

- 撤去状態を release、tag、default branch の配布可能状態として扱わない。
- `demi --version` と package import は GUI dependency を import せず成功させる。
- domain、config、input mapping、controller runtime の機材不要 test を維持する。
- GUI 起動失敗を pyglet の欠落や import traceback として露出させない。
- 作業 branch 上で PySide6 最小 shell の復旧まで連続して進める。

この中間状態を長期互換状態として維持しない。PySide6 への移行全体が完了するまで、UI
再設計を完了済みの `spec/complete` へ移さない。

## 6. 撤去完了条件

- 本番ソースと現行テストから pyglet の import がなくなっている。
- `pyproject.toml` と `uv.lock` に pyglet 配布物がない。
- パッケージ作成処理に pyglet の収集指示がない。
- `src/demi/ui` に旧ファイルが残っていない。
- `ApplicationSession` が旧 `ControllerView` と `StatusBar` を型として参照しない。
- 過去の `spec/complete` を除き、現行文書に pyglet を採用する指示が残っていない。
- PySide6 実装へ移す回帰 test 項目が `MILESTONES.md` に記録されている。
