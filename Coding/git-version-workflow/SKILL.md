---
name: git-version-workflow
description: Apply the user's Git commit, versioned message, squash, rebase, verification, and push conventions. Use when the user asks to commit, squash, rebase, or push changes, especially with semantic version tags or changelog updates.
---

# Git Version Workflow

## Scope

Apply these rules when preparing, squashing, rebasing, verifying, or pushing Git commits. When a release commit also updates a `CHANGELOG`, pair this skill with `wty-markdown-standards`.

## Commit Conventions

- Before committing, inspect `git status`, the current branch, remote tracking state, and recent commit history.
- Stage and commit only the intended changes; never overwrite or discard unrelated user edits.
- If the commit defines a version, use only `v<version>` as the commit message, optionally followed by a component version with `+` (for example, `v1.1` or `v1.1+component1.1`).
- Do not append action descriptions, semicolons, or colons to a versioned commit message; use the `+<component><version>` suffix for component versions.
- If the user explicitly requests a squash from a specified base commit, preserve that base and replace only the requested following commits with a single commit using the requested version message.

## Rebase, Verification, and Push

- Before pushing, fetch or inspect the current `origin/<branch>` and rebase local commits onto the latest remote branch.
- Resolve rebase conflicts by preserving both the remote changes and the local requested changes; if a `CHANGELOG` is affected, re-check descending version ordering and ensure there are no duplicate version headings.
- Run `git diff --check` and relevant syntax or focused tests before pushing.
- Use a normal `git push` when history is unchanged. If a requested rebase or squash rewrites commits already pushed to the same branch, use `git push --force-with-lease`, never an unconditional `--force`.
- If a push is blocked solely because the local Git LFS hook cannot run, report the hook failure and bypass it with `--no-verify` only after confirming that the commit does not add or modify LFS assets.
- After pushing, confirm the working tree and branch tracking state (`git status --short --branch`).
