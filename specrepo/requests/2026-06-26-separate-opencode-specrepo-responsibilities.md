# Feature Request: Separate opencode and SpecRepo responsibilities

Status: requested
Date: 2026-06-26
Requester: user

## Summary

Clarify and separate the responsibilities of `opencode-config/` and
`specrepo/` for spec-driven development with opencode.

`opencode-config/` should contain reusable opencode configuration, agent
profiles, and workflow guidance that can be copied across repositories.
`specrepo/` should contain repository-specific product, architecture, quality,
request, approval, and implementation-review records.

## Problem

The current repository contains SpecRepo workflow material in two places:
`opencode-config/` and `specrepo/`. Some opencode agent profiles and workflow
guides describe reusable roles, but they also include repository-specific paths,
verification commands, and implementation assumptions. This makes it harder to
reuse the opencode configuration cleanly across repositories without copying
project-specific details.

## Desired Behavior

Spec-driven development with opencode should have a clear boundary:

- Reusable opencode mechanics live under `opencode-config/`.
- Repo-specific workflow state and project facts live under `specrepo/`.
- opencode agents read the repo-specific facts from `specrepo/spec.yaml`,
  `specrepo/workflow.md`, templates, requests, proposals, approvals, and
  implementation reviews instead of hardcoding project details.
- The workflow documentation explains which role owns each stage and which
  directory is authoritative for that stage.

## Acceptance Criteria

- The architecture proposal identifies reusable responsibilities that belong in
  `opencode-config/`.
- The architecture proposal identifies repository-specific responsibilities
  that belong in `specrepo/`.
- The architecture proposal maps each spec-driven development role to its
  inputs, outputs, authority, and handoff boundaries.
- The architecture proposal identifies current repo-specific assumptions in
  `opencode-config/` that should be removed, parameterized, or moved during
  implementation.
- The architecture proposal identifies documentation/config files expected to
  change and a verification plan for the separation.

## Constraints

- Do not implement the separation until the architecture proposal is approved.
- Preserve the existing SpecRepo gates: request, proposal, human approval,
  implementation review, implementation, verification, and close.
- Preserve human ownership of final architecture approval and merge decisions.
- Keep opencode agent profiles conservative and reusable across repositories.

## Non-Goals

- Do not change LangChain AutoCommit runtime behavior.
- Do not change public Python APIs, CLI flags, LLM provider behavior, or Git
  commit behavior.
- Do not introduce a new workflow engine outside opencode and SpecRepo.
- Do not remove SpecRepo approval gates.

## Impacted Areas

- Public API: no
- CLI: no
- Config: yes
- LLM prompt/provider: no
- Git behavior: no
- Tests/docs: yes

## Notes

Requested boundary:

- Everything under `opencode-config/` should be reusable across repositories.
- Everything under `specrepo/` should be repository-specific.
