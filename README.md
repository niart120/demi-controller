# Project_Demi

A desktop application that converts PC keyboard and mouse inputs into virtual Pro Controller inputs and sends Bluetooth HID inputs to the target device.

## 起動

Python 3.12 以上と `uv` を用意して、開発環境から GUI を起動する。

```powershell
uv sync --dev
uv run demi
```

`uv run python -m demi` と `uv run project-demi` も同じ GUI を起動する。初回起動や USB Bluetooth アダプターが未接続の状態でも、コントローラー入力のプレビューと設定画面は開ける。接続や新規ペアリングには専用の USB Bluetooth アダプターと対象機器が必要になる。

Windows 用 standalone artifact の entry point は次である。

```powershell
.\dist\standalone\demi.exe
```

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
uv build
```

依存やパッケージメタデータを変更したら `uv lock` を実行し、`uv.lock` を commit する。

リリース前のパッケージ確認:

```powershell
uv run twine check --strict dist\*
```

standalone artifact の build と version smoke:

```powershell
uv run python packaging\build.py
uv run python packaging\smoke.py
```

生成先は `dist\standalone` です。Windows、macOS、Linux の artifact は対象 OS 上で個別に build します。
