# Architecture Proposal: Automated PR Creation After Commit

Status: awaiting_approval
Date: 2026-07-15
Request: `specrepo/requests/auto-pr-creation.md`

## Summary

After a successful commit and push, optionally create a pull request against a
configurable target branch using a Python library (e.g., `PyGithub`). A new
`git.auto_pr.*` config block in `params.yaml` controls the feature. The
PR-creating library is an optional dependency. API tokens reuse the existing
env-var / macOS Keychain pattern. When `auto_pr.enabled` is `false` (the
default) or the current branch matches the target branch, the feature is a
no-op.

## Current Architecture

Push-to-remote behavior is the end of the `apply_commit` / `generate_and_commit`
flow. There is no PR creation capability today.

**`autocommit/core.py`:**
- `apply_commit(message, ..., push_after=False, push_set_upstream=True)`:
  calls `commit()` then conditionally calls `push()`.
- `generate_and_commit(...)`: reads git config keys, calls
  `generate_commit_message()` then `apply_commit()`.
- Neither function has any concept of PR creation.

**`autocommit/utils/git_utils.py`:**
- `push(cwd, set_upstream=False)`: runs `git push` via subprocess.
- `current_branch(cwd)`: returns the current branch name via
  `git rev-parse --abbrev-ref HEAD`.

**`autocommit/utils/keychain.py`:**
- `get_api_key(service, key)`: retrieves a secret from macOS Keychain via
  `keyring`.
- Currently used only for LLM API keys.

**`autocommit/params.yaml`:**
- No PR-related keys exist.
- The `git:` section holds: `autostage_all`, `signoff`, `push_after_commit`,
  `push_set_upstream`, `allow_amend`, `conventional`, `default_type`,
  `scope_from_folder`, `max_subject_length`, `max_diff_chars`,
  `max_changed_files`, `include_diff_patch`, `ticket_regex`, `quality.*`.

**`autocommit/cli.py`:**
- CLI flags exist for all git config overrides following a consistent pattern:
  `--push` / `--no-push`, `--push-set-upstream` / `--no-push-set-upstream`, etc.
- No PR-related flags exist.

## Proposed Architecture

### 1. New module: `autocommit/utils/pr_utils.py`

A new module encapsulating all PR-creation logic, isolated from the rest of the
codebase. It provides one public function:

```python
def create_pr(
    *,
    repo_path: str,
    token: str,
    head_branch: str,
    base_branch: str,
    title: str,
    body: str = "",
) -> str:
    """Create a pull request and return its URL.

    Detects the remote hosting provider from the remote URL
    (github.com, gitlab.com, or enterprise equivalents).
    Uses the appropriate Python library (PyGithub, python-gitlab).

    Raises:
        RuntimeError: if the library is not installed, token is invalid,
                      or the API call fails.
    """
```

**Provider detection logic:**
1. Read `git remote get-url origin` to extract the host (e.g., `github.com`,
   `gitlab.example.com`).
2. Match against known providers:
   - `github.com` or any host containing `github` → use `PyGithub`.
   - `gitlab.com` or any host containing `gitlab` → use `python-gitlab`.
3. Unknown hosts raise `RuntimeError` with a clear message.

**Library invocation (example for GitHub):**
```python
from github import Github
g = Github(token)
repo = g.get_repo(owner_and_repo)  # parsed from remote URL
pr = repo.create_pull(title=title, body=body, base=base_branch, head=head_branch)
return pr.html_url
```

**Key design decisions:**
- Provider detection happens at call time, not import time — no premature import
  errors when the user has `auto_pr.enabled: false`.
- The GitHub token is resolved before calling `create_pr`, so `pr_utils.py` does
  not need to know about keychain/env-var resolution.
- The remote URL is parsed from `git remote get-url origin` using a new helper
  in `git_utils.py`.

### 2. New helper in `git_utils.py`

Add a function to parse the remote owner/repo from the origin URL:

