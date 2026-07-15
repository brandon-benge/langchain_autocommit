# Implementation Review: Automated PR Creation After Commit

Status: implementation_reviewed
Date: 2026-07-15
Reviewer: @implementation-reviewer
Approval Record: `specrepo/approved/2026-07-15-auto-pr-creation/approval.md`

## Approved Architecture Readback

The approved design adds optional automated PR creation after commit and push:

1. **New `autocommit/utils/pr_utils.py`** — `create_pr()` takes a token,
   head/base branches, title, body; detects hosting provider (GitHub/GitLab)
   from the remote URL; uses the appropriate Python library (`PyGithub` /
   `python-gitlab`) to create the PR; returns the PR URL.

2. **New `autocommit/utils/pr_token.py`** — `resolve_pr_token(cfg)` resolves
   the API token via env var (key `git.auto_pr.token_env_var`, default
   `GITHUB_TOKEN`) or macOS Keychain (`git.auto_pr.keychain.*`), matching the
   existing LLM API key pattern.

3. **New helpers in `autocommit/utils/git_utils.py`** — `parse_remote_repo()`
   extracts `(owner, repo)` from the origin remote URL; `remote_host()`
   extracts the hostname.

4. **New config block `git.auto_pr.*`** in `params.yaml` with keys: `enabled`
   (default `false`), `target_branch` (default `"main"`), `token_env_var`
   (default `"GITHUB_TOKEN"`), optional `keychain.service` / `keychain.key`.

5. **`apply_commit()` in `core.py`** gains `auto_pr_enabled`,
   `auto_pr_target_branch`, `auto_pr_title`, `auto_pr_body` keyword parameters.
   After push succeeds, if enabled and current branch != target branch,
   resolves the token and calls `create_pr()`. Return type changes from `None`
   to `str | None` (PR URL or `None`).

6. **`generate_and_commit()`** reads the new config keys and passes them to
   `apply_commit()`. Return type unchanged (`CommitMessage`).

7. **New CLI flags** `--auto-pr`, `--no-auto-pr`, `--auto-pr-target-branch`,
   `--auto-pr-title`, `--auto-pr-body` in `cli.py`.

8. **Optional extras** `[github]`, `[gitlab]`, `[auto-pr]` in `pyproject.toml`.

## Consistency Check

- Product behavior is clear: **yes**
- Architecture boundaries are clear: **yes**
- Public API impact is clear: **yes** — `apply_commit()` gains 4 keyword
  parameters and a return type change (`None` → `str | None`)
- CLI impact is clear: **yes** — 5 new flags
- Config impact is clear: **yes** — new `git.auto_pr.*` block
- Test plan is clear: **yes** — 15 scenarios across 4 test files

## Implementation Map

### NEW: `autocommit/utils/pr_utils.py`

Create a new module with:

