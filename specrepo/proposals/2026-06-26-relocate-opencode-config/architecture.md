# Architecture Proposal: Relocate opencode config

Status: awaiting_approval
Date: 2026-06-26
Request: `specrepo/requests/2026-06-26-relocate-opencode-config.md`

## Summary

Remove the repository-owned `opencode-config/` bundle after updating active
SpecRepo guidance to treat reusable opencode configuration as external
user-level configuration at `$HOME/.config/opencode`.

The repository will continue to own only project-specific SpecRepo state under
`specrepo/`, while reusable opencode agents, permissions, prompts, and
templates are maintained outside this project.

## Current Architecture

`specrepo/spec.yaml` defines this repository's SpecRepo state, source roots,
test roots, default verification command, and workflow directories.

`specrepo/workflow.md` currently says reusable opencode mechanics belong in the
root-level `opencode-config/` directory, while repository-specific facts belong
under `specrepo/`.

`specrepo/README.md` and `specrepo/templates/specrepo/` content also point to
`opencode-config/` as the in-repository location for reusable opencode
configuration. Historical request/proposal/approval/review records from
`2026-06-26-separate-opencode-specrepo-responsibilities` describe the previous
approved direction and should remain as history.

The root-level `opencode-config/` directory currently contains:

- opencode agent profiles under `agents/`.
- root opencode configuration files `opencode.jsonc` and `opencode.yaml`.
- reusable SpecRepo templates under `templates/specrepo/`.
- reusable workflow documentation, including `README.md` and
  `feature-development.md`.

## Proposed Architecture

Reusable opencode configuration is no longer repository-owned. Its expected
local location is `$HOME/.config/opencode`, matching the user's completed copy.

Active repository guidance should describe this boundary:

- `specrepo/` remains the repository-specific source of truth for requests,
  proposals, approvals, implementation reviews, baseline specs, templates,
  project facts, and verification commands.
- `$HOME/.config/opencode` is the user-level location for reusable opencode
  agent mechanics, including agent profiles, permissions, prompts, and generic
  workflow guidance.
- The repository root should not contain `opencode-config/`.

Historical SpecRepo records should not be rewritten simply because they mention
the former directory. They should remain as audit history unless a historical
file is being reused as active workflow guidance.

## Scope

In scope:

- Update active SpecRepo documentation and templates that currently direct
  users or agents to the root-level `opencode-config/` directory.
- Remove the root-level `opencode-config/` directory.
- Record verification showing that any remaining references are historical or
  product-provider references, not stale active guidance.

Out of scope:

- Modifying `$HOME/.config/opencode`.
- Redesigning opencode agents, permissions, or reusable templates.
- Changing LangChain AutoCommit runtime code, public API, CLI flags, provider
  behavior, Git behavior, or package config.
- Rewriting old approved records solely to match the new location.

## API, CLI, And Config Changes

- Public API: none.
- CLI: none.
- Config: root-level repository opencode configuration directory removed;
  runtime `autocommit/params.yaml` unchanged.
- Prompt/provider behavior: none.

## Files Expected To Change

- `specrepo/workflow.md`: replace root-level `opencode-config/` guidance with
  `$HOME/.config/opencode` or external opencode config guidance.
- `specrepo/README.md`: update the boundary statement for reusable opencode
  mechanics.
- `specrepo/templates/specrepo/root-README.md`: update generated root README
  guidance.
- `specrepo/templates/specrepo/workflow.md`: update generated workflow
  guidance.
- `specrepo/templates/specrepo/README.md`: update generated SpecRepo README
  guidance.
- `opencode-config/`: remove after references are updated.
- `specrepo/implementation-reviews/2026-06-26-relocate-opencode-config.md`:
  record implementation review and verification results after approval.

## Test Plan

- `rg -n "opencode-config|\\.config/opencode" specrepo/README.md specrepo/workflow.md specrepo/templates`
  should show only the new active external location language and no stale
  root-level directory guidance.
- `find opencode-config -maxdepth 1 -print` should fail because the directory
  has been removed.
- `rg -n "opencode-config" .` should be reviewed. Remaining matches are
  acceptable only when they are historical SpecRepo records for earlier
  requests/proposals/approvals/reviews.
- `pytest` is not required because no runtime code changes are planned; if run,
  it should continue to pass.

## Risks And Mitigations

- Risk: Future agents may not know where reusable opencode configuration lives.
  Mitigation: Active workflow and README files will explicitly name
  `$HOME/.config/opencode`.
- Risk: Removing the repository copy may hide reusable templates from future
  bootstrap work.
  Mitigation: This change assumes the user-level copy is now the reusable
  source, and the repository remains focused on local SpecRepo state.
- Risk: Historical references may appear stale in search results.
  Mitigation: Preserve history but document that historical records are not
  active guidance.

## Baseline Spec Updates

- Product spec: unchanged.
- Architecture spec: unchanged.
- Quality spec: unchanged.

The baseline product and package architecture specs describe LangChain
AutoCommit runtime behavior. The active workflow documentation under
`specrepo/` is sufficient for this repository workflow-location change.

## Approval Request

Approve this proposal before implementation begins.
