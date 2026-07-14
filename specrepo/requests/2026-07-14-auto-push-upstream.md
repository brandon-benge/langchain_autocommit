# Feature Request: Automatic upstream tracking branch setup on push

Status: requested
Date: 2026-07-14
Requester: user

## Summary

Make the `push_after_commit` config flag (and `--push` CLI flag) robust
against branches that have no upstream tracking branch. When a push is
requested but the current branch has no configured upstream, the tool
should automatically set the upstream tracking reference (equivalent to
`git push --set-upstream origin <branch>`) so that the push succeeds
without manual intervention.

## Problem

The `git.push_after_commit` config key already exists in `params.yaml`
and defaults to `true` in the bundled config. However, when the current
branch has never been pushed and therefore has no upstream tracking
branch, the underlying `git push` command fails. The CLI catches this
error and prints a "Push skipped" message instead of completing the
push. Users working on feature branches (especially branches created by
the SpecRepo workflow, such as `request/...` branches) encounter this
failure on their first commit, requiring them to manually run
`git push --set-upstream origin <branch>` after every `autocommit`
session.

The current behavior violates the user's expectation that setting
`push_after_commit: true` means "commit and push without further manual
steps."

## Desired Behavior

- When `push_after_commit` is `true` (or `--push` is passed on the CLI)
  and the current branch has no upstream tracking branch, the tool
  automatically sets the upstream to `origin/<current-branch>` before
  or during the push attempt.
- When the branch already has an upstream tracking branch, behavior is
  identical to today (plain `git push`).
- The auto-set-upstream behavior should be controllable via a config
  key in `params.yaml` (e.g., `git.push_set_upstream`) so that users
  who prefer the explicit error can opt out.
- The auto-set-upstream behavior should also be overridable via CLI
  flags (`--push-set-upstream` / `--no-push-set-upstream`).
- When push is invoked through the Python API (`apply_commit(push_after=True)`),
  the same logic applies — the function should not raise a
  `RuntimeError` when the only failure is a missing upstream.

## Acceptance Criteria

1. A user on a branch with no upstream runs `autocommit` with
   `push_after_commit: true` (default in bundled config): the commit is
   created and then the branch is pushed with the upstream tracking
   reference set automatically. The user sees "Pushed." not "Push
   skipped."
2. A user on a branch that already has an upstream sees no change in
   push behavior — plain `git push` is used.
3. A config key (e.g., `git.push_set_upstream`) controls whether the
   auto-upstream behavior is enabled. When set to `false`, a push on a
   branch with no upstream produces the same error as today (no silent
   upstream creation).
4. A CLI flag `--push-set-upstream` / `--no-push-set-upstream` overrides
   the config key, following the same pattern as existing Git overrides
   (`--push` / `--no-push`, `--signoff` / `--no-signoff`, etc.).
5. The `apply_commit` Python API propagates a
   `push_set_upstream` parameter (defaulting to the config value) so
   that programmatic callers have the same control.
6. When `push_after_commit` is `false`, no push (and therefore no
   upstream setup) is attempted regardless of the `push_set_upstream`
   setting.
7. Existing tests for the push path pass with no behavioral change for
   branches that already have an upstream.

## Constraints

- The feature must remain opt-in at the push level (`push_after_commit`
  must still be `true` for any push to occur).
- Auto-set-upstream must only apply to the "no upstream branch" error
  case; genuine push failures (authentication failure, network error,
  rejected push) must still be surfaced as errors.
- The implementation must detect the "no upstream branch" condition
  reliably from the `git push` error output or by checking the upstream
  before pushing.
- The bundled `params.yaml` default for the new config key should match
  user expectations — it is reasonable to default `push_set_upstream` to
  `true` since the whole point of `push_after_commit` is to avoid manual
  push steps.
- The Python API must remain backward compatible for callers that do
  not pass the new parameter.

## Non-Goals

- No change to `git push` behavior for branches that already have an
  upstream.
- No support for setting upstream to a remote other than `origin`.
- No support for setting upstream to a branch name that differs from the
  local branch name.
- No interactive prompting to confirm upstream creation.
- No changes to the deterministic fallback, commit message generation,
  or quality loop.

## Impacted Areas

- Public API: yes — `apply_commit` gains a new parameter
  (`push_set_upstream`) if programmatic control is exposed.
- CLI: yes — new flags `--push-set-upstream` / `--no-push-set-upstream`.
- Config: yes — new key under `git` (e.g., `push_set_upstream`).
- LLM prompt/provider: no
- Git behavior: yes — the `push` function in `git_utils.py` gains logic
  to detect missing upstream and optionally set it.
- Tests/docs: yes — new tests for the upstream-detection and
  auto-setup logic; config and CLI documentation updates.

## Notes

The user encountered this failure on the `request/custom-params-file`
branch with the following error:

```
Push skipped (fatal: The current branch request/custom-params-file has no upstream branch.
To push the current branch and set the remote as upstream, use

    git push --set-upstream origin request/custom-params-file
```

The bundled `autocommit/params.yaml` already sets
`git.push_after_commit: true`, meaning every user on a fresh branch hits
this on their first commit unless they pre-configure an upstream
manually.

Current push flow:
- `git_utils.push()` runs `git push` and raises `RuntimeError` on any
  nonzero return code.
- `cli.py` catches the exception and prints a "Push skipped" message.
- `core.py` (`apply_commit`) does not catch the exception, so it
  propagates unhandled to programmatic callers.

The implementation should detect the missing-upstream case (either by
checking `git rev-parse --abbrev-ref --symbolic-full-name @{upstream}`
before pushing or by inspecting the error output) and, when enabled,
retry with `git push --set-upstream origin <branch>`.