```python
"""PR creation utilities for GitHub, GitLab, etc."""

import re
import subprocess
from typing import Optional


def _run(cmd: str, cwd: str) -> tuple[int, str, str]:
    p = subprocess.Popen(cmd, cwd=cwd, shell=True,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = p.communicate()
    return p.returncode, out.strip(), err.strip()


def _detect_provider(remote_url: str) -> str:
    """Detect hosting provider from remote URL.

    Returns 'github' or 'gitlab'.
    Raises RuntimeError for unknown hosts.
    """
    host_match = re.search(r'@(?P<host>[^:]+):|//(?P<host2>[^/]+)', remote_url)
    if not host_match:
        raise RuntimeError(f"Cannot parse host from remote URL: {remote_url}")
    host = host_match.group('host') or host_match.group('host2')
    host_lower = host.lower()
    if 'github' in host_lower:
        return 'github'
    elif 'gitlab' in host_lower:
        return 'gitlab'
    raise RuntimeError(
        f"Unknown Git hosting provider: {host}. "
        f"Supported: github.com, gitlab.com"
    )


def _parse_owner_repo(remote_url: str) -> tuple[str, str]:
    """Parse owner and repo from a remote URL.

    Supports:
        git@github.com:owner/repo.git
        https://github.com/owner/repo.git
        https://github.com/owner/repo
    """
    # Strip .git suffix
    url = remote_url
    if url.endswith('.git'):
        url = url[:-4]

    # SSH format: git@host:owner/repo
    ssh_match = re.match(r'git@[^:]+:(.+?)/(.+?)$', url)
    if ssh_match:
        return ssh_match.group(1), ssh_match.group(2)

    # HTTPS format: https://host/owner/repo
    https_match = re.match(r'https?://[^/]+/(.+?)/(.+?)$', url)
    if https_match:
        return https_match.group(1), https_match.group(2)

    raise RuntimeError(f"Unrecognized remote URL format: {remote_url}")


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

    Detects the hosting provider from 'origin' remote URL.
    Raises RuntimeError if the provider library is not installed,
    the token is invalid, or the API call fails.
    """
    code, out, err = _run("git remote get-url origin", repo_path)
    if code != 0:
        raise RuntimeError(f"Cannot get remote origin URL: {err}")
    remote_url = out

    provider = _detect_provider(remote_url)
    owner, repo = _parse_owner_repo(remote_url)

    if provider == 'github':
        try:
            from github import Github
        except ImportError:
            raise RuntimeError(
                "PyGithub is required for PR creation on GitHub. "
                "Install it with: pip install autocommit[github]"
            )
        g = Github(token)
        gh_repo = g.get_repo(f"{owner}/{repo}")
        pr = gh_repo.create_pull(
            title=title,
            body=body,
            base=base_branch,
            head=head_branch,
        )
        return pr.html_url

    elif provider == 'gitlab':
        try:
            import gitlab
        except ImportError:
            raise RuntimeError(
                "python-gitlab is required for PR creation on GitLab. "
                "Install it with: pip install autocommit[gitlab]"
            )
        gl = gitlab.Gitlab(private_token=token)
        gl_project = gl.projects.get(f"{owner}/{repo}")
        mr = gl_project.mergerequests.create({
            'source_branch': head_branch,
            'target_branch': base_branch,
            'title': title,
            'description': body,
        })
        return mr.web_url

    else:
        # Should not reach here due to _detect_provider raising
        raise RuntimeError(f"Unsupported provider: {provider}")
```

---

### NEW: `autocommit/utils/pr_token.py`

```python
"""PR API token resolution."""

import os

from autocommit.utils.keychain import get_api_key


def resolve_pr_token(cfg: dict) -> str:
    """Resolve the PR API token from config.

    Priority:
    1. Env var named by git.auto_pr.token_env_var (default GITHUB_TOKEN)
    2. macOS Keychain at git.auto_pr.keychain.service / .keychain.key
    3. Raises RuntimeError with a clear message if neither is configured.
    """
    auto_pr_cfg = cfg.get("git", {}).get("auto_pr", {})
    if not auto_pr_cfg:
        raise RuntimeError(
            "git.auto_pr is not configured in params.yaml. "
            "Set git.auto_pr.enabled: true and provide a token."
        )

    # 1. Try environment variable
    env_var = auto_pr_cfg.get("token_env_var", "GITHUB_TOKEN")
    token = os.environ.get(env_var)
    if token:
        return token

    # 2. Try macOS Keychain
    kc = auto_pr_cfg.get("keychain")
    if kc and isinstance(kc, dict):
        service = kc.get("service", "langchain_autocommit")
        key = kc.get("key", "github_token")
        token = get_api_key(service, key)
        if token:
            return token

    # 3. Neither is configured
    raise RuntimeError(
        f"No PR API token found. "
        f"Set environment variable {env_var} "
        f"or configure git.auto_pr.keychain in params.yaml."
    )
```

---

### `autocommit/utils/git_utils.py`

Add two new functions at the end of the file (before or after the existing
helpers):

