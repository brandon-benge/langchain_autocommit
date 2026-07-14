# Architecture Proposal: Automatic upstream tracking branch setup on push

Status: awaiting_approval
Date: 2026-07-14
Request: `specrepo/requests/2026-07-14-auto-push-upstream.md`

## Summary

When `push_after_commit` is true (or `--push` is passed) and the current
branch has no upstream tracking branch, automatically set the upstream
to `origin/<current-branch>` and retry the push. A new config key
(`git.push_set_upstream`, default `true`) and matching CLI flags
(`--push-set-upstream` / `--no-push-set-upstream`) control the behavior,
with the same guard and override pattern as existing Git overrides.

## Current Architecture

Push behavior is spread across three files:

**`autocommit/utils/git_utils.py` — `push(cwd)`:**
- Runs `git push` via subprocess.
- Raises `RuntimeError` with stderr on any nonzero return code.
- No detection of the "no upstream branch" condition.
- No retry or fallback logic.

**`autocommit/core.py` — `apply_commit(message, ..., push_after=False)`:**
- Calls `commit()` then conditionally calls `push(cwd)`.
- Does not catch `RuntimeError` from push — it propagates to the caller.
- Used by `generate_and_commit()`.

**`autocommit/cli.py` — `main()`:**
- Reads `git.push_after_commit` from config and merges with `--push`/`--no-push`.
- Calls `apply_commit(message, cwd, signoff, amend)` — note: `push_after` is
  **not** passed to `apply_commit`; instead the CLI does its own separate push
  call (lines 242–247):
  ```python
  if _merge_flag(args.push, git_cfg.get("push_after_commit", False)):
      try:
          push(cwd)
          print("Pushed.")
      except Exception as e:
          print(f"  Push skipped ({e}).")
  ```
- The CLI thus prints "Pushed." on success or "Push skipped (...)" on failure,
  including when the only failure is a missing upstream.

Existing relevant tests:
- `tests/test_git_utils.py` — likely covers `push()` (read-only mock of subprocess).
- `tests/test_core.py` — may cover `apply_commit(push_after=True)`.
- `tests/test_autocommit.py` — covers `--push` / `--no-push` CLI flags.

## Proposed Architecture

### 1. New utility functions in `git_utils.py`

Add a helper to check whether the current branch has an upstream:

```python
def has_upstream(cwd: str) -> bool:
    code, out, err = _run("git rev-parse --abbrev-ref --symbolic-full-name @{upstream}", cwd)
    return code == 0
```

Modify `push()` to accept an optional `set_upstream` parameter:

```python
def push(cwd: str, set_upstream: bool = False) -> None:
    if set_upstream and not has_upstream(cwd):
        branch = current_branch(cwd)
        code, out, err = _run(f"git push --set-upstream origin {shlex.quote(branch)}", cwd)
    else:
        code, out, err = _run("git push", cwd)
    if code != 0:
        raise RuntimeError(err)
```

Key design choices:
- **Pre-check approach:** Run `git rev-parse @{upstream}` before pushing rather
  than parsing the error output of `git push`. This avoids locale-dependent error
  string matching and is more deterministic.
- **`set_upstream=False` preserves existing behavior** — when `push_set_upstream`
  is disabled, `push()` acts identically to today.
- **`set_upstream=True` without `push_after`** is irrelevant because the call
  site only invokes `push()` when push is requested.

### 2. New config key in `params.yaml`

```yaml
git:
  push_after_commit: true
  push_set_upstream: true    # NEW — auto-set upstream when branch has none
  ...
```

`push_set_upstream` defaults to `true` in the bundled config because the
entire purpose of `push_after_commit` is to push without manual steps.

### 3. `core.py` — `apply_commit` gains `push_set_upstream` parameter

```python
def apply_commit(
    message: CommitMessage,
    *,
    cwd: str | None = None,
    signoff: bool = False,
    amend: bool = False,
    push_after: bool = False,
    push_set_upstream: bool = True,     # NEW
) -> None:
    ...
    if push_after:
        push(cwd, set_upstream=push_set_upstream)
```

`generate_and_commit` reads the new config key and passes it:

