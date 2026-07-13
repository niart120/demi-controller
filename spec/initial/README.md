# Project_Demi 初期設計

作成日: 2026-07-10  
更新日: 2026-07-14
状態: 初期設計  
対象: 0.1.0  
正本: `spec/initial/`

## 1. 目的

Project_Demiは、PCのキーボードとマウスを仮想Pro Controller入力へ変換し、`swbt-python` を介して対象機器へBluetooth HID入力を送るデスクトップアプリケーションである。

既定のキー割り当て、マウスボタン割り当て、相対マウスからジャイロ角速度と姿勢整合した静的加速度への変換を提供する。入力状態はProject_Demi内部の型へ変換し、`swbt-python` の公開APIだけを通して送信する。独自の中間通信形式、シリアルポート、TCP中継は設けない。

## 2. 確定事項

| 項目 | 決定 |
|---|---|
| プロジェクト名 | `Project_Demi` |
| ルートパッケージ | `demi` |
| GUI・描画・入力 | PySide6 / Qt Widgets |
| Bluetooth HID | swbt-python 0.2系 |
| 初期コントローラー | Pro Controller |
| 初期主対象OS | Windows 11 |
| 移植対象 | macOS、Linux |
| 入力範囲 | フォーカス中のProject_Demiウィンドウ |
| 設定 | TOML、OS標準のユーザーディレクトリ |
| UI | コントローラー可視化、ツールバー、設定ダイアログ |
| 実行モデル | Qt GUIスレッド + asyncio接続ワーカー |
| 品質管理 | uv、ruff、ty、pytest |

## 3. 成果物の範囲

0.1.0では次を提供する。

- USB Bluetoothアダプターの列挙
- 保存済みボンド情報を使う再接続
- ユーザー操作による新規ペアリング
- 接続、切断、接続状態表示
- キーボード入力からボタン・左右スティックへの変換
- 排他マウスモードの相対移動からジャイロ角速度を生成し、同じ仮想pitchから静止時加速度を生成
- マウスボタンからコントローラーボタンへの変換
- コントローラーのリアルタイム可視化
- キー割り当て設定
- 接続設定
- 本体、ボタン、左右グリップの色設定
- 設定の保存、検証、スキーマ移行
- フォーカス喪失、停止、切断時のニュートラル復帰
- 診断ログと実機試験記録

## 4. 0.1.0で扱わないもの

- グローバルキーボード・マウスフック
- バックグラウンドでのゲーム操作
- 複数コントローラーの同時接続
- Joy-Con L/RおよびJoy-Conペア
- 振動、NFC、IR、LEDの任意制御
- マクロ、連射、スクリプト実行
- ネットワーク経由の入力
- OS固有Raw Inputの直接実装
- プラグイン機構
- 完全なテーマ編集
- 公式製品画像やロゴを複製したUI

これらは将来候補であり、0.1.0の内部APIを不必要に複雑化させない。

## 5. 設計原則

### 5.1 状態を先に作り、送信は境界で変換する

キーイベントごとに `press()` や `release()` を直接呼ばない。各時点の保持入力から完全な `ControllerFrame` を生成し、接続境界で `swbt.InputState` へ変換して `apply()` する。

これにより、同時押し、反対方向キー、フォーカス喪失、設定画面遷移で入力が残る問題を避ける。

### 5.2 GUIとBluetooth処理を分離する

Qtのevent loopはGUIスレッドに置く。`swbt-python` は専用スレッド上の `asyncio` イベントループで動かす。両者はコマンドと不変イベントだけで通信する。

### 5.3 安全側へ停止する

次の条件では必ず入力をニュートラルへ戻す。Project_Demiのニュートラルは、ボタン解放、スティック中央、ジャイロ0 rad/sに加え、水平なPro Controllerの静止状態を表す加速度 `(0, 0, +1) G` を含む。

- ウィンドウがフォーカスを失った
- マウス捕捉を解除した
- 設定画面を開いた
- Bluetooth接続が切れた
- UI更新が一定時間止まった
- 未処理例外が発生した
- アプリを終了した

### 5.4 入力反転をマッピング属性として扱う

押している間だけ対象を解除する入力は、特定のキーやボタンへ専用処理を設けず、任意のボタン割り当てに指定できる `inverted` 属性として表現する。判定は `source_active XOR inverted` とし、同じ対象への複数割り当ては各判定結果のORで集約する。

