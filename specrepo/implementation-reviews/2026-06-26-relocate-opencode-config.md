# Implementation Review: Relocate opencode config

Status: implementation_reviewed
Date: 2026-06-26
Approval Record: `specrepo/approved/2026-06-26-remove-opencode-config/approval.md`
Approved Proposal: `specrepo/proposals/2026-06-26-relocate-opencode-config/architecture.md`

## Consistency Check

The approved architecture is internally consistent. It moves reusable opencode
mechanics out of the repository and treats `$HOME/.config/opencode` as the
user-level configuration location, while keeping repository-specific SpecRepo
state under `specrepo/`.

One file-list detail differs from the current tree: the approved proposal names
`specrepo/templates/specrepo/*` files, but this repository only has workflow
artifact templates under `specrepo/templates/`. The reusable SpecRepo bootstrap
templates currently live under `opencode-config/templates/specrepo/`, which is
the directory approved for removal. This does not block implementation because
the active in-repository guidance that exists is limited to `specrepo/README.md`
and `specrepo/workflow.md`.

## Approved Scope Mapping

- `specrepo/README.md`: update the active boundary statement to point reusable
  opencode mechanics to `$HOME/.config/opencode`.
- `specrepo/workflow.md`: update directory authority guidance to point reusable
  opencode mechanics to `$HOME/.config/opencode`.
- `opencode-config/`: remove the duplicate repository copy.
- Historical SpecRepo records: preserve as audit history, even when they refer
  to the former `opencode-config/` directory.

## Impact Review

- Public API: no impact.
- CLI: no impact.
- Runtime config: no impact to `autocommit/params.yaml`.
- LLM prompt/provider behavior: no impact.
- Git behavior: no impact.
- Tests/docs: documentation and workflow-location cleanup only.

## Verification Plan

- Run `rg -n "opencode-config|\.config/opencode" specrepo/README.md specrepo/workflow.md specrepo/templates`.
- Run `find opencode-config -maxdepth 1 -print` and confirm the directory is
  gone.
- Run `rg -n "opencode-config" .` and confirm remaining matches are historical
  records or product-provider references, not stale active guidance.
- Do not run `pytest` unless requested; no runtime code changes are in scope.

## Blockers

None.


## Verification Results

- `rg -n "opencode-config|\.config/opencode" specrepo/README.md specrepo/workflow.md specrepo/templates` shows only the new `$HOME/.config/opencode` references in `specrepo/README.md` and `specrepo/workflow.md`.
- `find opencode-config -maxdepth 1 -print` exits with `No such file or directory`, confirming the repo-root directory was removed.
- `rg -n "opencode-config" .` shows only SpecRepo request/proposal/approval/implementation-review records for this change or earlier historical workflow records. No active guidance file still points agents to a repo-root `opencode-config/` directory.
- `pytest` was not run because the approved scope did not touch runtime code, public API, CLI, provider behavior, Git behavior, or package config.
