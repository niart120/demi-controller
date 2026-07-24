# UI設計

## 1. 方針

Project_DemiのUIは、ゲーム画面ではなく入力装置の状態表示と設定に限定する。PySide6のQt Widgetsを使い、入力・設定・終了の操作は標準部品の契約に従う。独自部品はcontroller previewの描画に限定する。

### 1.1 表示言語

利用者向け文言は英語を翻訳元とし、`QObject.tr()`または`QCoreApplication.translate()`を通す。既定表示は英語とする。`ui.language = "ja"`では、アプリ用catalogとQt標準catalogをWidget生成前に読み込む。

どちらかのcatalogを読み込めない場合は一部だけ日本語にせず、両方を英語へ戻す。toolbar、status bar、設定ダイアログ、通知、安全上のerror文言を翻訳対象とする。binding、diagnostic level、TOML key、ログのcanonical値は翻訳しない。

## 2. メインウィンドウ

既定サイズ:

```text
幅 960 px
高さ 640 px
最小 800 x 520 px
```

構成:

```text
┌─────────────────────────────────────────────────────────────┐
│ [接続/切断] [入力開始/停止]  [設定 ▾]                    │ 52
├─────────────────────────────────────────────────────────────┤
│                                                             │
│              ControllerPreviewWidget                        │
│                                                             │
│        L/ZL                                      R/ZR        │
│             left stick      A/B/X/Y                          │
│             d-pad           right stick                     │
│                                                             │
│       gyro X/Y/Z arcs · accel X/Y/Z signed vectors           │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│ connection | warning/error       adapter | capture | preview │ 28
└─────────────────────────────────────────────────────────────┘
```

`QMainWindow` の標準領域へ固定 `QToolBar`、中央の `ControllerPreviewWidget`、`QStatusBar` を配置する。中央表示は残り領域へ拡大する。状態バーは接続状態と通知を左側、アダプター、捕捉、ポインター、送信状態を右側に置く。

## 3. ツールバー

ツールバーは `QToolBar`、`QAction`、`QToolButton`、`QMenu` で構成し、独自の座標判定を持たない。

左から次を配置する。

### 3.1 接続状態

表示:

- 未設定
- アダプターなし
- 切断
- 接続中
- 接続済み
- 切断中
- エラー

接続済みかどうかを色だけに依存せず、文字とアイコン形状で区別する。

### 3.2 接続・切断

状態に応じてラベルと処理を変える。

| 状態 | 操作 |
|---|---|
| 未設定 | 接続設定を開く |
| 切断 | 接続 |
| 接続中 | 無効 |
| 接続済み | 切断 |
| エラー | 再試行または設定 |

新規ペアリングは通常の接続ボタンに混ぜず、接続設定内の明示操作にする。

`Ctrl+Enter` はこの状態依存actionと同じ処理を実行する。マウス捕捉中も有効とし、接続操作だけを行う場合は捕捉を解除しない。主キーボードの Return とテンキー Enter の両方を受け付ける。

### 3.3 入力開始・停止

- `IDLE` では「入力開始」
- `CAPTURED` では「入力停止」
- 接続中でなくても可視化確認のため開始できる
- 設定ダイアログ表示中は無効
- フォーカスがない場合は無効

未接続で開始した場合、状態バーへ「プレビューのみ。対象機器へは送信していない」と表示する。

### 3.4 設定ボタン

`Settings` の子に次のactionを置く。

- `Connection`
- `Bindings`
- `Mouse`
- `Colors`

各actionは同じ設定ダイアログを開き、同名の設定tabを前面にする。actionとtabは同じ順序で表示する。

ダイアログを開く前にニュートラル化し、排他マウスを解除する。

## 4. ControllerPreviewWidget

### 4.1 図形

公式製品画像を直接使わず、Project_Demi独自の簡略図形を描く。

