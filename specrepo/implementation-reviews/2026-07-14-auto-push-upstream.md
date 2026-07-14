# Implementation Review: Automatic upstream tracking branch setup on push

Status: implementation_reviewed
Date: 2026-07-14
Reviewer: @implementation-reviewer
Approval Record: `specrepo/approved/2026-07-14-auto-push-upstream/approval.md`

## Approved Architecture Readback

The approved design makes `push_after_commit` robust against branches with
no upstream tracking branch:

1. **New `has_upstream(cwd)`** in `git_utils.py` — checks whether the current
   branch has a configured upstream via
   `git rev-parse --abbrev-ref --symbolic-full-name @{upstream}`.
2. **Modified `push(cwd, set_upstream=False)`** — when `set_upstream=True` and
   the branch has no upstream, runs `git push --set-upstream origin <branch>`
   instead of plain `git push`.
3. **New config key `git.push_set_upstream`** (default `true`) in `params.yaml`.
4. **New `push_set_upstream` parameter** on `apply_commit()` in `core.py`.
5. **`generate_and_commit()`** reads the new config key and passes it through.
6. **New CLI flags** `--push-set-upstream` / `--no-push-set-upstream`.
7. **CLI push consolidation** — the separate `push()` call (lines 242–247) is
   removed; `push_after` and `push_set_upstream` are passed to `apply_commit`,
   which handles both commit and push.
8. **Error handling** — `apply_commit` raises `RuntimeError` on push failure;
   the CLI catches it, prints the error, and returns exit 1.

## Consistency Check

- Product behavior is clear: **yes**
- Architecture boundaries are clear: **yes**
- Public API impact is clear: **yes** — `apply_commit()` gains `push_set_upstream` parameter
- CLI impact is clear: **yes** — new flags, push logic consolidated into `apply_commit`
- Config impact is clear: **yes** — new `git.push_set_upstream` key added to `params.yaml`
- Test plan is clear: **yes** — 10 scenarios across 3 test files

## Implementation Map

### `autocommit/utils/git_utils.py` (lines 59–62)

**Current `push()` function:**
```python
def push(cwd: str) -> None:
    code, out, err = _run("git push", cwd)
    if code != 0:
        raise RuntimeError(err)
```

**Target — add `has_upstream()` and modify `push()`:**

```python
def has_upstream(cwd: str) -> bool:
    code, out, err = _run("git rev-parse --abbrev-ref --symbolic-full-name @{upstream}", cwd)
    return code == 0

def push(cwd: str, set_upstream: bool = False) -> None:
    if set_upstream and not has_upstream(cwd):
        branch = current_branch(cwd)
        code, out, err = _run(f"git push --set-upstream origin {shlex.quote(branch)}", cwd)
    else:
        code, out, err = _run("git push", cwd)
    if code != 0:
        raise RuntimeError(err)
```

Key details:
- `has_upstream()` goes immediately before `push()`.
- `push()` signature changes from `push(cwd)` to `push(cwd, set_upstream=False)`.
- `set_upstream=False` preserves existing behavior exactly.
- `shlex.quote(branch)` prevents shell injection from branch names.

---

### `autocommit/core.py` — `apply_commit()` (lines 184–198)

**Current:**
```python
def apply_commit(
    message: CommitMessage,
    *,
    cwd: str | None = None,
    signoff: bool = False,
    amend: bool = False,
    push_after: bool = False,
) -> None:
    if cwd is None:
        cwd = os.getcwd()
    if not message.subject:
        raise ValueError("No subject in commit message — nothing to commit")
    commit(cwd, message.subject, message.body, signoff=signoff, amend=amend)
    if push_after:
        push(cwd)
```

**Target:**
```python
def apply_commit(
    message: CommitMessage,
    *,
    cwd: str | None = None,
    signoff: bool = False,
    amend: bool = False,
    push_after: bool = False,
    push_set_upstream: bool = True,
) -> None:
    if cwd is None:
        cwd = os.getcwd()
    if not message.subject:
        raise ValueError("No subject in commit message — nothing to commit")
    commit(cwd, message.subject, message.body, signoff=signoff, amend=amend)
    if push_after:
        push(cwd, set_upstream=push_set_upstream)
```

Changes:
- Add `push_set_upstream: bool = True` after `push_after`.
- Change `push(cwd)` to `push(cwd, set_upstream=push_set_upstream)`.

---

### `autocommit/core.py` — `generate_and_commit()` (lines 201–253)

**Current (around line 236):**
```python
    if push_after is None:
        push_after = _bool(git_cfg.get("push_after_commit", False))
```

**Target — read the new config key:**
```python
    if push_after is None:
        push_after = _bool(git_cfg.get("push_after_commit", False))
    push_set_upstream = _bool(git_cfg.get("push_set_upstream", True))
```

**Current (line 253):**
```python
    if message.subject:
        apply_commit(message, cwd=cwd, signoff=signoff, amend=amend, push_after=push_after)
```

**Target — pass the new parameter:**
```python
    if message.subject:
        apply_commit(message, cwd=cwd, signoff=signoff, amend=amend,
                     push_after=push_after, push_set_upstream=push_set_upstream)
```

---

### `autocommit/cli.py` — import (line 11)

**Current:**
```python
from autocommit.utils.git_utils import push
```

**Target — remove the unused import:**
```python
# (delete this line)
```
`push` is no longer called directly from `cli.py`. The `current_branch` import
(not present in cli.py) is also not needed.

