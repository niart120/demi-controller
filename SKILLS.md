# Repo-local Skills

この repo の agent skill は `.agents/skills` を正本とする。各 skill の `SKILL.md` は Codex が読む実行手順であり、作業ルールの重複配置ではない。

## 一覧

| skill | 用途 |
|---|---|
| `agentic-sdd` | `AGENTS.md`、`spec/initial`、`spec/wip` を読み、次の作業単位を 1 つ選んで実装と gate へ進める。 |
| `agentic-self-review` | 完了前、PR 前、handoff 前に gate、未実行テスト、未検証リスクを整理する。 |
| `diagnosing-bugs` | Matt Pocock 氏の第三者提供 skill。再現困難な不具合と性能退行で、赤にできる再現手順、仮説、計測、回帰テストを順に作る。 |
| `docs-quality-review` | README、docs、docstring、spec、PR 本文、AGENTS/SKILLS の文言、置き場所、根拠を確認する。 |
| `type-boundary-review` | `ty` の結果、公開 API、標準ライブラリの型構文、`Any` / `Unknown` / `None` / `Protocol` / `TYPE_CHECKING` / `py.typed` の型境界を確認する。 |
| `docstring-style` | 公開 API の Google 形式 docstring を、型注釈、ruff pydocstyle、README/docs と整合させる。 |
| `spec-format` | 作業仕様を `spec/wip/unit_XXX` に作成し、完了時に `spec/complete/unit_XXX` へ移す。 |
| `dev-journal` | 仕様書へ昇格する前の小さい観測、先送り判断、未解決事項を記録する。 |
| `tdd-workflow` | TDD Test List から red / green / refactor を進める。 |
| `tdd-test-list` | 振る舞いベースの TDD Test List を作成、更新する。 |
| `tdd-one-cycle` | TDD Test List の 1 item だけを扱う。 |
| `tidy-first` | 振る舞い変更と構造変更を分ける。 |
| `refactor-after-green` | green 後に観測可能な振る舞いを変えず構造を整える。 |
| `test-desiderata-review` | テストの速さ、決定性、代表性、保守性の trade-off を確認する。 |
| `pr-merge-cleanup` | PR 作成、merge、default branch 同期、branch cleanup を行う。 |
| `pypi-release` | PyPI / TestPyPI release の preflight、version、tag、publish、smoke check を扱う。 |

## 運用

- 新しい繰り返し作業は、静的 docs だけでなく skill 化を検討する。
- skill を変更したら `quick_validate.py` を実行する。
- 汎用化できないプロジェクト固有の制約は、skill 本体ではなく `spec/initial` に置く。
