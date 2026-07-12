# Project Guide

## Purpose

A desktop application that converts PC keyboard and mouse inputs into virtual Pro Controller inputs and sends Bluetooth HID inputs to the target device.

## Source Of Truth

- `AGENTS.md`: repo-local operating instructions
- `SKILLS.md`: repo-local skill index
- `spec/initial`: standing project guidance
- `spec/wip`: active work units
- `spec/complete`: completed work records
- `.github/PULL_REQUEST_TEMPLATE.md`: required PR evidence

## Quality Gate

Default local gate:

```powershell
uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
uv run pytest tests/unit
uv build
git diff --check
```

Broaden the gate when a change touches packaging, CI, public APIs, release
behavior, or user-facing documentation.