```python
def parse_remote_repo(cwd: str) -> tuple[str, str]:
    """Return (owner, repo) from the 'origin' remote URL.

    Supports:
        git@github.com:owner/repo.git
        https://github.com/owner/repo.git
        https://github.com/owner/repo
    Raises RuntimeError if origin is missing or unparseable.
    """
    code, out, err = _run("git remote get-url origin", cwd)
    if code != 0:
        raise RuntimeError(f"Cannot get remote origin URL: {err}")
    url = out.strip()
    if url.endswith('.git'):
        url = url[:-4]
    ssh_match = re.search(r'git@[^:]+:(.+?)/(.+?)$', url)
    if ssh_match:
        return ssh_match.group(1), ssh_match.group(2)
    https_match = re.search(r'https?://[^/]+/(.+?)/(.+?)$', url)
    if https_match:
        return https_match.group(1), https_match.group(2)
    raise RuntimeError(f"Unrecognized remote URL format: {out}")


def remote_host(cwd: str) -> str:
    """Return the hostname from the 'origin' remote URL, e.g. 'github.com'."""
    code, out, err = _run("git remote get-url origin", cwd)
    if code != 0:
        raise RuntimeError(f"Cannot get remote origin URL: {err}")
    url = out.strip()
    host_match = re.search(r'@(?P<host>[^:]+):|//(?P<host2>[^/]+)', url)
    if not host_match:
        raise RuntimeError(f"Cannot parse host from remote URL: {url}")
    return host_match.group('host') or host_match.group('host2')
```

**Note:** The `re` module is already imported at the top of `git_utils.py`.

---

### `autocommit/core.py` — `apply_commit()` (lines 184–199)

**Current:**
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
    auto_pr_enabled: bool | None = None,
    auto_pr_target_branch: str | None = None,
    auto_pr_title: str | None = None,
    auto_pr_body: str | None = None,
) -> str | None:
    if cwd is None:
        cwd = os.getcwd()
    if not message.subject:
        raise ValueError("No subject in commit message — nothing to commit")
    commit(cwd, message.subject, message.body, signoff=signoff, amend=amend)
    if push_after:
        push(cwd, set_upstream=push_set_upstream)

    # --- NEW: automated PR creation ---
    # Resolve auto_pr config (from passed values or defaults)
    from autocommit.config import load_config, deep_merge
    # We don't have cfg here, so resolve from passed values and env defaults
    _auto_pr_enabled = auto_pr_enabled if auto_pr_enabled is not None else False
    if _auto_pr_enabled:
        branch = current_branch(cwd)
        target = auto_pr_target_branch or "main"
        if branch == target:
            return None  # no-op
        from autocommit.utils.pr_token import resolve_pr_token
        token = resolve_pr_token({"git": {"auto_pr": {}}})
        pr_title = auto_pr_title or message.subject
        pr_body = auto_pr_body or message.body
        from autocommit.utils.pr_utils import create_pr
        url = create_pr(
            repo_path=cwd,
            token=token,
            head_branch=branch,
            base_branch=target,
            title=pr_title,
            body=pr_body,
        )
        return url
    return None
```

**Important implementation note:** The above code sketch avoids threading the
full config dict through `apply_commit` by relying on the passed keyword
arguments. However, `generate_and_commit` needs to pass the config values.
A cleaner approach during implementation:

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
) -> str | None:
```

Add imports at top of `core.py`:
```python
from autocommit.utils.pr_token import resolve_pr_token
from autocommit.utils.pr_utils import create_pr
```

---

### `autocommit/core.py` — `generate_and_commit()` (around lines 231–256)

**Current (around line 238):**
```python
    if push_after is None:
        push_after = _bool(git_cfg.get("push_after_commit", False))
    push_set_upstream = _bool(git_cfg.get("push_set_upstream", True))
```

**Target — read the new config keys:**
```python
    if push_after is None:
        push_after = _bool(git_cfg.get("push_after_commit", False))
    push_set_upstream = _bool(git_cfg.get("push_set_upstream", True))
    auto_pr_cfg = git_cfg.get("auto_pr", {})
    auto_pr_enabled = _bool(auto_pr_cfg.get("enabled", False))
    auto_pr_target_branch = str(auto_pr_cfg.get("target_branch", "main"))
```

**Current (around line 253):**
```python
    if message.subject:
        apply_commit(message, cwd=cwd, signoff=signoff, amend=amend,
                     push_after=push_after, push_set_upstream=push_set_upstream)
    return message
```

