# PySide6 UI 設計

## 1. 目的

Qt Widgets の提供部品を利用し、Project_Demi 固有の UI 実装を controller preview と
application action の接続に限定する。通常の desktop control、layout、focus、keyboard
navigation、dialog lifecycle は Qt に任せる。

## 2. 設計原則

- `QMainWindow` を main window の唯一の所有者にする。
- toolbar、status bar、dialog、form、list、color selection は Qt Widgets を使う。
- 独自描画は `ControllerPreviewWidget` の `paintEvent()` に閉じ込める。
- Qt object は GUI 主スレッドだけで生成・更新する。
- domain、controller、config は PySide6 を import しない。
- controller worker から GUI へは immutable `RuntimeEvent` を渡す。
- UI から application 層へは意味のある action を渡し、widget を渡さない。
- 設定 dialog 表示中の入力 event を controller mapping へ流さない。
- 入力評価の8ミリ秒周期と表示の最大60 Hzを別の timer として扱う。
- `QApplication` は CLI の GUI 起動時だけ生成し、`--version` と module import では生成しない。

## 3. 目標構造

```text
demi.cli
  -> demi.app.run_application()
       -> SettingsRepository.load()
       -> ControllerRuntime(QtRuntimeEventBridge).start()
       -> InputPublisher
       -> CaptureCoordinator(PointerCapturePort)
       -> QApplication
       -> MainWindow
            ├── MainToolBar
            ├── ControllerPreviewWidget
            ├── QStatusBar
            └── settings dialogs
       -> QApplication.exec()

controller worker
  -> QtRuntimeEventBridge.emit(RuntimeEvent)
  -> queued Qt signal
  -> GUI main thread
  -> ApplicationSession.handle_runtime_event()
  -> MainWindow.refresh()

Qt key/mouse/focus event
  -> QtInputAdapter
  -> CaptureCoordinator / PhysicalInputState
  -> QTimer 8 ms
  -> InputPublisher.publish()
  -> ControllerRuntime.offer_frame()
  -> ControllerPreviewWidget.set_frame()
```

## 4. module 構成

PySide6 版は次の責務で分割する。実装中にファイルを統合する場合も、application state、
Qt object、入力変換、独自描画の責務は混在させない。

| module / class | 責務 |
|---|---|
| `demi.ui.application.QtApplicationRunner` | `QApplication` の生成、event loop、終了 status |
| `demi.ui.main_window.MainWindow` | window ownership、部品配置、action接続、表示同期 |
| `demi.ui.controller_preview.ControllerPreviewWidget` | `ControllerFrame` と色から controller を描画 |
| `demi.ui.input_adapter.QtInputAdapter` | Qt key/mouse/focus event を正規化して capture 境界へ渡す |
| `demi.ui.event_bridge.QtRuntimeEventBridge` | worker event を queued signal で GUI 主スレッドへ渡す |
| `demi.ui.dialogs.MappingDialog` | binding一覧、取得、反転、重複警告、保存・取消 |
| `demi.ui.dialogs.ConnectionDialog` | adapter一覧、再検索、接続設定、pairing確認 |
| `demi.ui.dialogs.ControllerColorsDialog` | 4色の編集、preview、保存、再接続選択 |
| `demi.application.ui_state.ApplicationUiSnapshot` | Qt 型を含まない main window の表示 snapshot |

旧 UI の class 名を維持することを目的にしない。`Toolbar`、`StatusBar`、`ModalRenderer` の
wrapper は作らず、Qt の object を `MainWindow` が所有する。

## 5. main window

`QMainWindow` の標準領域を使う。

```text
QMainWindow
├── QToolBar
│   ├── connection state label
│   ├── connection QAction
│   ├── capture QAction
│   ├── mapping QAction
│   ├── connection settings QAction
│   └── colors QAction
├── ControllerPreviewWidget
└── QStatusBar
```

### 5.1 toolbar