```python
push_set_upstream = _bool(git_cfg.get("push_set_upstream", True))
...
apply_commit(message, cwd=cwd, signoff=signoff, amend=amend,
             push_after=push_after, push_set_upstream=push_set_upstream)
```

### 4. `cli.py` — new flags and consolidated push call

Add `--push-set-upstream` / `--no-push-set-upstream` flags:

```python
ap.add_argument("--push-set-upstream", action="store_true", dest="push_set_upstream", default=None,
                help="Automatically set upstream tracking branch on first push")
ap.add_argument("--no-push-set-upstream", action="store_false", dest="push_set_upstream", default=None,
                help="Do not automatically set upstream tracking branch")
```

**Consolidate the push call.** Currently `cli.py` bypasses `apply_commit`'s
`push_after` parameter and does its own separate `push()` call. This proposal
fixes that inconsistency by passing `push_after` (and the new
`push_set_upstream`) to `apply_commit`. The CLI's explicit push-after logic
(lines 242–247) is removed; `apply_commit` handles the push and its error
reporting.

This also means the `push` import in `cli.py` can be removed.

```python
apply_commit(message, cwd=cwd, signoff=signoff, amend=amend,
             push_after=_merge_flag(args.push, git_cfg.get("push_after_commit", False)),
             push_set_upstream=_merge_flag(args.push_set_upstream, git_cfg.get("push_set_upstream", True)))
```

The `print("Committed.")` and `print("Pushed.")` messages move into
`apply_commit` (or remain in the CLI but the push error is handled within
`apply_commit`). The preferred approach: `apply_commit` prints nothing; the CLI
prints "Committed." after `apply_commit` returns, and prints "Pushed." only
when `push_after` was true and push succeeded. Error messages should be
surfaced by `apply_commit` raising or the CLI catching.

Design choice: **Keep `apply_commit` silent** (no print statements). The CLI
wraps the call:

```python
try:
    apply_commit(message, cwd=cwd, signoff=signoff, amend=amend,
                 push_after=push_after, push_set_upstream=push_set_upstream)
    print("Committed." if not push_after else "Committed.\n  Pushed.")
except RuntimeError as e:
    print(f"  Push failed: {e}")
    return 1
```

This preserves the existing behavior where the CLI controls user-facing output
and the core library raises exceptions.

### 5. Error handling

- **Genuine push failures** (auth failure, network error, rejected push): `git push`
  returns a nonzero code with a descriptive error message. `push()` raises
  `RuntimeError`. The CLI catches it and prints the error.
- **Missing upstream with `push_set_upstream=False`**: `git push` fails, `push()`
  raises `RuntimeError`. Same path as above — the user sees the native Git error
  message advising them to set the upstream manually.
- **Missing upstream with `push_set_upstream=True`**: `has_upstream()` returns
  `False`, `push()` runs `git push --set-upstream origin <branch>` which either
  succeeds or fails with a genuine error.

## Scope

In scope:

- New `has_upstream()` and modified `push(set_upstream=...)` in `git_utils.py`.
- New `git.push_set_upstream` config key (default `true`) in `params.yaml`.
- New `push_set_upstream` parameter on `apply_commit`.
- CLI flags `--push-set-upstream` / `--no-push-set-upstream`.
- Consolidation of the CLI push path to use `apply_commit`'s `push_after`
  parameter instead of a separate `push()` call.
- Updates to architecture spec and `params.yaml`.
- Tests for upstream detection, auto-setup, error cases, CLI flags.

Out of scope:

- Non-`origin` remote names.
- Pushing to a differently-named remote branch.
- Interactive prompting before setting upstream.
- Changes to `generate_commit_message`, the quality loop, or the fallback path.
- Multi-remote or multi-upstream support.

## API, CLI, And Config Changes

- **Public API:**
  - `apply_commit()` gains `push_set_upstream: bool = True` keyword-only
    parameter.
  - `generate_and_commit()` propagates the new config key; no signature change
    needed (it reads from config).

- **CLI:**
  - New `--push-set-upstream` / `--no-push-set-upstream` flags.
  - The CLI's separate `push()` call (lines 242–247 of current `cli.py`) is
    replaced by passing `push_after` and `push_set_upstream` into
    `apply_commit`, removing the redundant import of `push` from `cli.py`.