- 本体: 上側が幅広く中央下部が狭まるフェイスプレートと、左右外側から下方へ連続するグリップを持つ独自の簡略シルエット
- スティック: 外周円と可動ノブ
- A/B/X/Y: 円
- 十字キー: 内枠のない単一の十字パス。押下方向の腕だけを押下色で塗り分ける
- L/R/ZL/ZR: 上部の台形または丸角矩形
- Plus/Minus/Home/Capture: 小型記号
- 左スティックと十字キー: 左スティックを上、十字キーを左下に置く
- IMU: ジャイロ3軸の符号付き横棒と、3軸補助線上へ投影する1本の合成加速度ベクトル

### 4.2 描画方式

`ControllerPreviewWidget.paintEvent()` 内で `QPainter` を使う。入力フレーム受信と再描画要求を分離し、最大60 Hzのタイマーで `update()` を要求する。widget外へ `QPainter`、`QPen`、`QBrush` を保持せず、毎回の描画は最新 `ControllerFrame` と色設定から決定する。pixel完全一致を契約にせず、描画モデル、状態、更新頻度を試験する。

### 4.3 色

設定された4色を両方へ反映する。

- `body`
- `buttons`
- `left_grip`
- `right_grip`

GUIプレビューでは `body` を本体、`buttons` をボタンとスティック表面、`left_grip` / `right_grip` を本体下部の左右グリップ領域へ反映する。

ボタン押下は設定色の明度変更に依存せず、`#F4C95D` の塗り、`#FFF1A8` の太い輪郭、`#181818` の文字へ切り替える。未押下の塗りとのコントラスト比は3:1以上とする。スティック押下はノブへ別円を重ねず、スティック外周を同じ明色輪郭で示す。

ボタン内ラベルは操作要素の短辺の42%を基準に拡大し、11pxを下限とする。

### 4.4 状態表示

`ControllerPreviewWidget` は `ControllerFrame` だけを受け取る。Qt入力状態やswbt状態を直接参照しない。

表示更新:

- ボタン集合: 押下オーバーレイ
- スティック: 中心から半径内へ移動
- ジャイロ: 3軸を中央が0の横棒として並べ、負を左、正を右、角速度の大きさを棒の長さで示して表示用上限へclampする。操作ボタンと同じ円形を使わない。rad/sの値はtooltipとアクセシビリティ説明へ置く
- 加速度: 薄い3軸補助線と `+X` / `+Y` / `+Z` ラベルを表示し、3成分を模式投影した1本の矢印で符号と大きさを示して表示用上限へclampする。画面上では +Xを上、+Yを左下、+Zを右下とし、実機のトリガー方向、左方向、ボタン面外向きへそれぞれ対応させる。G単位の値はtooltipとアクセシビリティ説明へ置く
- マウス入力状態: コントローラー図の下、IMU表示の上へON/OFFとF5を表示する。ON/OFFは色だけに依存せず文字でも判別できる
- 切断: 半透明の「未接続」表示。ただしプレビューは継続

## 5. 設定ダイアログ

`QDialog`、`QTabWidget`、共通の `QDialogButtonBox` を使い、`Connection`、`Bindings`、`Mouse`、`Colors` を切り替える。入れ子のtabは作らない。4つのtabは1つのdraftを共有し、Saveは全tabの変更を1回で保存する。CancelとEscは全tabの変更を破棄し、色previewを保存値へ戻す。

### 5.1 Bindings tab

model/view controlを使い、binding rowやscroll領域を独自座標で描画しない。

### 5.2 構成

```text
┌──────────────────────────────────────────────┐
│ キー割り当て                     [×]         │
├──────────────────────────────────────────────┤
│ [割り当てを追加 ▾]          [標準に戻す]    │
│ 対象      入力    反転  操作    競合    削除   │
│ A         F       [ ]  [変更]           [🗑]  │
│ B         V       [ ]  [変更]           [🗑]  │
│ ...                                          │
│ 左スティック上 W        [変更]          [🗑]  │
│ 診断ジャイロY- I        [変更]          [🗑]  │
│ 診断加速度0G O          [変更]          [🗑]  │
│ ...                                          │
└──────────────────────────────────────────────┘
```

