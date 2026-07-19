---
name: docs-quality-review
description: "README、docs、公開 API docstring、spec、PR 本文、AGENTS.md、SKILLS.md の追加・更新・レビューで、利用者向け文言、完了条件、検証根拠、agent 向け情報の置き場所を確認する skill。ユーザが docs、ドキュメント、README、文章、文言、仕様書、PR body、公開 API 説明、agent guide の見直しを依頼したときに使う。"
---

# Docs Quality Review

文体の好みではなく、公開面の役割、完了条件、検証事実、未検証事項が読み手に誤って伝わらないかを確認する。

## 対象文書

最初に対象文書の役割を決める。

| 対象 | 役割 |
|---|---|
| `README.md` | 利用開始の入口。詳細な設計、agent 運用、作業履歴を置かない。 |
| `docs/` | 利用者向けの公開説明。現在の仕様、手順、制約を具体的に書く。 |
| public API docstring | 引数、戻り値、例外、状態変化、使用例を公開契約として書く。 |
| `spec/wip` / `spec/complete` | 対象範囲、対象外、TDD 状態、検証、先送り事項を残す作業記録。 |
| `spec/dev-journal.md` | 仕様化前の観測、未確定方針、実験的な支援範囲を短く置く。 |
| `AGENTS.md` / `SKILLS.md` | agent 向けの恒常ルール、呼び出し先、実行手順。 |
| PR body | 変更理由、論理変更単位、実行 command、結果、未実行理由の根拠。 |

## 確認規則

- README と公開 docs は利用者向けに書く。開発手順、agent 運用、作業中の都合は `AGENTS.md`、`SKILLS.md`、`spec/` へ移す。
- README は短い入口に保つ。長い説明、実機ログ、詳細な API 契約、環境 matrix は専用 docs へ移す。
- public API、package metadata、release の挙動を変更した場合は、docstring、README/docs、docs test を完了条件に含める。
- 対話内だけの表現を残さない。`前回`、`今回`、`一旦`、`上述`、`ユーザに言われたため` のような文脈依存語は repo に残る言葉へ直す。
- 事実、推論、提案、未検証を分ける。未実行の検証や外部仕様の推測を確認済みとして書かない。
- 完了状態を盛らない。未実行は `not run`、対象外は `not applicable` とし、理由を書く。
- docs / spec の品質は、対象ファイルを読んで、事実整合、対象読者、根拠、未検証表示、リンク、仮テキストを review する。
- 自動検査へ落とすのは、構文、参照、schema、実行可能な製品契約に限る。自然言語の表現、見出し、説明順、禁止語、作業記録の状態語を固定する assertion は追加しない。
- docs test が落ちた場合は、文書の誤りと test 設計の誤りを同列に調査する。変更対象を読まない test の pass を、その文書の検証根拠にしない。
- experimental、preview、unsupported などの支援範囲は、公開 docs で条件を明確にする。未確定の実装方針は `spec/dev-journal.md` に置く。
- docs site や GitHub Pages 公開が対象範囲に入る場合、local build 成功だけで完了にしない。remote workflow、deployment、公開 URL の確認を根拠に含める。
- 繰り返す agent 手順は static docs に埋め込まず skill 化する。agent 向けの導線は README ではなく `AGENTS.md` と `.agents/skills` に置く。

## 手順

1. `git diff --name-only` と対象 spec を確認し、変更された対象文書を列挙する。
2. 各対象文書の役割に合わない内容を移動または削除する。
3. 公開面の文言から、開発者向けメタ表現、会話依存語、仮テキストを取り除く。
4. public API / package / release / docs site に触れている場合、必要な docs gate を追加する。
5. docs-only 変更では、確認した対象ファイルと確認方法を検証記録に書く。
6. PR body、work unit、handoff には実行 command と結果を具体的に書く。
7. `agentic-self-review` の前に指摘を整理し、未検証事項を残す。

## Checks

最低限、対象ファイルに応じて次を確認する。

```powershell
git diff --name-only
$paths = @("README.md", "docs", "spec", "AGENTS.md", "SKILLS.md", ".github") | Where-Object { Test-Path -LiteralPath $_ }
rg -n "TODO|TBD|xxx|前回|今回|一旦|上述|適宜|必要に応じて" $paths
git diff --check
```

該当する機械的契約または構成がある場合だけ実行する。

```powershell
uv run ruff format --check .
uv run pytest tests/unit
uv run mkdocs build --strict
```

repo-local skill を変更した場合:

```powershell
uv run --with pyyaml python -X utf8 C:\Users\train\.codex\skills\.system\skill-creator\scripts\quick_validate.py .agents\skills\<skill-name>
```

## Report

指摘がある場合は先に出す。

```markdown
### Docs Review

指摘:
- [severity] 対象: 問題 / 根拠 / 修正

確認:
- 対象:
- methods:
- commands:
- not run:

残リスク:
- なし
```