反転設定があっても、入力捕捉外、フォーカス喪失、切断、終了時は必ず完全なニュートラルにする。Project_Demiはジャイロをrad/s、加速度をGで保持し、raw化、丸め、範囲処理はswbt-pythonの公開APIへ委譲する。

### 5.5 外部型をドメインへ漏らさない

Qtの入力型、`swbt.Button`、`swbt.InputState` は、それぞれのアダプター内でだけ使う。設定、試験、入力変換の中心はProject_Demi独自の型で表現する。

## 6. 全体構成

```text
OS keyboard / mouse events
            │
            ▼
QtInputAdapter ──► PhysicalInputState
                              │
                              ▼
                        InputMapper
                              │
                              ▼
                       ControllerFrame
                        │             │
                        │             └──► ControllerPreviewWidget
                        ▼
                 ControllerRuntime
                 dedicated thread
                        │
                        ▼
                    SwbtAdapter
                        │
                        ▼
                   swbt-python
                        │
                        ▼
              dedicated USB Bluetooth
```

接続イベントは逆方向へ流れる。

```text
swbt-python
    │
    ▼
ControllerRuntimeEvent
    │ thread-safe dispatch
    ▼
ApplicationPresenter
    │
    ├──► Toolbar / dialogs
    └──► status bar / controller view
```

## 7. 文書

| 文書 | 内容 |
|---|---|
| `requirements.md` | 要件ID、受入条件 |
| `architecture.md` | 依存方向、ソース構成、スレッド |
| `input.md` | 入力取得、割り当て、ジャイロ |
| `ui.md` | 画面、描画、操作 |
| `swbt-integration.md` | 外部API境界、接続処理 |
| `configuration.md` | TOML、保存先、移行 |
| `lifecycle.md` | 状態遷移と異常終了 |
| `testing.md` | 自動・実機試験 |
| `roadmap.md` | 実装順序 |
| `risks.md` | リスクと未検証事項 |
| `naming.md` | 公開名、コード上の名称 |
| `appendix/aim-model.md` | YawPitchModelの選定理由と代替案。非規範 |

## 8. 外部事実とプロジェクト判断

| 区分 | 内容 |
|---|---|
| 外部事実 | swbt-python 0.2.0はPython 3.12以上を要求する |
| 外部事実 | swbt-pythonはProController、InputState、ControllerColors、アダプター列挙APIを公開する |
| 外部事実 | 実機接続にはBumbleが直接利用する専用USB Bluetoothアダプターが必要である |
| プロジェクト判断 | GUIはPySide6のQt Widgets、key/mouse event、Qt event loopを使う |
| プロジェクト判断 | Project_Demiの入力評価周期は8ミリ秒、描画目標は60Hzとする |
| プロジェクト判断 | マウスジャイロはYawPitchModelを使い、pitchを既定±75度に制限する。内部角度はラジアン、水平・垂直感度は独立した無次元倍率とする |
| プロジェクト判断 | ボタン割り当ては任意に反転でき、反転判定を特定の入力や対象へ直書きしない |
| 外部事実 | Pro Controllerおよび左Joy-Conの共通IMU正方向は、+Xがトリガー方向、+Yが左、+Zがボタン・スティック面から外向きである。右Joy-Conのraw Y/Zは逆向きである |
| プロジェクト判断 | ドメイン層はPro Controller基準の右手座標系を使い、水平静止時の加速度を `(0, 0, +1) G` とする |
| プロジェクト判断 | ジャイロ角速度はrad/s、加速度はGで保持し、raw変換はswbt-python issue #69/#70で追加される公開APIへ委譲する |
| プロジェクト判断 | swbt-pythonのオブジェクトは接続ワーカーだけが所有する |
| 未検証 | Qtの通常mouse eventが全OS・全マウスで未加速の相対値を返す保証はなく、OS別アダプターが必要である |
| 未検証 | 単体アプリ化後のBumble/libusbアクセスはOS別に実機確認が必要である |

## 9. 完了定義

0.1.0は、次をすべて満たした時点で完了とする。

- 品質ゲートが通る
- Windows 11の確認対象構成で、ペアリング、再接続、入力、切断が成功する
- フォーカス喪失、捕捉解除、強制的なUI停止相当の試験で、ジャイロ0かつ静的加速度1Gを含むニュートラルになる
- 設定破損時に安全な初期値で起動し、破損ファイルを保全する
- 入力可視化と実機入力が同じ `ControllerFrame` を使用する
- ボンド情報や機密診断値がログへ出ない
- 実機条件と結果が `spec/hardware-test-log.md` に残る
