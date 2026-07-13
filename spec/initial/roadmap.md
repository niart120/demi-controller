# 実装ロードマップ

各単位は `spec/wip/unit_XXX/` に要求、計画、結果を置く。単位をまたぐ大規模な先行実装を避ける。

## Unit 001: テンプレート初期化

成果:

- `agentic-python-project-template` から `Project_Demi` を生成
- 配布名 `project-demi`
- パッケージ `demi`
- Python 3.12
- uv、ruff、ty、pytest
- `spec/initial/` の配置
- CIの最小実行

完了条件:

```bash
uv sync --dev
uv run ruff check .
uv run ty check --no-progress
uv run pytest
uv run python -m demi --version
```

が機材なしで成功する。

## Unit 002: ドメイン型と設定

成果:

- ControllerFrame
- LogicalButton
- StickVector
- GyroRate
- AccelG
- AppSettings
- TOML codec、validation、repository
- platformdirs
- 組み込みプリセット

完了条件:

- 正常・破損・未知版の設定試験
- Defaultプロファイルと反転入力のfixture
- 外部ライブラリをimportしないdomain層

## Unit 003: 入力状態とマッピング

成果:

- PhysicalInputState
- キー・マウスソース正規化
- ボタン集約
- スティック合成
- YawPitchModel
- 8ミリ秒Publisher

完了条件:

- 反対方向、複数ソース、差分消費、resetの単体試験
- ラジアン毎秒の角速度生成
- 仮想pitchと整合する静的1G生成
- 捕捉外はジャイロ0・加速度+1Gのニュートラル

## Unit 004: pygletウィンドウと可視化

> 履歴注記: このunitは完了時のpyglet実装を示す。現行UIの採用判断と後続計画は `spec/ui-redesign/` およびunit_013以降を正本とする。

成果:

- メインウィンドウ
- ツールバー
- 状態バー
- ControllerView
- PygletInputBackend
- 入力開始・F12解除
- フォーカス喪失

接続はFakeControllerPortを使う。

完了条件:

- 800x520で操作可能
- 60Hz表示
- 入力状態と図が一致
- フォーカス喪失で即ニュートラル

## Unit 005: 接続ランタイム

成果:

- 専用スレッド
- asyncioイベントループ
- コマンドキュー
- 最新フレームスロット
- RuntimeEvent
- 250ミリ秒停止監視
- 偽SwbtAdapter

完了条件:

- スレッド競合試験
- 停止監視試験
- 遅延capture epoch破棄
- 終了後にタスクとスレッドが残らない

## Unit 006: swbt-pythonアダプター

成果:

- アダプター列挙
- ProController生成
- 再接続
- 新規ペアリング
- InputState変換
- `IMUFrame.gyro_rate()` による角速度変換
- `with_accel_g()` によるG単位加速度変換
- ControllerColors
- 切断
- 例外分類

完了条件:

- swbt-python issue #69/#70を取り込んだ版を固定
- 公開APIだけを使用し、ローカルなIMU raw変換を持たない
- 定常rest状態で0Gではなく `(0, 0, +1) G` を送る
- 契約試験
- `bumble` マーカー試験
- 機材なしの通常試験を壊さない

## Unit 007: 設定モーダル

成果:

- キー割り当て
- 接続設定
- 色設定
- 競合警告
- 原子的保存
- 破損復旧通知

完了条件:

- 全FR-010〜FR-014受入条件
- モーダル表示時ニュートラル
- 色変更の再接続導線

## Unit 008: 実機試験と安定化

成果:

- Windows 11実機試験
- 新規ペアリング
- 再接続
- 全主要入力
- ジャイロ調整
- アダプター抜去
- 終了安全性
- hardware test log

完了条件:

- 0.1.0対象構成で受入シナリオが通る
- 既知問題が文書化される
- 未検証OSを確認済みと誤記しない

## Unit 009: OS別移植確認

順序:

1. macOS
2. Linux

成果:

- 起動
- 設定
- pyglet入力
- 排他マウス
- アダプター列挙
- 可能な範囲の実機接続

Linuxで排他マウスがOSショートカットへ与える影響を記録する。未確認項目は実験的と表示する。

## Unit 010: パッケージング

候補は実装時に小さな比較を行い、PyInstallerまたはNuitkaの一方へ固定する。

成果:

- Windows単体アプリ
- macOSアプリ
- Linux配布物
- assets同梱
- ライセンス一覧
- 起動ログ
- バージョン情報

完了条件:

- 対象OS上で別々にビルド
- クリーン環境で起動
- アダプター列挙
- 設定保存
- 正常終了
- Bumble/libusb関連資源の不足がない

## リリース0.1.0

必須:

- Unit 001〜008
- Windows 11確認構成
- ソース実行
- 設計・試験記録
- ライセンスと非提携注記

0.1.1以降:

- OS別パッケージ
- macOS/Linuxの確認範囲拡大
- UI操作性修正
- ジャイロ調整プリセット

0.2候補:

- 追加入力バックエンド
- Joy-Con L/R
- プロファイルのインポート・エクスポート
- OS Raw Input