---

### `autocommit/cli.py` — new flags (after lines 122–123)

Add after the `--no-push` flag:

```python
ap.add_argument("--push-set-upstream", action="store_true", dest="push_set_upstream", default=None,
                help="Automatically set upstream tracking branch on first push")
ap.add_argument("--no-push-set-upstream", action="store_false", dest="push_set_upstream", default=None,
                help="Do not automatically set upstream tracking branch")
```

---

### `autocommit/cli.py` — apply_commit call and push logic (lines 237–248)

**Current:**
```python
    signoff = _merge_flag(args.signoff, git_cfg.get("signoff", False))
    amend = _merge_flag(args.amend, git_cfg.get("allow_amend", False))
    apply_commit(message, cwd=cwd, signoff=signoff, amend=amend)
    print("Committed.")

    if _merge_flag(args.push, git_cfg.get("push_after_commit", False)):
        try:
            push(cwd)
            print("Pushed.")
        except Exception as e:
            print(f"  Push skipped ({e}).")
```

**Target — consolidate push into `apply_commit`:**
```python
    signoff = _merge_flag(args.signoff, git_cfg.get("signoff", False))
    amend = _merge_flag(args.amend, git_cfg.get("allow_amend", False))
    push_after = _merge_flag(args.push, git_cfg.get("push_after_commit", False))
    push_set_upstream = _merge_flag(args.push_set_upstream, git_cfg.get("push_set_upstream", True))

    try:
        apply_commit(message, cwd=cwd, signoff=signoff, amend=amend,
                     push_after=push_after, push_set_upstream=push_set_upstream)
        print("Committed." if not push_after else "Committed.\n  Pushed.")
    except RuntimeError as e:
        print(f"  Push failed: {e}")
        return 1
```

Key details:
- `push_after` is resolved from flag/config before the call.
- `push_set_upstream` is resolved the same way.
- `apply_commit` raises `RuntimeError` on push failure (existing behavior).
- The CLI catches it and prints the error message, returns exit 1.
- On success, prints "Committed." or "Committed.\n  Pushed." depending on
  whether a push was requested.

---

### `autocommit/params.yaml` (line 24)

Add the new key under the `git` section. Current (around line 24):
```yaml
git:
  autostage_all: true
  signoff: true
  push_after_commit: true
```

Target:
```yaml
git:
  autostage_all: true
  signoff: true
  push_after_commit: true
  push_set_upstream: true
```

---

### Tests

| New test location | What it verifies |
|---|---|
| `tests/test_git_utils.py` — `test_has_upstream_true` | `has_upstream()` returns `True` when `@{upstream}` resolves (mock stdout) |
| `tests/test_git_utils.py` — `test_has_upstream_false` | `has_upstream()` returns `False` when `@{upstream}` fails (mock return code) |
| `tests/test_git_utils.py` — `test_push_with_set_upstream_no_upstream` | `push(set_upstream=True)` on branch with no upstream runs `git push --set-upstream origin <branch>` |
| `tests/test_git_utils.py` — `test_push_without_set_upstream_no_upstream` | `push(set_upstream=False)` on branch with no upstream raises `RuntimeError` |
| `tests/test_git_utils.py` — `test_push_with_set_upstream_has_upstream` | `push(set_upstream=True)` on branch with upstream runs plain `git push` |
| `tests/test_core.py` — `test_apply_commit_push_set_upstream_true` | `apply_commit(push_after=True, push_set_upstream=True)` succeeds on no-upstream (mock push) |
| `tests/test_core.py` — `test_apply_commit_push_set_upstream_false` | `apply_commit(push_after=True, push_set_upstream=False)` raises on no-upstream |
| `tests/test_autocommit.py` — CLI flag test | `--push-set-upstream` flag propagates to `apply_commit` |
| `tests/test_autocommit.py` — CLI flag test | `--no-push-set-upstream` disables auto-setup |
| `tests/test_autocommit.py` — backward compat | `--push` / `--no-push` still work unchanged |

---

### Spec updates already applied

- `specrepo/specs/architecture.md` — Commit Application Flow and Configuration
  Contract sections updated.

## Questions Or Blockers

**None.** The approved architecture is complete and maps to concrete changes in
4 source files plus `params.yaml` and tests. A few detailed implementation
notes below (not blockers):

- **Empty `push_set_upstream` flag value:** `--push-set-upstream` (store_true)
  is always `True` or `None`; it can't be accidentally empty. No edge case.
- **`cli.py` error exit:** The proposal says returning `1` on push failure.
  This is consistent with the existing `return 1` paths in `cli.py` (line 35,
  192, 235).
- **The `push` import removal in `cli.py`** should be verified by checking no
  other code in `cli.py` uses `push` — currently it's only used on line 244.

## Verification Plan

```bash
pytest -v
```

The existing test suite must pass unchanged. New tests (listed above) should
be added and passing.

Additionally, manual verification:
```bash
# Create a branch with no upstream, set push_after_commit=true, run autocommit
# Verify the branch is pushed and tracking is set
git checkout -b test-auto-push
autocommit -y
git branch -vv  # should show origin/test-auto-push as upstream
```

## Review Decision

**Proceed** — the approved architecture is internally consistent, maps to
concrete file-level changes in 4 source files plus `params.yaml`, has no
blocking issues, and the test plan covers all scenarios.
