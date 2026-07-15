# Feature Request: Automated PR Creation After Commit

Status: requested
Date: 2026-07-15
Requester: brandonbenge

## Summary

After `generate_and_commit` pushes a commit, the tool should optionally
automatically create a pull request against a configurable target branch. A new
configuration block in `params.yaml` (`git.auto_pr`) enables the feature and
specifies the target branch. When enabled and the current branch differs from
the target branch, the tool pushes and then creates a PR from the current
branch against the configured target.

## Problem

Currently the project automates commit generation and push, but the user must
manually create a PR on the remote hosting service (GitHub, GitLab, etc.) after
every push. For developers working in a feature-branch workflow, this is a
repetitive manual step that breaks the full automation chain. The project's
current non-goal of "not a PR generation tool" precludes an obvious extension
that fits the existing automation pattern.

## Desired Behavior

- A new configuration key `git.auto_pr.enabled` (boolean, default `false`) in
  `params.yaml` controls whether PR creation is attempted.
- A new configuration key `git.auto_pr.target_branch` (string, default `"main"`)
  specifies the branch the PR should target.
- After a successful commit and push in `apply_commit` /
  `generate_and_commit`, if `git.auto_pr.enabled` is `true`, the tool checks
  the current branch name.
- If the current branch is the same as `git.auto_pr.target_branch`, the PR
  creation is **skipped** with an informational message (no-op).
- If the current branch differs from `git.auto_pr.target_branch`, the tool
  creates a PR using a Python library (e.g., `PyGithub` for GitHub, or
  `python-gitlab` for GitLab), with the current branch as the source and
  `auto_pr.target_branch` as the target.
- The PR title defaults to the last commit message subject; the PR body
  defaults to the last commit message body. Overridable via keyword arguments
  in the public API.
- API token for the remote hosting service is configured following the same
  pattern as the LLM API key — either via environment variable or macOS
  Keychain (key name: `git.auto_pr.token_env_var` or
  `git.auto_pr.keychain`).
- The feature must raise a clear error when the API token is missing or the
  Python library is not installed.

## Acceptance Criteria

1. A user can set `git.auto_pr.enabled: true` and
   `git.auto_pr.target_branch: "main"` in `params.yaml`, run
   `generate_and_commit` on a feature branch, and observe that a PR is created
   against `main` after the push.
2. When `git.auto_pr.enabled` is `false` (default), no PR creation is attempted
   regardless of the current branch.
3. When the current branch equals `git.auto_pr.target_branch`, no PR is
   created and a non-error informational message is logged.
4. When the API token is missing or the Python library is not installed, a
   clear error is raised (not a silent skip).
5. The `generate_and_commit` function accepts keyword overrides for PR
   settings (e.g., `auto_pr_enabled`, `auto_pr_target_branch`,
   `auto_pr_title`, `auto_pr_body`), consistent with the existing override
   pattern.
6. All acceptance criteria are covered by deterministic tests (mocking the
   Python library calls).

## Constraints

- PR creation must not modify the working tree or staged changes.
- The feature must only attempt PR creation after a successful `git push`.
- API token must follow the existing security pattern: environment variable or
  macOS Keychain, never hardcoded in config.
- The Python PR library (e.g., `PyGithub`) must be an optional dependency —
  installed only when the user opts into this feature.
- Default behavior (`enabled: false`) must be a no-op — zero overhead for
  users who do not enable it.
- The `CommitMessage` NamedTuple signature must remain stable (subject, body).

## Non-Goals

- Not a full PR management tool (no listing, reviewing, merging, or closing
  PRs).
- No interactive PR creation workflow.
- No support for draft PRs, reviewers, labels, or other PR metadata in the
  initial version.
- No built-in merge-conflict resolution.
- No support for non-GitHub/GitLab hosting services in the initial version
  (extensible via CLI abstraction).

## Impacted Areas

- Public API: yes — `apply_commit` and `generate_and_commit` may gain new
  keyword arguments.
- CLI: unknown — new CLI flags may be added for PR settings.
- Config: yes — new `git.auto_pr.*` keys in `params.yaml`.
- External integrations: yes — Python PR library (e.g., `PyGithub`) and
  remote hosting API.
- Data/storage behavior: no
- Tests/docs: yes — new test coverage for PR creation logic; documentation for
  the new config keys and behavior.

## Notes

- The current non-goal in `specrepo/specs/product.md` ("Not a code review or PR
  generation tool") will need to be updated or scoped down if this feature is
  approved.
- The exact Python library (e.g., `PyGithub` for GitHub, `python-gitlab` for
  GitLab) and the abstraction to support multiple hosting providers are design
  decisions for the architecture proposal.
- API token configuration should reuse the existing env-var / macOS Keychain
  pattern to keep a consistent UX (see `autocommit/utils/keychain.py`).
