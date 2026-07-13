# Project_Demi

A desktop application that converts PC keyboard and mouse inputs into virtual Pro Controller inputs and sends Bluetooth HID inputs to the target device.

## 起動

Python 3.12 以上と `uv` を用意して、開発環境から GUI を起動する。

```powershell
uv sync --dev
uv run demi
```

`uv run python -m demi` と `uv run project-demi` も同じ GUI を起動する。この版の GUI はウィンドウ状態の復元と安全な終了を提供する最小構成の画面であり、コントローラー入力のプレビュー、キーボード / マウス操作、設定画面、接続 / ペアリング操作は未実装である。Windows 用の単体配布物は提供していない。

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
