---
name: tdd-workflow
description: "この Python repo の spec/wip、spec/initial、TDD Test List から Canon TDD を進める orchestration skill。ユーザが TDD、テストリスト、red/green/refactor、仕様から実装への進行を求めるときに使う。"
---

# TDD Workflow

`spec-format`、`tdd-test-list`、`tdd-one-cycle`、`refactor-after-green` を接続する。

## Git Context

- 変更前に branch と `git status --short` を確認する。
- default branch への直接 commit はユーザの明示指示がある場合を除き避ける。
- dirty worktree では既存変更を読んで、ユーザ変更を破棄しない。

## Workflow

1. 関連する `spec/initial/*.md` と `spec/wip` を読む。
2. 作業仕様がなければ `spec-format` で作る。
3. `tdd-test-list` で振る舞いベースの item に分ける。
4. 次に扱う item を 1 つだけ選ぶ。
5. `tdd-one-cycle` で red / green / refactor を進める。
6. green 後の構造変更は `refactor-after-green` と `tidy-first` で behavior change と分ける。
7. test quality に迷う場合は `test-desiderata-review` を使う。
8. spec の TDD Test List、検証、先送り事項を更新する。

## Rules

- red から green の途中で見つけた別の振る舞いは list に追加し、今の item に混ぜない。
- refactor は green 後に行う。
- formatter / linter だけを refactor と呼ばない。
- package metadata に触れたら `uv lock --check` と `uv build` を追加する。