```python
def parse_remote_repo(cwd: str) -> tuple[str, str]:
    """Return (owner, repo) from the 'origin' remote URL.

    Supports:
        git@github.com:owner/repo.git
        https://github.com/owner/repo.git
        https://github.com/owner/repo
    Raises RuntimeError if origin is missing or unparseable.
    """
```

And a function to get the remote host:

```python
def remote_host(cwd: str) -> str:
    """Return the hostname from the 'origin' remote URL, e.g. 'github.com'."""
```

### 3. Token resolution in a new `autocommit/utils/pr_token.py`

A lightweight module (or integrated into `config.py`) that resolves the PR API
token in the same style as the existing LLM API key resolution:

```python
def resolve_pr_token(cfg: dict) -> str:
    """Resolve the PR API token from config.

    Priority:
    1. Env var named by git.auto_pr.token_env_var (default GITHUB_TOKEN)
    2. macOS Keychain at git.auto_pr.keychain.service / .keychain.key
    3. Raises RuntimeError with a clear message if neither is configured.
    """
```

This reuses the existing `keyring` dependency already in the project via
`autocommit/utils/keychain.py`.

### 4. Config schema in `params.yaml`

```yaml
git:
  # ... existing keys ...
  auto_pr:
    enabled: false
    target_branch: main
    token_env_var: GITHUB_TOKEN
    # keychain:
    #   service: langchain_autocommit
    #   key: github_token
```

All keys have defaults, so existing configs remain valid:
- `enabled`: `false`
- `target_branch`: `"main"`
- `token_env_var`: `"GITHUB_TOKEN"`
- `keychain`: not set by default (disabled; when absent, env var is used)

### 5. `core.py` changes

**`apply_commit` gains new keyword parameters:**

```python
def apply_commit(
    message: CommitMessage,
    *,
    cwd: str | None = None,
    signoff: bool = False,
    amend: bool = False,
    push_after: bool = False,
    push_set_upstream: bool = True,
    auto_pr_enabled: bool | None = None,      # NEW
    auto_pr_target_branch: str | None = None,  # NEW
    auto_pr_title: str | None = None,          # NEW
    auto_pr_body: str | None = None,           # NEW
) -> None:
```

After the existing `if push_after: push(...)` block, add:

```python
    auto_pr_cfg = cfg.get("git", {}).get("auto_pr", {})
    if _bool(auto_pr_enabled if auto_pr_enabled is not None
             else auto_pr_cfg.get("enabled", False)):
        branch = current_branch(cwd)
        target = auto_pr_target_branch or auto_pr_cfg.get("target_branch", "main")
        if branch == target:
            return  # no-op, same branch
        # resolve token
        token = resolve_pr_token(cfg)
        # build title/body from message or overrides
        pr_title = auto_pr_title or message.subject
        pr_body = auto_pr_body or message.body
        # create PR
        from autocommit.utils.pr_utils import create_pr
        url = create_pr(
            repo_path=cwd,
            token=token,
            head_branch=branch,
            base_branch=target,
            title=pr_title,
            body=pr_body,
        )
        # store URL for return or logging (see section 6)
```

**Important:** Since `apply_commit` currently does not have access to the config
dict, the config must be passed through. Options:

- **Preferred:** Store the config dict on the `apply_commit` call by threading
  it through from `generate_and_commit` via a new `_config` parameter
  (underscore-prefixed to indicate internal use).
- **Alternative:** Re-read config inside `apply_commit`. This duplicates work
  and loses runtime overrides, so it's not recommended.

**`generate_and_commit` reads the new config keys and passes them:**

```python
auto_pr_enabled = _bool(git_cfg.get("auto_pr", {}).get("enabled", False))
auto_pr_target_branch = str(git_cfg.get("auto_pr", {}).get("target_branch", "main"))

apply_commit(
    message, cwd=cwd,
    signoff=signoff, amend=amend,
    push_after=push_after, push_set_upstream=push_set_upstream,
    auto_pr_enabled=auto_pr_enabled,
    auto_pr_target_branch=auto_pr_target_branch,
)
```

