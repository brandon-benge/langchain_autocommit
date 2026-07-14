# Approval Record: Automatic upstream tracking branch setup on push

Status: approved
Date: 2026-07-14
Approver: user (via @architecture-approver)
Request: `specrepo/requests/2026-07-14-auto-push-upstream.md`
Approved Proposal: `specrepo/proposals/2026-07-14-auto-push-upstream/architecture.md`

## Decision

Approved

## Approved Scope

- New `has_upstream()` helper and modified `push(cwd, set_upstream=...)` in
  `autocommit/utils/git_utils.py`.
- New `git.push_set_upstream` config key (default `true`) in
  `autocommit/params.yaml`.
- New `push_set_upstream: bool = True` parameter on `apply_commit()` in
  `autocommit/core.py`.
- `generate_and_commit()` reads the new config key and passes it to
  `apply_commit()`.
- New CLI flags `--push-set-upstream` / `--no-push-set-upstream` in
  `autocommit/cli.py`.
- Consolidation of the CLI push path: remove the separate `push()` call
  and redundant `push` import; pass `push_after` and `push_set_upstream`
  through `apply_commit` instead.
- Updates to `specrepo/specs/architecture.md` (Commit Application Flow and
  Configuration Contract sections) — already applied.
- Tests for `has_upstream()`, `push(set_upstream=...)`, `apply_commit()`
  with various flag combinations, and new CLI flag parsing.

## Conditions

None

## Notes

1. **CLI error behavior changes from soft-fail to hard-fail.** Previously, a
   push failure produced "Push skipped" and exit 0. After this change, a
   genuine push failure (auth, network, rejected) raises `RuntimeError` from
   `apply_commit`; the CLI catches it, prints the error, and returns exit 1.
   This is intentional — silent push failures are worse than visible ones.

2. **`apply_commit` remains silent; the CLI owns user-facing output.**
   The `apply_commit` function raises rather than printing. The CLI wraps
   the call and prints "Committed." / "Pushed." or "Push failed: ...".

3. **Detached HEAD is not handled specially.** The `@{upstream}` check may
   fail in detached HEAD, but this is not a typical commit-and-push workflow.
   The error message from Git will be clear.

4. **Only `origin` remote is supported** for auto-set-upstream. Non-origin
   remotes or differently-named remote branches are out of scope.