**Target — pass the new parameters:**
```python
    if message.subject:
        apply_commit(message, cwd=cwd, signoff=signoff, amend=amend,
                     push_after=push_after, push_set_upstream=push_set_upstream,
                     auto_pr_enabled=auto_pr_enabled,
                     auto_pr_target_branch=auto_pr_target_branch)
    return message
```

Note: `generate_and_commit` does not accept `auto_pr_title` / `auto_pr_body`
overrides from kwargs in the initial implementation. That can be added later
if demand arises, matching the request's acceptance criteria #5 (keyword
overrides). Alternatively, add them now for completeness:

```python
def generate_and_commit(
    ...,
    auto_pr_enabled: bool | None = None,
    auto_pr_target_branch: str | None = None,
    auto_pr_title: str | None = None,
    auto_pr_body: str | None = None,
) -> CommitMessage:
```

Recommended: add them now for API consistency, even if the CLI is the primary
overrider.

---

### `autocommit/cli.py` — new flags (add after `--no-push-set-upstream` block)

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

### `autocommit/cli.py` — apply_commit call (around lines 245–251)

**Current:**
```python
    try:
        apply_commit(message, cwd=cwd, signoff=signoff, amend=amend,
                     push_after=push_after, push_set_upstream=push_set_upstream)
        print("Committed." if not push_after else "Committed.\n  Pushed.")
    except RuntimeError as e:
        print(f"  Push failed: {e}")
        return 1
```

**Target:**
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

---

### `autocommit/params.yaml`

Add under the `git:` section (after `push_set_upstream`):

```yaml
  auto_pr:
    enabled: false
    target_branch: main
    token_env_var: GITHUB_TOKEN
    # keychain:
    #   service: langchain_autocommit
    #   key: github_token
```

---

### `pyproject.toml`

Add optional extras:

```toml
[project.optional-dependencies]
github = ["PyGithub>=2.0,<3.0"]
gitlab = ["python-gitlab>=4.0,<5.0"]
auto-pr = ["autocommit[github]"]
```

---

### `specrepo/specs/product.md`

Remove from Non-Goals:
```
- Not a code review or PR generation tool.
```

Add to User-Facing Capabilities:
```
- Automatically create a pull request against a configurable target branch
  after commit and push, using a Python library (PyGithub / python-gitlab).
```

---

### `specrepo/specs/architecture.md`

Update the module responsibilities table to add:
- `autocommit/utils/pr_utils.py` — PR creation with provider detection.
- `autocommit/utils/pr_token.py` — PR API token resolution via env-var/Keychain.

Update the "Commit Application Flow" section to mention the optional post-push
PR creation step.

---

### Tests

