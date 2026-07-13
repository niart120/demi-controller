# UI 全面再設計

## 1. 位置付け

このディレクトリは、Project_Demi の GUI を pyglet ベースの独自実装から
PySide6 / Qt Widgets へ全面移行するための設計パッケージである。

初期設計の正本は引き続き `spec/initial/` とする。ただし、UI 再設計の目標状態について
`spec/initial/` の pyglet 前提とこのディレクトリが競合する場合、このディレクトリに記録した
採用判断を移行作業の入力とする。実装開始時に、各マイルストーンの作業仕様を
`spec/wip/unit_XXX` へ作成し、関連する `spec/initial/` を同じ変更内で更新する。

この設計パッケージ自体は完了済み実装を示さない。記載する実装、試験、OS 別挙動は、
各マイルストーンの検証が完了するまで未検証である。

## 2. 採用判断

| 項目 | 判断 |
|---|---|
| GUI ライブラリ | PySide6 |
| UI 方式 | Qt Widgets |
| QML | 採用しない |
| 移行方式 | 旧 UI を先に一括撤去し、PySide6 で積み直す |
| 旧 UI 互換層 | 作らない |
| pyglet | runtime dependency と production code から削除する |
| 対象 OS | Windows、macOS、Linux |
| 単体配布 | PyInstaller 対応を UI 機能移行より後に扱う |
| ドメイン・接続処理 | 現行の framework 非依存部分を維持する |

Qt Widgets を選ぶ理由は、ツールバー、状態バー、設定ダイアログ、色選択、選択リスト、
フォーム、ショートカット入力などを既存部品で構成できるためである。現在の
`src/demi/ui/dialogs.py` と `src/demi/ui/window.py` が担う描画、座標計算、当たり判定、
フォーカス管理をアプリケーション固有コードとして維持しない。

## 3. 必須成果

- `src/demi/ui` の現行実装を一括削除し、PySide6 前提の UI として新規に構成する。
- `src/demi/input/pyglet_backend.py` を削除する。
- `pyproject.toml` と `uv.lock` から pyglet を削除し、PySide6 を追加する。
- `demi.app` から pyglet 具象型と旧 UI 表示型への依存を除く。
- Qt の標準部品でツールバー、状態バー、設定ダイアログを実装する。
- `ControllerFrame` を入力としてコントローラー状態を描画する Qt widget を実装する。
- キー、マウス、フォーカス、捕捉解除を Qt 境界から application 層へ渡す。
- worker event を Qt 主スレッドで処理する。
- 関連する初期設計、試験方針、診断情報、利用手順を PySide6 前提へ更新する。

## 4. 文書一覧

| 文書 | 内容 |
|---|---|
| `CURRENT_UI_REMOVAL.md` | 現行 UI の依存監査、削除対象、維持する境界 |
| `PYSIDE6_UI_DESIGN.md` | PySide6 / Qt Widgets を使う目標構造と画面設計 |
| `RELATIVE_MOUSE_INPUT.md` | `QAbstractNativeEventFilter`、Win32 Raw Input、GLFW の比較と採用判断 |
| `MILESTONES.md` | 撤去先行の実装順、TDD Test List、検証と完了条件 |

## 5. 対象範囲

- GUI event loop、window、toolbar、status bar、dialog、controller preview の置換
- keyboard、mouse、focus event の Qt 境界への置換
- GUI 主スレッドと controller worker の event delivery の置換
- UI に直接依存する application composition の整理
- pyglet runtime dependency と現行 UI test の削除
- PySide6 のライセンス表示と OS 可搬性に必要な設計
- CLI から同じ GUI を起動する既存契約の復旧

## 6. 対象外

- swbt-python、Bumble、Bluetooth 接続方式の変更
- `ControllerFrame`、入力マッピング、設定スキーマの意味変更
- コントローラー画像や公式ロゴの導入
- QML、Qt Quick、Qt WebEngine の導入
- Web UI、Electron、ブラウザー埋め込み
- PyInstaller one-file artifact の完成と配布サイズ最適化
- OS の raw input API を使う新規 backend の実装

PyInstaller 固有の pyglet 参照は依存撤去時に削除する。ただし、PySide6 を含む単体配布の
成立、起動時間、配布サイズ、署名、各 OS の plugin 収集は後続作業とする。

## 7. 事実と未検証事項

### 7.1 確認済みの事実

- 現行 runtime dependency は `pyglet>=2.1,<2.2` である。
- UI 描画、イベントループ、時計、入力捕捉、キー・マウス定数は pyglet に依存している。
- ツールバー、状態バー、設定モーダルは座標と当たり判定を含む独自実装である。
- domain、controller、config、主要な input mapping は pyglet 具象型を持たない。
- CI は Windows、macOS、Linux と Python 3.12、3.13 の組合せを持つ。
- PyInstaller の standalone build は現行 pyglet 構成を前提にしている。

### 7.2 未検証

- 採用する PySide6 6.x の版範囲と `ty` の型検査結果
- Qt の offscreen platform を使う CI の安定性
- Qt event から得られる相対マウス値と OS ごとの差
- Windows、macOS、Linux の実 display、DPI、font、mouse capture
- PySide6 を含む standalone artifact の起動と配布サイズ
- 配布形態に応じた LGPLv3 の具体的な遵守方法

ライセンス欄は技術上の配布要件を洗い出すための記録であり、法的判断を完了した記録ではない。

## 8. 設計文書チェックリスト

- [x] 現行 UI の撤去対象と維持する境界を記録した。
- [x] PySide6 / Qt Widgets を前提に画面、入力、スレッド境界を再設計した。
- [x] 旧 UI を先に一括撤去する移行順を記録した。
- [x] 相対マウス入力方式を比較し、GLFW を不採用とした根拠を記録した。
- [x] 振る舞いベースの TDD Test List を作成した。
- [x] PyInstaller 対応を後続へ分離した。
- [x] 未検証事項とライセンス確認事項を記録した。
- [x] 文書検査の実行結果を `MILESTONES.md` に記録した。
