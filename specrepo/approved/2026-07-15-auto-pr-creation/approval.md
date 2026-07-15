# Approval Record: Automated PR Creation After Commit

Status: approved
Date: 2026-07-15
Approver: user (via @request-author → manual spec-reviewer → @architecture-approver)
Request: `specrepo/requests/auto-pr-creation.md`
Approved Proposal: `specrepo/proposals/2026-07-15-auto-pr-creation/architecture.md`

## Decision

Approved

## Approved Scope

- New `autocommit/utils/pr_utils.py` module with `create_pr()` function and
  provider detection (GitHub via PyGithub, GitLab via python-gitlab).
- New `autocommit/utils/pr_token.py` module with `resolve_pr_token()` using
  the existing env-var / macOS Keychain pattern.
- New helpers in `autocommit/utils/git_utils.py`: `parse_remote_repo()` and
  `remote_host()`.
- New `git.auto_pr.*` config block in `autocommit/params.yaml` with keys:
  `enabled` (default `false`), `target_branch` (default `"main"`),
  `token_env_var` (default `"GITHUB_TOKEN"`), optional `keychain.*`.
- `apply_commit()` gains `auto_pr_enabled`, `auto_pr_target_branch`,
  `auto_pr_title`, `auto_pr_body` keyword parameters and returns `str | None`
  (PR URL on success, `None` otherwise).
- `generate_and_commit()` return type unchanged (`CommitMessage`); passes PR
  config through to `apply_commit()`.
- New CLI flags `--auto-pr`, `--no-auto-pr`, `--auto-pr-target-branch`,
  `--auto-pr-title`, `--auto-pr-body` in `autocommit/cli.py`.
- Optional extras `[github]`, `[gitlab]`, `[auto-pr]` in `pyproject.toml`.
- Updates to `specrepo/specs/product.md` (remove "Not a code review or PR
  generation tool" non-goal; add PR creation to capabilities list).
- Updates to `specrepo/specs/architecture.md` (new module descriptions and
  extended flow).
- Tests for all new and changed functions.

## Conditions

None

## Notes

1. **`apply_commit` return type changes from `None` to `str | None`.** This is
   backward-compatible: existing callers that ignore the return value still
   work, and `None` is returned when no PR is created.

2. **`generate_and_commit` is NOT changing its return type.** It continues to
   return `CommitMessage`. The PR URL is surfaced either via the CLI output or
   by calling `apply_commit` directly. A future enhancement may extend
   `CommitMessage` with an optional `pr_url` field if demand arises.

3. **Provider detection uses the remote URL hostname.** GitHub.com and any host
   containing "github" map to PyGithub; GitLab.com and any host containing
   "gitlab" map to python-gitlab. Unknown hosts raise a clear error.

4. **The PR libraries (PyGithub, python-gitlab) are optional extras**, not
   required dependencies. Users who set `auto_pr.enabled: true` without
   installing the library will get a clear `RuntimeError` with install
   instructions.

5. **No merge happens locally.** The PR is created on the remote hosting
   service; the merge is performed by whoever approves the PR on the remote
   side. This is standard GitHub/GitLab flow.
