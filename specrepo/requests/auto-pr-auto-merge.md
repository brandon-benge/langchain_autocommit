# Feature Request: Auto-Merge Flag for Automated PR Creation

Status: requested
Date: 2026-07-15
Requester: brandonbenge

## Summary

Extend the existing `git.auto_pr` feature with an optional auto-merge
flag. When enabled, after a pull request is created and all required
status checks (CI, tests, etc.) pass on the remote hosting service, the
PR is automatically merged into the target branch.

## Problem

The current `git.auto_pr` feature creates a pull request after a
successful commit and push, but the user must still manually merge the
PR on the remote hosting service. For fully automated deployment
pipelines or developers working on simple feature branches that only
need to pass CI, this manual merge is a remaining friction point that
breaks end-to-end automation.

## Desired Behavior

- A new configuration key `git.auto_pr.auto_merge` (boolean, default
  `false`) in `params.yaml` controls whether auto-merge is attempted.
- When `git.auto_pr.auto_merge` is `true` and a PR is created (or
  already exists for the current branch), the tool waits for all
  required status checks on the PR to pass.
- Once checks pass (or if they have already passed), the tool merges
  the PR into the target branch using the remote hosting provider's API.
- When `git.auto_pr.auto_merge` is `false` (default), no merge is
  attempted — the PR is created and left open for manual merge, exactly
  as today.
- The merge method should be configurable (e.g., merge commit,
  squash-merge, rebase-merge) to align with project conventions.
- Auto-merge must only be attempted after a successful PR creation.
  If PR creation is skipped (e.g., current branch equals target branch),
  auto-merge is also skipped.
- A polling timeout or max-wait duration should be configurable so the
  tool does not hang indefinitely when checks never complete.
  If the timeout is reached without all checks passing, the tool should
  report the timeout as a warning and leave the PR open.
- The feature must raise a clear error when the remote hosting
  provider's API does not support auto-merge or when the authenticated
  user lacks permission to merge.

## Acceptance Criteria

1. A user can set `git.auto_pr.auto_merge: true` in `params.yaml`, run
   `generate_and_commit` on a feature branch, and observe that after PR
   creation the PR is automatically merged once its status checks pass.
2. When `git.auto_pr.auto_merge` is `false` (default), no merge is
   attempted — behavior matches today's auto_pr feature exactly.
3. When the current branch equals the target branch (so no PR is
   created), auto-merge is skipped with an informational message.
4. When status checks fail or never complete within the configured
   timeout, the PR is left open and a warning is reported (the tool does
   not exit with an error in this case, since the PR may still be merged
   manually).
5. The merge method (merge commit, squash, rebase) is configurable via
   `git.auto_pr.merge_method` with a sensible default (e.g.,
   `"merge_commit"`).
6. The `generate_and_commit` and `apply_commit` functions accept keyword
   overrides for auto-merge settings (e.g., `auto_pr_auto_merge`,
   `auto_pr_merge_method`, `auto_pr_merge_timeout`), consistent with the
   existing override pattern.
7. All acceptance criteria are covered by deterministic tests (mocking
   the Python library calls).

## Constraints

- Auto-merge must not modify the working tree or staged changes.
- The feature must only attempt merging after a successful PR creation.
- API token for merge operations reuses the same `git.auto_pr.token_env_var`
  or keychain configuration already resolved for PR creation.
- The Python PR library (e.g., `PyGithub`) must already be installed as
  an optional dependency (part of the existing auto_pr feature).
- Default behavior (`auto_merge: false`) must be a no-op — zero overhead
  for users who do not enable it.
- Polling for status checks must be rate-limit-aware and should not make
  excessive API calls. A reasonable polling interval (e.g., every 10–30
  seconds) is expected.
- The timeout should have a practical default (e.g., 10 minutes) and be
  configurable.
- The `CommitMessage` NamedTuple signature must remain stable (subject,
  body).

## Non-Goals

- No rewriting of PR history or force-pushing to the target branch.
- No support for merge queues or complex merge strategies (e.g.,
  merge trains, stacked PRs) in the initial version.
- No support for approving PRs or adding reviewers — the feature only
  merges when checks pass.
- No interactive merge confirmation flow (the merge is fully automated
  when enabled).
- No support for non-GitHub/GitLab hosting services initially (follows
  the existing auto_pr constraint; extensible via provider abstraction).
- No support for merging PRs that have merge conflicts — the merge is
  only attempted when the remote API reports the PR as mergeable.

## Impacted Areas

- Public API: yes — `apply_commit` and `generate_and_commit` may gain
  new keyword arguments for auto-merge settings.
- CLI: yes — new CLI flags for `--auto-pr-auto-merge`,
  `--auto-pr-merge-method`, `--auto-pr-merge-timeout`.
- Config: yes — new `git.auto_pr.auto_merge`, `git.auto_pr.merge_method`,
  `git.auto_pr.merge_timeout` keys in `params.yaml`.
- External integrations: yes — extended use of the PR Python library
  (e.g., `PyGithub`) to poll status checks and merge.
- Data/storage behavior: no
- Tests/docs: yes — new test coverage for auto-merge logic; documentation
  for the new config keys and CLI flags.

## Notes

- GitHub's native auto-merge feature (enable via API, let GitHub merge
  when checks pass) and GitLab's "merge when pipeline succeeds" (MWPS)
  are potential design candidates that avoid local polling. The
  architecture proposal should evaluate which approach (native
  auto-merge API vs. local polling + merge) best fits the project.
- The existing approved architecture in
  `specrepo/proposals/2026-07-15-auto-pr-creation/architecture.md` and
  the approval record in
  `specrepo/approved/2026-07-15-auto-pr-creation/approval.md` include a
  non-goal: "No listing, reviewing, merging, or closing PRs." This
  non-goal specifically excluded merging, which this request proposes to
  add. The product spec in `specrepo/specs/product.md` states: "It does
  not manage branches, merge pull requests, close pull requests, or
  manage releases. PR creation is supported only as an optional post-push
  step." Both will need updating if this request is approved.
