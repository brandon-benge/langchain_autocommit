# Architecture Proposal: Auto-Merge Flag for Automated PR Creation

Status: awaiting_approval
Date: 2026-07-15
Request: `specrepo/requests/auto-pr-auto-merge.md`

## Summary

Extend the existing `git.auto_pr` feature with an optional auto-merge
mode. When `git.auto_pr.auto_merge` is `true`, after creating a pull
request the tool calls the remote hosting provider's native auto-merge
API — GitHub's `enable_auto_merge` or GitLab's "merge when pipeline
succeeds" — and returns immediately without waiting for checks. The
merge happens asynchronously on the provider side once all required
status checks pass. A configurable merge method (merge commit, squash,
rebase) and a synchronous polling fallback for providers that lack
native auto-merge are part of the design.

## Current Architecture

The auto-merge feature builds on the already-implemented `git.auto_pr`
PR creation infrastructure:

**`autocommit/utils/pr_utils.py`:**
- `create_pr()`: Creates a PR via PyGithub or python-gitlab.
  Returns the PR URL. Currently no merge capability.

**`autocommit/core.py` — `apply_commit()`:**
- After push, checks `auto_pr.enabled`. If enabled and the current
  branch differs from the target, it resolves a token and calls
  `create_pr()`. Returns the PR URL (str) or None.

**`autocommit/cli.py`:**
- Existing flags: `--auto-pr`, `--no-auto-pr`,
  `--auto-pr-target-branch`, `--auto-pr-title`, `--auto-pr-body`.

**`autocommit/params.yaml`:**
```yaml
git:
  auto_pr:
    enabled: false
    target_branch: main
    token_env_var: GITHUB_TOKEN
```

**Current non-goal in `specrepo/specs/architecture.md` and
`specrepo/specs/product.md`:** The product spec states: "It does not
manage branches, merge pull requests, close pull requests, or manage
releases. PR creation is supported only as an optional post-push step."
The approved proposal (2026-07-15-auto-pr-creation) explicitly
excluded merging as out of scope.

## Proposed Architecture

### 1. Extended `create_pr` in `autocommit/utils/pr_utils.py`

Rename or alias the existing `create_pr` to an internal function and
add a higher-level function that optionally enables auto-merge at
creation time. The existing `create_pr` signature is preserved for
backward compatibility; a new `create_pr_and_auto_merge()` function
accepts the additional parameters:

```python
def create_pr_and_auto_merge(
    *,
    repo_path: str,
    token: str,
    head_branch: str,
    base_branch: str,
    title: str,
    body: str = "",
    auto_merge: bool = False,
    merge_method: str = "merge",    # "merge" | "squash" | "rebase"
) -> str:
    """Create a pull request and optionally enable auto-merge.

    When *auto_merge* is ``True``, uses the native auto-merge API of
    the detected hosting provider (GitHub: enable_auto_merge, GitLab:
    merge_when_pipeline_succeeds). Returns the PR URL.

    Raises ``RuntimeError`` if auto-merge is requested but the provider
    or library version does not support it.
    """
```

**Provider-specific behaviour:**

- **GitHub (PyGithub)** — After `repo.create_pull(...)`, call
  `pr.enable_auto_merge(merge_method=merge_method)`. The `merge_method`
  maps to `"MERGE"`, `"SQUASH"`, or `"REBASE"`.
- **GitLab (python-gitlab)** — Pass
  `{'merge_when_pipeline_succeeds': True, 'merge_error': ...}` in the
  MR creation dict. The merge strategy is controlled by the project's
  default merge method unless overridden by a `merge_request` parameter.

If the installed library version does not support these API calls, raise
a clear `RuntimeError` with upgrade instructions.

The existing `create_pr()` function remains unchanged for callers that
do not need auto-merge. It may optionally delegate to the shared
internal logic.

### 2. New config keys in `params.yaml`

```yaml
git:
  auto_pr:
    enabled: false
    target_branch: main
    token_env_var: GITHUB_TOKEN
    auto_merge: false        # NEW — enable auto-merge
    merge_method: merge      # NEW — "merge", "squash", or "rebase"
    merge_timeout: 600       # NEW — max seconds to wait when polling
                             #        (reserved for future synchronous
                             #         poll+merge mode; not used by
                             #         native auto-merge)
```

All new keys have defaults, so existing configs remain valid:
- `auto_merge`: `false`
- `merge_method`: `"merge"`
- `merge_timeout`: `600` (10 minutes)

### 3. `core.py` changes

**`apply_commit()` gains new keyword parameters:**