### 6. Return value enhancement for `apply_commit`

Currently `apply_commit` returns `None`. To surface the PR URL to callers
(including the CLI), change the return type to `str | None`:

```python
def apply_commit(...) -> str | None:
    ...
    if pr_created:
        return url
    return None
```

`generate_and_commit` continues to return `CommitMessage` — no breaking change.
Callers that need the PR URL can either:
- Use `apply_commit` directly with `auto_pr_enabled=True` and capture its
  return value.
- Read the PR URL from the CLI output (which prints it).
- Access it via a new `pr_url` attribute on the result if we extend
  `CommitMessage` with an optional third field (see alternative below).

**Alternative (if `CommitMessage` stability constraint is relaxed):** Add an
optional `pr_url: str = ""` field to `CommitMessage`. This is the most ergonomic
approach for callers. Backward compatibility: existing tuple unpacking
`subject, body = msg` still works; attribute access `.subject` and `.body` still
works. The architecture proposal recommends this approach if the constraint is
acceptable, but the primary design below keeps `CommitMessage` stable.

**Recommended approach (stable `CommitMessage`):** Keep `generate_and_commit`
returning `CommitMessage`. Add a module-level function or a simple dataclass for
combined results only if user demand emerges.

### 7. `cli.py` changes

Add new CLI flags:

```python
ap.add_argument("--auto-pr", action="store_true", dest="auto_pr", default=None,
                help="Enable automatic PR creation after push")
ap.add_argument("--no-auto-pr", action="store_false", dest="auto_pr", default=None,
                help="Disable automatic PR creation after push")
ap.add_argument("--auto-pr-target-branch", type=str, default=None,
                help="Target branch for auto-created PR (default: main)")
ap.add_argument("--auto-pr-title", type=str, default=None,
                help="Title for auto-created PR (default: commit subject)")
ap.add_argument("--auto-pr-body", type=str, default=None,
                help="Body for auto-created PR (default: commit body)")
```

Wire them into the `apply_commit` call:

```python
auto_pr_enabled = _merge_flag(args.auto_pr, git_cfg.get("auto_pr", {}).get("enabled", False))
auto_pr_target_branch = args.auto_pr_target_branch or git_cfg.get("auto_pr", {}).get("target_branch", "main")

try:
    pr_url = apply_commit(
        message, cwd=cwd, signoff=signoff, amend=amend,
        push_after=push_after, push_set_upstream=push_set_upstream,
        auto_pr_enabled=auto_pr_enabled,
        auto_pr_target_branch=auto_pr_target_branch,
        auto_pr_title=args.auto_pr_title,
        auto_pr_body=args.auto_pr_body,
    )
    msg = "Committed."
    if push_after:
        msg += "\n  Pushed."
    if pr_url:
        msg += f"\n  PR created: {pr_url}"
    print(msg)
except RuntimeError as e:
    print(f"  Error: {e}")
    return 1
```

### 8. Optional dependency strategy

`PyGithub` and `python-gitlab` should be optional extras in `pyproject.toml`:

```toml
[project.optional-dependencies]
github = ["PyGithub>=2.0,<3.0"]
gitlab = ["python-gitlab>=4.0,<5.0"]
auto-pr = ["autocommit[github]"]  # or a combined extra
```

When the user sets `auto_pr.enabled: true` but the required library is not
installed, `create_pr` raises `RuntimeError` with a message like:
"PyGithub is required for PR creation on GitHub. Install it with: pip install
autocommit[github]"

### 9. Error handling and edge cases

| Scenario | Behavior |
|---|---|
| `auto_pr.enabled: false` | No-op, zero cost. |
| Current branch == target branch | Informational log, no PR. |
| Library not installed | `RuntimeError` with install instructions. |
| Token not configured | `RuntimeError` with setup instructions. |
| Invalid/expired token | `RuntimeError` from the Python library, propagated. |
| Remote `origin` missing | `RuntimeError` from `parse_remote_repo`. |
| Network error during PR creation | `RuntimeError` from the Python library, propagated. |
| Push fails | PR creation is never attempted. |

