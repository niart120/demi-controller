# Third-party notices

このファイルは、ビルドした wheel の `demi/THIRD_PARTY_NOTICES.md` として配布する。ソース一式ではこのパスと `packaging/LICENSES.md` を参照する。

## Project_Demi

Project_Demi 自体はリポジトリー直下の `LICENSE` に記載した MIT License で配布する。wheel では同じ本文を `demi_controller-<version>.dist-info/licenses/LICENSE` に含める。

## PySide6 と Qt

GUI 実行時には `PySide6` を使用する。`PySide6` をインストールすると、`PySide6_Essentials`、`PySide6_Addons`、`shiboken6` も解決される。Essentials と Addons は Qt の実行バイナリーを含む。

適用するライセンス選択と必要な通知は、実際に配布する PySide6 / Qt の版と利用形態で確認する。次の公式資料を参照する。

- [Qt for Python licenses](https://doc.qt.io/qtforpython-6/licenses.html)
- [Qt Licensing](https://doc.qt.io/qt-6/licensing.html)

インストール済みの各配布物が持つ版とライセンスファイルは、`importlib.metadata.distribution()` の `version`、`files`、`locate_file()` で確認できる。`*.dist-info/licenses/` にあるファイルだけで必要な通知が完結すると仮定しない。

## その他の実行時依存

`platformdirs`、`swbt-python`、`tomli-w` と、それらが解決する依存は、インストール済み配布物のメタデータとライセンスファイルを確認する。`uv.lock` は解決した版の記録であり、ライセンスの代替資料ではない。

この文書は third-party notice の到達経路を示す技術記録であり、法的適合の結論ではない。単体配布物に必要な Qt plugin、実行バイナリー、通知の同梱確認は milestone 7 の対象である。
