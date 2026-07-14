# Source and wheel license inventory

この文書は、ソース一式と wheel 利用者が Project_Demi、PySide6、Qt、その他の third-party notice へ到達するための索引である。ライセンスの適合性や利用形態の判断を完了したことは示さない。

## Project_Demi

- ソース一式: リポジトリー直下の `LICENSE`
- wheel: `demi_controller-<version>.dist-info/licenses/LICENSE`

## PySide6 と Qt

`PySide6` は GUI の直接依存であり、`PySide6_Essentials`、`PySide6_Addons`、`shiboken6` を解決する。Essentials と Addons は Qt の実行バイナリーを含む。

- source / wheel 共通の案内: `demi/THIRD_PARTY_NOTICES.md`
- 公式の third-party notices: [Qt for Python licenses](https://doc.qt.io/qtforpython-6/licenses.html)
- 公式のライセンス選択: [Qt Licensing](https://doc.qt.io/qt-6/licensing.html)
- インストール済み配布物: `importlib.metadata.distribution()` で版、`files`、`locate_file()` を確認する

配布物ごとの `*.dist-info/licenses/` を確認するが、そのディレクトリーだけで必要な通知が完結すると仮定しない。

## その他の実行時依存

`platformdirs`、`swbt-python`、`tomli-w` と解決済みの依存については、インストール済み配布物のメタデータとライセンスファイルを確認する。`uv.lock` は版の再現性を担保する記録であり、ライセンス本文の代替ではない。

## 単体配布

Windows、macOS、Linux 向けの単体配布物は現時点で提供していない。`packaging/build.py` による実行バイナリー、Qt plugin、通知の同梱確認は milestone 7 で扱う。この文書を単体配布のライセンス監査完了の根拠にしない。