- `QToolBar` と `QAction` を使う。
- 接続状態は色だけでなく文字で示す。
- busy state では該当 action を無効にする。
- capture action は IDLE と CAPTURED で表示を切り替える。
- 設定 action は dialog 表示中と shutdown 中に無効にする。
- action の座標計算と独自 hit test は実装しない。

### 5.2 status bar

- `QStatusBar` と複数の `QLabel` を使う。
- adapter、connection、capture、warning/error を別領域として更新する。
- プレビューのみの状態と入力評価間隔を表示する。
- warning/error は省略によって意味が失われない文字列を使い、色だけに依存しない。

### 5.3 controller preview

- `QWidget` を継承し、`paintEvent()` で `QPainter` を使う。
- 入力は完全な `ControllerFrame` と `ControllerColorSettings` に限定する。
- body、button、stick、IMU、capture overlay を描画する。
- frame 更新時は値を保存して `update()` を要求し、同期的な再描画を強制しない。
- paint event 内で domain state、runtime、settings file を更新しない。
- 公式画像、ロゴ、製品外観の複製を使わない。

## 6. dialog

### 6.1 共通

- 各設定画面は `QDialog` とする。
- 保存には `QDialogButtonBox.Save`、取消には `QDialogButtonBox.Cancel` を使う。
- draft は既存 `SettingsEditor` と `SettingsModalController` が所有する。
- widget の値を直接永続化せず、application action を経て検証済み settings を保存する。
- validation error では dialog を閉じず、該当 control と説明を表示する。
- dialog を閉じても capture を自動再開しない。
- native modal event loop の多重利用を避け、controller worker を停止させない。

### 6.2 mapping dialog

- `QTableView` または `QTreeView` で target、source、反転、競合を表示する。
- binding capture は明示操作後の次の key または mouse button だけを受け取る。
- Qt key event は既存の `KeySource` 語彙へ変換し、Qt enum 値やローカライズ済み文字列を
  設定へ保存しない。現行語彙と一致しない key は明示的な変換表と設定 migration で扱う。
- `F12` は固定の capture release とし、binding target にできない。
- 重複は保存前に表示し、確定か取消を選べる。
- 反転は checkable control と文字で示す。

### 6.3 connection dialog

- adapter は `QComboBox` または model/view control で選ぶ。
- 再検索中も GUI event loop を塞がない。
- adapter が0件なら接続とpairingを無効にし、必要な機材を示す。
- 保存済み adapter が見つからなくても別候補を自動選択しない。
- pairing は別の確認 dialog を通して開始する。

### 6.4 controller colors dialog

- 4色を個別の control と `QColorDialog` で編集する。
- `#RRGGBB` を表示し、domain validation を通らない値を保存しない。
- preview は draft の色で更新し、取消時は保存済み色へ戻す。
- 接続中の保存後は、後で反映するか再接続するかを明示的に選択する。

## 7. input と pointer capture

Qt event を domain source へ変換する具象 adapter を1か所に置く。

| Qt event | application behavior |
|---|---|
| key press / release | 正規化した `KeySource` の保持状態を更新 |
| mouse press / release | 正規化した mouse source の保持状態を更新 |
| mouse move | capture 中だけ delta を蓄積 |
| focus out / deactivate | capture 解除、入力 clear、neutral frame |
| F12 | widget focus に関係なく capture 解除 |
| close event | ordered shutdown を一度だけ要求 |

`CaptureCoordinator.WindowPort.set_exclusive_mouse()` は pyglet の名前を含むため、
`PointerCapturePort.set_pointer_capture(enabled)` のような framework 非依存の契約へ変更する。
Qt 側は mouse grab、cursor visibility、OS別の相対移動量取得を具象実装する。Windows の
第一実装は `QAbstractNativeEventFilter` で `WM_INPUT` を受ける Win32 Raw Input とする。
GLFW は Qt window に入力 mode を取り付けられず、別 event loop と window ownership が必要に
なるため採用しない。詳細は `RELATIVE_MOUSE_INPUT.md` を正本とする。

Qt の通常 mouse event が OS 加速前の raw delta を保証するとは扱わない。画面端を越える継続入力、
OS ショートカット、DPI、複数モニターを実機で確認する。raw backend を実装していない OS では、
補正後の相対値であることを UI と診断情報に明示する。