一覧は `QTableView` とmodelで表示し、Qt標準のスクロールを使う。canonical sourceはmodel roleへ保持し、表には利用者向けの入力名を表示する。

### 5.3 変更操作

- 対象行の「変更」をmouse、Enter、またはSpaceで実行する。
- 対象行の入力列へ入力待ち状態、操作列へ「取消」を表示する。表外の取得buttonと固定対象labelは設けない。
- 次のキーまたはマウスボタンを候補表示する。
- Inverted列はボタン割り当ての行だけチェック可能にする。スティック方向と診断targetの行にはチェックを表示しない。
- Remove列はQt標準のゴミ箱アイコンを中央表示し、tooltipで操作名を示す。同じ行だけを削除し、表外に選択行用の削除buttonを置かない。
- `Esc` は取消。Esc自体を割り当てる場合は「Escを割り当てる」補助操作を使う。
- 競合がある場合はsource、変更先、既存targetを列挙し、置換または取消を選ばせる。取消時はdraftを変更しない。
- `F5` はマウス入力切替用の予約キーであり、割り当て待受では候補にしない。`F4` と `F12` は通常の入力として扱う。
- Bindings以外のtabへ移動した場合は待受を中止し、非表示の待受状態を残さない。
- `Add binding` は `Buttons`、`Left stick`、`Right stick`、`Diagnostics` の分類menuを開く。targetを選ぶと未割り当て行を末尾へ追加する。
- 複数の `KEY:UNASSIGNED` は入力競合として扱わない。
- 保存前に設定全体を検証する。

### 5.4 IMU 診断target

`GYRO:X_POSITIVE`、`GYRO:X_NEGATIVE`、`GYRO:Y_NEGATIVE`、`GYRO:Y_POSITIVE`、`GYRO:Z_POSITIVE`、`GYRO:Z_NEGATIVE`、`IMU:NEUTRAL` は通常のbinding行として一覧へ表示する。利用者は通常の行操作で同じtargetの追加・削除とsource変更ができる。`IMU:NEUTRAL` は当該フレームをジャイロ `(0, 0, 0)`、加速度 `(0, 0, 1)` にする。

## 6. Mouse tab

同ダイアログ内の `QGroupBox` とform controlで次を編集する。

- 有効
- 水平感度
- 垂直感度
- 水平反転
- 垂直反転
- pitch上限

水平感度と垂直感度は、それぞれ `1.0` を標準とする独立倍率として表示する。一方を変更しても他方の表示値を再計算しない。数値入力には許容範囲と現在値を表示する。

## 7. Connection tab

`QGroupBox`、`QComboBox`、`QCheckBox` を使う。アプリケーション全体の設定を上、接続プロファイル操作を下の別groupで表示する。adapter 0件ではpairingを無効にし、Saveと再検索を有効に保つ。

項目:

```text
Global settings
  USB adapter: [usb:0 ... ▾] [Rescan]
  Reconnect on startup: [ ]
  Diagnostic log level: INFO

Controller profile
  Controller type: Pro Controller
  Status: Saved / Not saved
  [Pair new controller] [Delete profile]
```

Saveは設定だけを保存し、接続を開始しない。接続はメイン画面の接続actionで明示する。接続プロファイルのパスと30秒timeoutはUIへ表示しない。`Pair new controller` と `Delete profile` は確認画面を挟む。

確認文には次を含める。

- 対象機器側でコントローラー登録画面を開く必要がある。
- 専用USB Bluetoothアダプターが必要である。
- 既存の接続プロファイルを削除または置換する場合の影響。
- 処理中にUSBアダプターを抜かない。

## 8. Colors tab

