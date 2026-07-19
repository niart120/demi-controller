---
name: pr-merge-cleanup
description: "この Python repo の作業ブランチを GitHub PR 経由で default branch に取り込み、ローカル同期と branch cleanup まで行う skill。ユーザが PR 作成、マージ、ブランチ後片付け、main/master へ入れる、PR cleanup を依頼したときに使う。remote 未設定、default branch 上、dirty worktree、required check 失敗では停止する。"
---

# PR Merge Cleanup

作業ブランチの変更を GitHub PR 経由で default branch に取り込み、local sync と branch cleanup まで行う。

## GitHub 操作

- push、PR 作成、PR 状態確認、merge、remote branch 削除は GitHub plugin を使う。
- publish と PR 作成は `github:yeet`、PR の確認と merge は `github:github` を使う。
- GitHub plugin が対象 repository、branch、権限を解決できない場合は停止する。別の GitHub CLI 経路へ退避しない。

## Preconditions

- `origin` remote が設定済み。
- default branch を確認できる。
- 作業ブランチ上である。
- `git status --short` が clean。
- 必要な commit が完了している。
- GitHub plugin が対象 repository への push / PR / merge 権限を持つ。

remote 未設定の現段階では stop condition として扱い、push や PR 作成を試みない。

## Workflow

1. `git branch --show-current` を確認する。
2. `git remote get-url origin` と default branch を確認する。
3. default branch 上なら停止する。
4. `git status --short` が空であることを確認する。
5. `git log --oneline <default>..HEAD` で commit log を作る。
6. `agentic-self-review` の結果と実行 gate を PR 本文へ反映する。
7. `github:yeet` を使い、対象 branch を publish して PR を作成する。merge を行う依頼では ready-for-review の PR とする。
8. `github:github` を使い、PR 番号、URL、head / base branch、mergeable state、required check を確認する。
9. required check が通るまで GitHub plugin で PR 状態を確認する。
10. check が通ったら GitHub plugin で merge する。repository の既定 merge 方針を変えない。
11. default branch へ戻り、`git pull --ff-only origin <default>` で同期する。
12. GitHub plugin で remote の作業 branch を削除し、local の作業 branch も削除する。
13. PR 番号、URL、merge commit、削除 branch、gate 状態を報告する。

## Stop Conditions

- `origin` remote がない。
- default branch 上にいる。
- dirty worktree がある。
- required check が未完了または失敗。
- mergeable state が blocked / dirty / unknown。
- PR 本文に gate の必須情報が不足している。
- GitHub plugin が PR 作成、状態確認、merge、remote branch 削除を実行できない。

## PR Body

- Summary: 変更目的を 1-3 行で書く。
- Related: spec、docs、issue、作業指示元。
- Changes: file list ではなく論理単位。
- Commit Log: `<default>..HEAD`。
- Testing: command と結果。未実行 gate は理由。
- Agentic SDD Gates: used / not used と evidence。
- Review Notes: scope drift、先送り事項。