## Scope

In scope:

- New `autocommit/utils/pr_utils.py` module with `create_pr()` and provider
  detection.
- New `autocommit/utils/pr_token.py` module (or inline in config) for token
  resolution.
- New helpers in `autocommit/utils/git_utils.py`: `parse_remote_repo()`,
  `remote_host()`.
- New `git.auto_pr.*` config keys in `params.yaml`.
- `apply_commit()` gains `auto_pr_*` keyword parameters and returns `str | None`
  (PR URL).
- `generate_and_commit()` return type unchanged (`CommitMessage`).
- New CLI flags `--auto-pr`, `--no-auto-pr`, `--auto-pr-target-branch`,
  `--auto-pr-title`, `--auto-pr-body`.
- Optional extras in `pyproject.toml` for `PyGithub` / `python-gitlab`.
- Tests for all new and changed functions.
- Updates to baseline specs (product.md, architecture.md).

Out of scope:

- Draft PRs, reviewers, labels, milestones, or any PR metadata.
- Listing, reviewing, merging, or closing PRs.
- Interactive PR creation workflow.
- Built-in merge-conflict resolution.
- Support for non-GitHub/GitLab providers in the initial version (the
  abstraction supports future extensions).
- Multi-remote or non-`origin` remote names.

## API, CLI, And Config Changes

- **Public API:**
  - `apply_commit()` gains `auto_pr_enabled`, `auto_pr_target_branch`,
    `auto_pr_title`, `auto_pr_body` keyword-only parameters.
  - `apply_commit()` return type changes from `None` to `str | None` (PR URL).
- `generate_and_commit()` continues to return `CommitMessage` (unchanged).
- New internal functions: `create_pr()`, `resolve_pr_token()`,
  `parse_remote_repo()`, `remote_host()`.

- **CLI:**
  - New flags: `--auto-pr`, `--no-auto-pr`, `--auto-pr-target-branch`,
    `--auto-pr-title`, `--auto-pr-body`.
  - CLI output includes PR URL when one is created.

- **Config:**
  - New `git.auto_pr` block with keys: `enabled` (bool, default `false`),
    `target_branch` (string, default `"main"`), `token_env_var` (string, default
    `"GITHUB_TOKEN"`), optional `keychain.service` / `keychain.key`.

- **Prompt/provider behavior:** Unchanged.

## Files Expected To Change

| File | Change |
|---|---|
| `autocommit/utils/pr_utils.py` | NEW — `create_pr()`, provider detection. |
| `autocommit/utils/pr_token.py` | NEW — `resolve_pr_token()` using keychain/env-var. |
| `autocommit/utils/git_utils.py` | Add `parse_remote_repo()`, `remote_host()`. |
| `autocommit/core.py` | `apply_commit()` gains PR params and returns `str \| None`; `generate_and_commit()` passes PR config through (return type unchanged). |
| `autocommit/params.yaml` | Add `git.auto_pr.*` keys. |
| `autocommit/cli.py` | New CLI flags; wire PR params into `apply_commit()` call; print PR URL. |
| `pyproject.toml` | Add optional extras `[github]`, `[gitlab]`, `[auto-pr]`. |
| `specrepo/specs/product.md` | Update non-goals and capabilities list. |
| `specrepo/specs/architecture.md` | Add new module descriptions and data flow. |
| `tests/test_pr_utils.py` | NEW — tests for `create_pr()` with mocked libraries. |
| `tests/test_git_utils.py` | Add tests for `parse_remote_repo()`, `remote_host()`. |
| `tests/test_core.py` | Tests for `apply_commit(auto_pr_enabled=...)` and `generate_and_commit()` return type. |
| `tests/test_autocommit.py` | Tests for new CLI flags. |

## Test Plan