`QColorDialog` と無文字の `QPushButton` を使う。各buttonは現在色で塗った色見本であり、mouse click、Enter、Spaceから標準色選択を開く。

4行の色設定を持つ。

```text
本体          [          ]
ボタン        [          ]
左グリップ    [          ]
右グリップ    [          ]
```

色見本の可視テキストと可視hexラベルは空にする。正確な現在値と操作説明はtooltipとaccessible descriptionへ置き、accessible nameには行のfield名を設定する。白、黒、ウィンドウ背景同色でも輪郭が消えないよう、fillとは独立したborder、hover、pressed、focus規則を使う。focusは色差だけに依存せず太いhighlight枠で示す。

pickerを確定した場合だけ対象色のdraft、色見本、local previewを更新する。picker取消では変更signalを発行しない。dialog取消は複数色のdraftを破棄して保存済みpreviewへ戻し、保存時の再接続確認は既存契約を維持する。custom color wheel、可視hex editor、preset、左右同色操作は0.1.0の対象外とする。

接続中に保存した場合:

```text
表示色は更新済みです。
対象機器へ反映するにはコントローラーを再接続します。
[後で] [再接続して反映]
```

## 9. 状態バー

`QStatusBar` と複数の `QLabel` を使い、adapter、connection、capture、warning/errorを分離して表示する。

常時表示する情報:

```text
Adapter: usb:0 | Connected | Input: Captured | 8 ms | warning
```

必要以上に内部プロトコル値を見せない。エラー時は短い要約を表示し、詳細はログ表示またはログファイルへの導線に分ける。

## 10. ダイアログ管理

同時に開ける `QDialog` は1つだけとする。設定ダイアログの保存と取消には共通の `QDialogButtonBox` の標準buttonを使う。ダイアログを開く処理はApplicationCoordinator経由とし、widgetが設定やruntime状態を直接変更しない。validation errorではダイアログを閉じず、draftと該当controlを保持する。

## 11. レイアウト

`QVBoxLayout`、`QFormLayout`、model/view control、size policyを使い、独自の座標計算やhit testで操作部品を配置しない。中央領域は割合と最小値を使う。

- プレビュー内容領域: `8:5` を中央領域へ最大内接
- 横長の余剰領域: 左右の背景余白
- 縦長の余剰領域: 上下の背景余白
- フェイスボタン、十字キー、スティック: 内容領域の短辺を基準に円形を保持
- 最小操作部品高さ: 32px
- ツールバーボタン間隔: 8px
- 文字が収まらない場合は省略せず、ウィンドウ最小幅を守る

高DPIではQtの論理寸法とdevice pixel ratioを混同しない。スクリーンショット基準試験はOSごとの差が大きいため、座標と状態の試験を中心にする。

## 12. キーボード操作

最低限の操作:

| キー | UI動作 |
|---|---|
| Tab / Shift+Tab | フォーカス移動 |
| Enter / Space | ボタン実行 |
| Esc | ダイアログ取消 |
| F5 | マウス入力切替 |
| F12 | 通常の割り当て入力 |
| Ctrl+Q | 終了 |
| Ctrl+C | マウス捕捉切替 |
| Ctrl+Enter | 接続・切断。主キーとテンキーの両方 |

UIフォーカスとコントローラー割り当ての競合は、入力モードの優先順位で解決する。

## 13. UI受入条件

- 800x520で主要操作が欠けない。
- 設定ダイアログを開いた瞬間にControllerPreviewWidgetがニュートラルを示す。
- 接続処理中もウィンドウ移動と再描画が止まらない。
- 60Hz描画中に入力評価の95パーセンタイル間隔が16ミリ秒を超えないことを診断モードで測定する。
- 色だけを見なくても、接続、捕捉、押下を判別できる。
- 英語または日本語の選択時に、アプリ固有文言とQt標準部品が同じ言語で表示される。
- 翻訳catalogを読み込めない場合も、言語が混在せず英語で操作を継続できる。