```python
def apply_commit(
    message: CommitMessage,
    *,
    cwd: str | None = None,
    signoff: bool = False,
    amend: bool = False,
    push_after: bool = False,
    push_set_upstream: bool = True,
    auto_pr_enabled: bool | None = None,
    auto_pr_target_branch: str | None = None,
    auto_pr_title: str | None = None,
    auto_pr_body: str | None = None,
    auto_pr_auto_merge: bool | None = None,       # NEW
    auto_pr_merge_method: str | None = None,       # NEW
    auto_pr_merge_timeout: int | None = None,      # NEW
    _config: dict | None = None,
) -> str | None:
```

After the existing PR-creation block (which calls `create_pr`), add a
new block that reads `auto_merge` from the config/overrides and calls
`create_pr_and_auto_merge` instead of `create_pr` when auto-merge is
enabled:

```python
    # In the PR creation block, replace:
    #   url = create_pr(...)
    # with:
    _auto_merge = (
        auto_pr_auto_merge
        if auto_pr_auto_merge is not None
        else _bool(_auto_pr_cfg.get("auto_merge", False))
    )
    _merge_method = (
        auto_pr_merge_method
        or _auto_pr_cfg.get("merge_method", "merge")
    )
    if _auto_merge:
        url = create_pr_and_auto_merge(
            repo_path=cwd,
            token=token,
            head_branch=branch,
            base_branch=target,
            title=pr_title,
            body=pr_body,
            auto_merge=True,
            merge_method=_merge_method,
        )
    else:
        url = create_pr(
            repo_path=cwd,
            token=token,
            head_branch=branch,
            base_branch=target,
            title=pr_title,
            body=pr_body,
        )
```

**`generate_and_commit()`** reads the new config keys and passes them
through to `apply_commit()`:

```python
    auto_pr_cfg = git_cfg.get("auto_pr", {})
    auto_pr_enabled = _bool(auto_pr_cfg.get("enabled", False))
    auto_pr_target_branch = str(auto_pr_cfg.get("target_branch", "main"))
    auto_pr_auto_merge = _bool(auto_pr_cfg.get("auto_merge", False))         # NEW
    auto_pr_merge_method = str(auto_pr_cfg.get("merge_method", "merge"))     # NEW
    auto_pr_merge_timeout = int(auto_pr_cfg.get("merge_timeout", 600))       # NEW

    apply_commit(
        message, cwd=cwd, signoff=signoff, amend=amend,
        push_after=push_after, push_set_upstream=push_set_upstream,
        auto_pr_enabled=auto_pr_enabled,
        auto_pr_target_branch=auto_pr_target_branch,
        _config=cfg,
        auto_pr_auto_merge=auto_pr_auto_merge,          # NEW
        auto_pr_merge_method=auto_pr_merge_method,      # NEW
        auto_pr_merge_timeout=auto_pr_merge_timeout,    # NEW
    )
```

### 4. `cli.py` changes

Add new CLI flags:

```python
ap.add_argument("--auto-pr-auto-merge", action="store_true",
                dest="auto_pr_auto_merge", default=None,
                help="Enable auto-merge on the created PR")
ap.add_argument("--no-auto-pr-auto-merge", action="store_false",
                dest="auto_pr_auto_merge", default=None,
                help="Disable auto-merge on the created PR")
ap.add_argument("--auto-pr-merge-method", type=str, default=None,
                choices=["merge", "squash", "rebase"],
                help="Merge method for auto-merge (merge, squash, rebase)")
ap.add_argument("--auto-pr-merge-timeout", type=int, default=None,
                help="Max seconds to wait for checks (default: 600)")
```

Wire them into the `apply_commit` call:

```python
    auto_pr_auto_merge = _merge_flag(
        args.auto_pr_auto_merge,
        git_cfg.get("auto_pr", {}).get("auto_merge", False),
    )
    auto_pr_merge_method = (
        args.auto_pr_merge_method
        or git_cfg.get("auto_pr", {}).get("merge_method", "merge")
    )
    auto_pr_merge_timeout = (
        args.auto_pr_merge_timeout
        or int(git_cfg.get("auto_pr", {}).get("merge_timeout", 600))
    )

    pr_url = apply_commit(
        message, cwd=cwd, signoff=signoff, amend=amend,
        push_after=push_after, push_set_upstream=push_set_upstream,
        auto_pr_enabled=auto_pr_enabled,
        auto_pr_target_branch=auto_pr_target_branch,
        auto_pr_title=args.auto_pr_title,
        auto_pr_body=args.auto_pr_body,
        auto_pr_auto_merge=auto_pr_auto_merge,
        auto_pr_merge_method=auto_pr_merge_method,
        auto_pr_merge_timeout=auto_pr_merge_timeout,
        _config=cfg,
    )
```