## 8. timer と thread

- input evaluation は `Qt.TimerType.PreciseTimer` を指定した `QTimer` で8ミリ秒を目標にする。
- controller preview の更新要求は最大60 Hzに制限する。
- timer callback は入力評価、最新frameの通知、再描画要求だけを行う。
- Bluetooth I/O、adapter列挙、接続、切断をGUI threadで実行しない。
- runtime event は Qt queued connection で `ApplicationSession` の処理へ渡す。
- shutdown 後に timer と signal receiver が残らないよう、所有関係を `QObject` parentで固定する。

8ミリ秒は目標周期であり、desktop OS 上の実時間保証ではない。平均値、95、99パーセンタイルと
250ミリ秒 watchdog の誤発火を実測する。

## 9. application 境界

現行 `ApplicationSession` は `ControllerView` と `StatusBar` を直接受け取るため、UI framework
非依存になっていない。再設計では `ApplicationSession` から両方の引数を除く。

`ApplicationSession` は settings、presentation、dialog、capture state から Qt 型を含まない
`ApplicationUiSnapshot` を返す。GUI action または runtime event の処理後、Qt adapter が
`MainWindow.refresh(snapshot)` を呼ぶ。最新 `ControllerFrame` は入力評価時に
`ControllerPreviewWidget.set_frame()` へ別経路で渡す。

Qt widget 型や `QColor` を `ApplicationSession` へ注入してはならない。保存値は引き続き
`ControllerColorSettings`、`WindowSettings` などの domain 型で渡す。

## 10. test 方針

- application、domain、input mapping は `QApplication` なしで単体試験する。
- Qt widget test は process 内に1つだけ `QApplication` fixture を作る。
- CI の widget test は Qt の offscreen platform で実行可能か検証する。
- GUI test は widget の公開状態、signal、action、model を確認し、pixel 完全一致を主判定にしない。
- controller preview は frame から描画 model への変換を純粋関数として試験する。
- keyboard、mouse、focus、close は Qt event を送り、外から観測できる application state を確認する。
- worker event は GUI thread で処理されたことを thread id と状態変化で確認する。
- 実 display、pointer capture、DPI、複数モニターは OS 別 manual acceptance とする。

## 11. ライセンスと可搬性

PySide6 は LGPLv3 / GPLv3 / commercial license で提供される。Project_Demi では LGPLv3 で
利用できる Qt module に限定し、少なくとも `QtCore`、`QtGui`、`QtWidgets` の範囲から始める。
GPL のみの追加 module を根拠なく導入しない。

実装時に次を確認する。

- PySide6 と同梱 Qt module のライセンスファイル
- Qt に含まれる third-party component の notice
- 配布物で利用者がライセンス文書へ到達できること
- LGPLv3 の library replacement を妨げない配布方法
- 改変した LGPL component がある場合の対応

Windows、macOS、Linux は同一 source から各 OS 上で個別に検証する。Qt の採用だけを根拠に
3 OS 対応済みとは記録しない。source 実行、widget test、実 display、単体配布を別々の証拠とする。

## 12. PyInstaller の扱い

PyInstaller 対応は UI 機能移行の完了条件から外す。ただし、旧 pyglet の収集設定は依存撤去時に
削除し、誤った artifact を release しない。

後続の packaging work unit で次を扱う。

- PySide6 / Qt plugin、DLL、framework、license の収集
- one-file と one-folder の比較
- 起動時間と配布サイズ
- Windows、macOS、Linux の clean environment GUI smoke
- macOS app bundle、署名、権限
- package workflow と release gate の復旧

## 13. 外部仕様の参照先

- [Qt for Python](https://doc.qt.io/qtforpython-6/)
- [Qt Widgets](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/)
- [Qt licensing](https://doc.qt.io/qt-6/licensing.html)
- [Qt for Python と PyInstaller](https://doc.qt.io/qtforpython-6/deployment/deployment-pyinstaller.html)
