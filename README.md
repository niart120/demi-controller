# Project_Demi

A desktop application that converts PC keyboard and mouse inputs into virtual Pro Controller inputs and sends Bluetooth HID inputs to the target device.

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

## エージェント作業

このリポジトリは次を使う。

- `AGENTS.md`: リポジトリ内の常設指示
- `SKILLS.md`: リポジトリ内 skill の索引
- `spec/initial`: 継続的に参照するプロジェクト規約
- `spec/wip`: 作業中の作業単位
- `spec/complete`: 完了した作業記録
- `spec/dev-journal.md`: 小さい観測と先送り判断
- `.agents/skills`: 呼び出し可能なローカル手順

作業単位は小さく保つ。完了前に、事実、未検証事項、検証コマンド、結果を対象の仕様書に記録する。