- **Config:**
  - New key `git.push_set_upstream` (bool, default `true`) in `params.yaml`.

- **Prompt/provider behavior:** Unchanged.

## Files Expected To Change

| File | Change |
|---|---|
| `autocommit/utils/git_utils.py` | Add `has_upstream()`; modify `push()` to accept `set_upstream` parameter. |
| `autocommit/core.py` | `apply_commit()` gains `push_set_upstream` param; `generate_and_commit()` reads the new config key and passes it. |
| `autocommit/cli.py` | Add `--push-set-upstream` / `--no-push-set-upstream` flags; consolidate push logic into `apply_commit` call; remove direct `push` import. |
| `autocommit/params.yaml` | Add `push_set_upstream: true` under the `git` section. |
| `specrepo/specs/architecture.md` | Update "Commit Application Flow" and "Configuration Contract" sections. |
| `tests/test_git_utils.py` | Tests for `has_upstream()` and `push(set_upstream=...)` with mocked/no-upstream branches. |
| `tests/test_core.py` | Tests for `apply_commit(push_after=True, push_set_upstream=True/False)`. |
| `tests/test_autocommit.py` | Tests for `--push-set-upstream` / `--no-push-set-upstream` CLI flags. |

## Test Plan

| Test target | Behavior verified |
|---|---|
| `tests/test_git_utils.py` | `has_upstream()` returns `True` when `@{upstream}` resolves. |
| `tests/test_git_utils.py` | `has_upstream()` returns `False` when `@{upstream}` fails. |
| `tests/test_git_utils.py` | `push(set_upstream=True)` on a branch with no upstream runs `git push --set-upstream origin <branch>`. |
| `tests/test_git_utils.py` | `push(set_upstream=False)` on a branch with no upstream raises `RuntimeError`. |
| `tests/test_git_utils.py` | `push(set_upstream=True)` on a branch with an upstream runs plain `git push`. |
| `tests/test_core.py` | `apply_commit(push_after=True, push_set_upstream=False)` raises on no-upstream. |
| `tests/test_core.py` | `apply_commit(push_after=True, push_set_upstream=True)` succeeds on no-upstream. |
| `tests/test_autocommit.py` | `--push-set-upstream` flag propagates to `apply_commit`. |
| `tests/test_autocommit.py` | `--no-push-set-upstream` disables auto-setup (reverts to error). |
| `tests/test_autocommit.py` | Existing `--push` / `--no-push` flags continue to work unchanged. |

## Risks And Mitigations

- **Risk: The upstream check (`@{upstream}`) may fail in a detached HEAD state.**
  **Mitigation:** `current_branch()` would return `"HEAD"`. The `push` call with
  `--set-upstream origin HEAD` would be a no-op or error. This is acceptable
  because detached HEAD is not a typical commit-and-push workflow. The error
  message will be clear.

- **Risk: Users who rely on the current "Push skipped" soft-fail behavior may be
  surprised by the new error-on-fail from `apply_commit`.**
  **Mitigation:** `push_set_upstream` defaults to `true`, so the common case
  (no upstream) succeeds silently. For genuine failures, raising the error is
  appropriate — the current soft-fail hides real problems. The CLI catches the
  error and prints the message without crashing.

- **Risk: Renaming `push_set_upstream` to match `push_after_commit` naming
  convention (`push_set_upstream` uses underscores but follows the existing
  pattern of `autostage_all`, `scope_from_folder`, etc.)**
  **Mitigation:** All git config keys use snake_case. `push_set_upstream`
  matches this convention. The CLI flags use hyphens (`--push-set-upstream`)
  following argparse convention, matching `--max-subject-length`,
  `--quality-max-retries`, etc.

## Baseline Spec Updates

- **Product spec:** unchanged — the existing "Apply the generated commit with
  optional signoff, amend, and push behavior" capability is refined, not added.
- **Architecture spec:** changed — the "Commit Application Flow" and
  "Configuration Contract" sections must describe the new `push_set_upstream`
  behavior.
- **Quality spec:** unchanged.

## Approval Request

Approve this proposal before implementation begins.