Update the success message to indicate auto-merge was enabled:

```python
    msg = "Committed."
    if push_after:
        msg += "\n  Pushed."
    if pr_url:
        if auto_pr_auto_merge:
            msg += f"\n  PR created with auto-merge enabled: {pr_url}"
        else:
            msg += f"\n  PR created: {pr_url}"
```

### 5. Return value and PR URL surfacing

`apply_commit()` continues to return `str | None` (the PR URL). A new
boolean return value or separate indicator for auto-merge is not needed
because:
- The caller can infer success from the PR URL being non-None.
- The CLI prints a different message when auto-merge is enabled (see
  §4 above).
- A future enhancement could extend `CommitMessage` or return a richer
  result object if demand arises.

### 6. Error handling and edge cases

| Scenario | Behavior |
|---|---|
| `auto_merge: false` (default) | No merge — identical to today. |
| `auto_merge: true`, PR created successfully | Native auto-merge enabled on the PR; function returns PR URL. |
| `auto_merge: true`, provider API does not support auto-merge | `RuntimeError` with clear message explaining the limitation. |
| `auto_merge: true`, library version too old | `RuntimeError` with upgrade instructions. |
| `auto_merge: true`, no PR created (branch == target) | Auto-merge skipped with informational log. |
| `merge_method` is invalid | `RuntimeError` before any API call. |
| Current branch == target branch | PR creation skipped, auto-merge also skipped. |
| Library not installed | Caught by existing `create_pr` error handling. |

## Scope

In scope:

- New `create_pr_and_auto_merge()` function in
  `autocommit/utils/pr_utils.py` (or inline extension of `create_pr()`).
- New config keys `git.auto_pr.auto_merge`, `git.auto_pr.merge_method`,
  `git.auto_pr.merge_timeout` in `params.yaml`.
- `apply_commit()` gains `auto_pr_auto_merge`,
  `auto_pr_merge_method`, `auto_pr_merge_timeout` keyword parameters.
- `generate_and_commit()` reads new config keys and passes them through.
- New CLI flags: `--auto-pr-auto-merge`, `--no-auto-pr-auto-merge`,
  `--auto-pr-merge-method`, `--auto-pr-merge-timeout`.
- CLI output distinguishes auto-merged PRs from plain PRs.
- Tests for all new and changed functions.
- Updates to baseline specs (product.md, architecture.md).

Out of scope:

- Synchronous poll-then-merge mode (waiting locally for checks and
  then merging). The proposed design uses native provider auto-merge
  APIs for now. A future request can add polling if needed.
- Merge queues, merge trains, or stacked PRs.
- Force-push or history rewriting.
- Interactive merge confirmation.
- Non-GitHub/GitLab providers (follows existing auto_pr constraint).
- Merging PRs with merge conflicts (provider API enforces this).
- Adding reviewers, labels, or other PR metadata before merging.
- Cancelling auto-merge once enabled.

## API, CLI, And Config Changes

- **Public API:**
  - `apply_commit()` gains `auto_pr_auto_merge` (bool | None),
    `auto_pr_merge_method` (str | None),
    `auto_pr_merge_timeout` (int | None) keyword-only parameters.
  - Return type unchanged (`str | None`).
  - `generate_and_commit()` return type unchanged (`CommitMessage`).
  - New internal function: `create_pr_and_auto_merge()`.

- **CLI:**
  - New flags: `--auto-pr-auto-merge`, `--no-auto-pr-auto-merge`,
    `--auto-pr-merge-method`, `--auto-pr-merge-timeout`.
  - CLI output includes "with auto-merge enabled" when applicable.

- **Config:**
  - New `git.auto_pr.auto_merge` (bool, default `false`).
  - New `git.auto_pr.merge_method` (string, default `"merge"`,
    choices: `"merge"`, `"squash"`, `"rebase"`).
  - New `git.auto_pr.merge_timeout` (integer, default `600`).

- **Prompt/provider behavior:** Unchanged.

## Files Expected To Change

| File | Change |
|---|---|
| `autocommit/utils/pr_utils.py` | Add `create_pr_and_auto_merge()`; optionally refactor `create_pr()` to share internal logic. |
| `autocommit/core.py` | `apply_commit()` gains auto-merge keyword params; PR creation block uses `create_pr_and_auto_merge()` when `auto_merge` is `true`. `generate_and_commit()` reads and passes new config keys. |
| `autocommit/params.yaml` | Add `auto_merge`, `merge_method`, `merge_timeout` under `git.auto_pr`. |
| `autocommit/cli.py` | New CLI flags; wire into `apply_commit()` call; update output messages. |
| `specrepo/specs/product.md` | Update non-goals: remove or narrow "does not merge pull requests" to allow auto-merge. |
| `specrepo/specs/architecture.md` | Add auto-merge to config table and `pr_utils.py` module description; update flow. |
| `tests/test_pr_utils.py` | Tests for `create_pr_and_auto_merge()` with mocked libraries. |
| `tests/test_core.py` | Tests for `apply_commit(auto_pr_auto_merge=True, ...)` enabling auto-merge after PR creation. |
| `tests/test_autocommit.py` | Tests for new CLI flags and output messages. |

