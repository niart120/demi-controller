# Project_Demi

A desktop application that converts PC keyboard and mouse inputs into virtual Pro Controller inputs and sends Bluetooth HID inputs to the target device.

## 起動

Python 3.12 以上と `uv` を用意して、開発環境から GUI を起動する。

```powershell
uv sync --dev
uv run demi
```

`uv run python -m demi` と `uv run project-demi` も同じ PySide6 / Qt Widgets GUI を起動する。GUIはコントローラー入力のプレビュー、フォーカス中のキーボード / マウス入力捕捉、キー割り当て・接続・色の設定ダイアログ、接続と新規ペアリングの操作を提供する。入力捕捉は明示操作で開始し、`F12` またはフォーカス喪失で解除される。

メインウィンドウの最小サイズは `800 x 520` である。コントローラープレビューは中央の `8:5` 領域へ収まり、横長では左右、縦長では上下が背景余白になる。画面比を変えてもフェイスボタン、十字キー、スティックは円形を保つ。

確認済みの配布形態はソース一式と `uv build` で生成した wheel である。Windows 用の単体配布物は提供していない。Bluetoothアダプターと対象機器を使う受入試験の状況は [hardware test log](spec/hardware-test-log.md) を参照する。

ライセンスと third-party notice は、ソース一式では [LICENSE](LICENSE) と [license inventory](packaging/LICENSES.md) を参照する。wheel をインストールした環境では `demi/THIRD_PARTY_NOTICES.md` に Project_Demi、PySide6、Qt の案内を含める。

表示を開かずに配布バージョンだけ確認するには、次を実行する。

```powershell
uv run demi --version
```

## 開発

```powershell
uv sync --dev
uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
uv run pytest tests/unit
uv run pytest tests/integration
uv build
git diff --check
```

依存やパッケージメタデータを変更したら `uv lock` を実行し、`uv.lock` を commit する。

リリース前のパッケージ確認:

```powershell
uv run twine check --strict dist\*
```