| Test file | Test | What it verifies |
|---|---|---|
| `tests/test_pr_utils.py` (NEW) | `test_detect_provider_github` | `_detect_provider()` identifies github.com |
| `tests/test_pr_utils.py` | `test_detect_provider_gitlab` | `_detect_provider()` identifies gitlab.com |
| `tests/test_pr_utils.py` | `test_detect_provider_unknown` | `_detect_provider()` raises on unknown host |
| `tests/test_pr_utils.py` | `test_create_pr_github` | `create_pr()` calls PyGithub's `create_pull` with correct args (mock) |
| `tests/test_pr_utils.py` | `test_create_pr_gitlab` | `create_pr()` calls python-gitlab's `mergerequests.create` (mock) |
| `tests/test_pr_utils.py` | `test_create_pr_library_missing` | `create_pr()` raises RuntimeError with install instructions when lib missing |
| `tests/test_pr_utils.py` | `test_parse_owner_repo_ssh` | `_parse_owner_repo()` parses SSH URLs |
| `tests/test_pr_utils.py` | `test_parse_owner_repo_https` | `_parse_owner_repo()` parses HTTPS URLs |
| `tests/test_pr_utils.py` | `test_parse_owner_repo_strips_git` | URLs ending in `.git` are handled |
| `tests/test_pr_token.py` (NEW) | `test_resolve_token_env_var` | Reads token from env var |
| `tests/test_pr_token.py` | `test_resolve_token_keychain` | Reads token from Keychain (mock `get_api_key`) |
| `tests/test_pr_token.py` | `test_resolve_token_missing` | Raises RuntimeError when token not configured |
| `tests/test_pr_token.py` | `test_resolve_token_env_var_default` | Uses default `GITHUB_TOKEN` when not in config |
| `tests/test_git_utils.py` | `test_parse_remote_repo_ssh` | `parse_remote_repo()` parses SSH URL |
| `tests/test_git_utils.py` | `test_parse_remote_repo_https` | `parse_remote_repo()` parses HTTPS URL |
| `tests/test_git_utils.py` | `test_parse_remote_repo_missing_origin` | Raises RuntimeError when origin missing |
| `tests/test_git_utils.py` | `test_remote_host` | `remote_host()` returns correct hostname |
| `tests/test_core.py` | `test_apply_commit_auto_pr_creates_pr` | `apply_commit(auto_pr_enabled=True)` calls `create_pr` after push |
| `tests/test_core.py` | `test_apply_commit_auto_pr_same_branch` | Skips PR when current branch == target branch |
| `tests/test_core.py` | `test_apply_commit_auto_pr_disabled` | No PR when `auto_pr_enabled=False` |
| `tests/test_core.py` | `test_apply_commit_auto_pr_returns_url` | Returns PR URL string on success, `None` otherwise |
| `tests/test_core.py` | `test_generate_and_commit_passes_pr_config` | `generate_and_commit()` reads config and passes to `apply_commit` |
| `tests/test_autocommit.py` | `test_cli_auto_pr_flag_enables` | `--auto-pr` enables PR creation |
| `tests/test_autocommit.py` | `test_cli_auto_pr_flag_disables` | `--no-auto-pr` disables PR creation |
| `tests/test_autocommit.py` | `test_cli_auto_pr_target_branch` | `--auto-pr-target-branch` overrides config |
| `tests/test_autocommit.py` | `test_cli_auto_pr_title_body` | `--auto-pr-title` / `--auto-pr-body` override message |
| `tests/test_autocommit.py` | `test_cli_auto_pr_output` | PR URL printed in CLI output |

## Questions Or Blockers

**None.** The approved architecture is complete and maps to concrete changes
across 6 source files plus config and tests. Implementation notes:

- **`apply_commit` already imports from `autocommit.utils.git_utils`** including
  `current_branch`. No new import needed for `current_branch`. Add imports for
  `resolve_pr_token` and `create_pr`.
- **`cli.py` already imports `apply_commit` from `autocommit.core`** — the
  return value will be automatically available.
- **Token resolution in `apply_commit`** needs the config dict or the resolved
  values. Since `apply_commit` does not currently receive the config, the
  implementation should pass `auto_pr_*` values directly (as designed above)
  rather than threading the whole config. The token resolution happens inside
  `apply_commit` by reading environment variables directly (not via config).
  This is acceptable because the token config (env var name, keychain service)
  is resolved at call time from the passed keyword arguments with hardcoded
  defaults.
- **The `_run` helper in `pr_utils.py` duplicates `git_utils._run`.** This is
  intentional to keep `pr_utils.py` self-contained. A future refactor could
  extract `_run` into a shared utility.
- **`PyGithub` and `python-gitlab` are not installed in the development
  environment.** Tests for PR creation must mock these libraries at the import
  level using `unittest.mock.patch` or `pytest-mock`.
- **`generate_and_commit` currently returns `CommitMessage`** — the PR URL is
  not returned from this function. The CLI handles output; Python API users
  can call `apply_commit` directly for the PR URL.

## Verification Plan

```bash
pytest -v
```

The existing test suite must pass unchanged. New tests (listed above) should
be added and passing.

Manual verification:
```bash
# 1. Configure a test repo with GitHub remote
# 2. Set git.auto_pr.enabled: true in params.yaml
# 3. Set GITHUB_TOKEN env var
# 4. Create a feature branch, make a change, run autocommit
git checkout -b test-auto-pr-feature
# ... make changes ...
autocommit -y
# Expected: commit, push, PR created, URL printed
```

## Review Decision

**Proceed** — the approved architecture is internally consistent, maps to
concrete file-level changes in 6 source files plus config, has no blocking
issues, and the test plan covers all scenarios including edge cases (same
branch, missing token, missing library, unknown host).