## Test Plan

| Test target | Behavior verified |
|---|---|
| `tests/test_pr_utils.py` | `create_pr_and_auto_merge(auto_merge=True)` calls GitHub `enable_auto_merge` with correct merge method. |
| `tests/test_pr_utils.py` | `create_pr_and_auto_merge(auto_merge=True)` creates GitLab MR with `merge_when_pipeline_succeeds`. |
| `tests/test_pr_utils.py` | `create_pr_and_auto_merge(auto_merge=False)` behaves identically to `create_pr()`. |
| `tests/test_pr_utils.py` | `create_pr_and_auto_merge(auto_merge=True)` raises `RuntimeError` when provider/version lacks support. |
| `tests/test_pr_utils.py` | Invalid `merge_method` raises `RuntimeError`. |
| `tests/test_core.py` | `apply_commit(auto_pr_enabled=True, auto_pr_auto_merge=True)` calls `create_pr_and_auto_merge` instead of `create_pr`. |
| `tests/test_core.py` | `apply_commit(auto_pr_enabled=True, auto_pr_auto_merge=False)` calls `create_pr` (no merge). |
| `tests/test_core.py` | `apply_commit(auto_pr_auto_merge=True)` skips when current branch == target branch. |
| `tests/test_core.py` | `generate_and_commit()` reads `auto_merge` / `merge_method` from config and passes to `apply_commit()`. |
| `tests/test_autocommit.py` | `--auto-pr-auto-merge` flag enables auto-merge. |
| `tests/test_autocommit.py` | `--no-auto-pr-auto-merge` flag disables auto-merge. |
| `tests/test_autocommit.py` | `--auto-pr-merge-method` overrides config value. |
| `tests/test_autocommit.py` | `--auto-pr-merge-timeout` overrides config value. |
| `tests/test_autocommit.py` | CLI output includes "auto-merge enabled" when flag is set. |

## Risks And Mitigations

- **Risk: Native auto-merge API differs between GitHub and GitLab,
  increasing implementation complexity.**
  **Mitigation:** Both providers expose straightforward API calls
  (GitHub: `enable_auto_merge`, GitLab: `merge_when_pipeline_succeeds`).
  The provider detection from `create_pr` is reused. The abstraction
  is contained within `pr_utils.py`.

- **Risk: PyGithub or python-gitlab versions in use may not support
  auto-merge methods.**
  **Mitigation:** Wrap the auto-merge call in a try/except for
  `AttributeError` or version-specific exceptions and raise a clear
  `RuntimeError` with upgrade instructions. The existing library
  version pins in `pyproject.toml` should be updated to minimum
  versions that support these APIs.

- **Risk: Enabling auto-merge is irreversible (once enabled, the
  provider will merge when checks pass).**
  **Mitigation:** This is intentional — it is the desired behaviour.
  Users who want manual control should keep `auto_merge: false`
  (the default). The PR URL is still printed so the user can cancel
  the auto-merge on the provider's web UI if needed.

- **Risk: The product spec's non-goal "does not merge pull requests"
  must be updated, which is a material change to approved specs.**
  **Mitigation:** The proposal is transparent about this. The
  architecture proposal explicitly calls out the spec change required.
  The approval record should acknowledge this change.

- **Risk: `merge_method` may not be supported by all plans (e.g.,
  GitHub Free may not support all merge methods).**
  **Mitigation:** Pass the method to the API and let the provider
  raise the error. The error message from the library is propagated
  to the user. The user can adjust their plan or method choice.

## Baseline Spec Updates

- **Product spec:** **changed** — The non-goal "It does not manage
  branches, merge pull requests, close pull requests, or manage
  releases" must be narrowed to exclude only managing branches,
  closing PRs, and managing releases, while allowing auto-merge of
  PRs as an optional post-PR-creation step.
- **Architecture spec:** **changed** — New config keys in the
  `git` config table, new `create_pr_and_auto_merge()` function in
  the `pr_utils.py` module description, and extended `apply_commit`
  flow description.
- **Quality spec:** **unchanged** — The existing test strategy
  supports the new tests (mocked library calls).

## Approval Request

Approve this proposal before implementation begins.