| Test target | Behavior verified |
|---|---|
| `tests/test_pr_utils.py` | `create_pr()` with `PyGithub` mock creates PR with correct args. |
| `tests/test_pr_utils.py` | `create_pr()` with `python-gitlab` mock creates MR with correct args. |
| `tests/test_pr_utils.py` | `create_pr()` raises `RuntimeError` when library not installed. |
| `tests/test_pr_utils.py` | `create_pr()` raises `RuntimeError` when remote host is unknown. |
| `tests/test_pr_utils.py` | Provider detection from remote URL (github.com, gitlab.com, enterprise). |
| `tests/test_git_utils.py` | `parse_remote_repo()` parses SSH and HTTPS URLs correctly. |
| `tests/test_git_utils.py` | `parse_remote_repo()` raises `RuntimeError` when origin is missing. |
| `tests/test_git_utils.py` | `remote_host()` returns correct hostname. |
| `tests/test_core.py` | `apply_commit(auto_pr_enabled=True, ...)` calls `create_pr` after push. |
| `tests/test_core.py` | `apply_commit(auto_pr_enabled=True)` skips PR when current branch == target branch. |
| `tests/test_core.py` | `apply_commit(auto_pr_enabled=False)` never calls `create_pr`. |
| `tests/test_core.py` | `apply_commit()` returns PR URL string when PR created, `None` otherwise. |
| `tests/test_core.py` | `generate_and_commit()` passes PR config to `apply_commit` and returns `CommitMessage` (unchanged). |
| `tests/test_autocommit.py` | `--auto-pr` flag enables PR creation. |
| `tests/test_autocommit.py` | `--no-auto-pr` flag disables PR creation. |
| `tests/test_autocommit.py` | `--auto-pr-target-branch` overrides config value. |
| `tests/test_autocommit.py` | `--auto-pr-title` / `--auto-pr-body` override commit message. |
| `tests/test_autocommit.py` | PR URL printed in CLI output when PR is created. |

## Risks And Mitigations

- **Risk: Adding `PyGithub` / `python-gitlab` as optional deps increases the
  dependency surface.**
  **Mitigation:** Both are well-maintained, widely-used libraries. Optional
  extras ensure users who don't need PR functionality are not affected.
  Version pins are wide enough to avoid conflicts.

- **Risk: Changes to `apply_commit` return type (`None` → `str | None`) may
  break existing callers that expect `None`.**
  **Mitigation:** `None` is still a valid return value for the no-PR case.
  Any caller that ignores the return value still works unchanged. Callers
  that check `is None` also work. This is fully backward-compatible.

- **Risk: Provider detection from remote URL may fail on unusual Git hosting
  configurations (e.g., GitHub Enterprise with a custom hostname, or SSH URLs
  with non-standard ports).**
  **Mitigation:** The URL parsing regex handles both HTTPS and SSH formats.
  GitHub Enterprise hostnames containing "github" match the GitHub provider.
  Unknown hosts raise a clear error with the detected hostname, allowing the
  user to configure a custom mapping or submit a feature request.

- **Risk: The `_config` threading (passing config into `apply_commit`) adds an
  internal parameter.**
  **Mitigation:** Use an underscore-prefixed parameter name (`_config`) to
  signal it's internal, or refactor `apply_commit` to accept the relevant
  values directly (as proposed). The proposed approach passes the individual
  values directly, avoiding the need for a `_config` parameter.

## Baseline Spec Updates

- **Product spec:** changed — The non-goal "Not a code review or PR generation
  tool" must be removed or scoped down. The PR creation capability must be
  added to the user-facing capabilities list.
- **Architecture spec:** changed — New module descriptions, config keys, and
  data flow additions for `pr_utils.py`, `pr_token.py`, and the extended
  `apply_commit` / `generate_and_commit` flow.
- **Quality spec:** unchanged — The test strategy already supports the patterns
  needed (mocked subprocess calls; the existing mock pattern extends to mocking
  Python library calls).

## Approval Request

Approve this proposal before implementation begins.
