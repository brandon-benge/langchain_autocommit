# Approval Record: Auto-Merge Flag for Automated PR Creation

Status: approved
Date: 2026-07-15
Approver: brandonbenge (via @request-author → manual spec-reviewer → @architecture-approver)
Request: `specrepo/requests/auto-pr-auto-merge.md`
Approved Proposal: `specrepo/proposals/2026-07-15-auto-pr-auto-merge/architecture.md`

## Decision

Approved

## Approved Scope

- New `create_pr_and_auto_merge()` function in
  `autocommit/utils/pr_utils.py` that calls the native auto-merge API
  after PR creation (GitHub: `enable_auto_merge`, GitLab:
  `merge_when_pipeline_succeeds`).
- New config keys `git.auto_pr.auto_merge` (bool, default `false`),
  `git.auto_pr.merge_method` (string, default `"merge"`, choices:
  `"merge"`, `"squash"`, `"rebase"`), `git.auto_pr.merge_timeout`
  (int, default `600`).
- `apply_commit()` gains `auto_pr_auto_merge`, `auto_pr_merge_method`,
  `auto_pr_merge_timeout` keyword-only parameters.
- `generate_and_commit()` reads new config keys and passes them through
  to `apply_commit()`.
- New CLI flags: `--auto-pr-auto-merge`, `--no-auto-pr-auto-merge`,
  `--auto-pr-merge-method`, `--auto-pr-merge-timeout`.
- CLI output distinguishes auto-merged PRs from plain PRs.
- Tests for all new and changed functions.
- Updates to baseline specs (product.md, architecture.md).

## Conditions

- The `create_pr()` function in `pr_utils.py` must remain unchanged for
  backward compatibility.
- The merge timeout config key is reserved for a future synchronous
  poll+merge mode; it is not used by the initial native-auto-merge
  implementation.

## Notes

1. **Native auto-merge APIs are used.** The tool enables auto-merge on
   the provider and returns immediately. It does not poll for check
   completion locally.

2. **Spec changes required.** The product spec's non-goal must be
   narrowed to allow PR auto-merging. The architecture spec's config
   table and `pr_utils.py` module description must be updated.

3. **Provider library version requirements.** PyGithub 2.x+ supports
   `enable_auto_merge`. python-gitlab 4.x+ supports
   `merge_when_pipeline_succeeds`. The optional-dependency version pins
   in `pyproject.toml` should be verified to meet these minimums.

4. **Error handling.** If the installed library version does not support
   the auto-merge API, a clear `RuntimeError` with upgrade instructions
   must be raised.
