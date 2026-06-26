# Implementation Review: Separate opencode and SpecRepo responsibilities

Status: implementation_reviewed
Date: 2026-06-26
Reviewer: Codex
Approval Record: `specrepo/approved/2026-06-26-separate-opencode-specrepo-responsibilities/approval.md`

## Approved Architecture Readback

The approved change separates reusable opencode workflow mechanics from
repository-specific SpecRepo state. `opencode-config/` should become a portable
opencode bundle for SpecRepo agents, permissions, and generic workflow
guidance. `specrepo/` should remain the repository-specific authority for
project facts, workflow gates, specs, requests, proposals, approvals,
implementation reviews, templates, and verification commands.

Implementation is limited to documentation and opencode configuration changes.
No LangChain AutoCommit runtime behavior, public API, CLI behavior, provider
behavior, prompt behavior, Git behavior, tests, or runtime config may change.

## Consistency Check

- Product behavior is clear: yes
- Architecture boundaries are clear: yes
- Public API impact is clear: not applicable
- CLI impact is clear: not applicable
- Config impact is clear: yes
- Test plan is clear: yes

## Implementation Map

- `opencode-config/README.md`: describe `opencode-config/` as reusable across
  repositories and direct agents to read repo-specific facts from SpecRepo.
- `opencode-config/feature-development.md`: make the guide repository-neutral,
  remove hardcoded test-command assumptions, and clarify role handoffs.
- `opencode-config/opencode.yaml`: keep only reusable permissions by default
  and remove Python-specific verification allowlists.
- `opencode-config/opencode.jsonc`: remove language-specific watcher ignores
  from the reusable default.
- `opencode-config/agents/spec-reviewer.md`: remove repository-specific
  implementation path restrictions and use SpecRepo manifest fields for source,
  test, command, and workflow facts.
- `opencode-config/agents/architecture-approver.md`: keep approval-review
  behavior generic and repository-neutral.
- `opencode-config/agents/implementation-reviewer.md`: keep pre-code review
  behavior generic and manifest-driven.
- `opencode-config/agents/spec-coder.md`: require the approved verification
  plan or `specrepo/spec.yaml.commands.test` instead of hardcoding `pytest`.
- `opencode-config/agents/test-reviewer.md`: require quality expectations from
  `specrepo/specs/quality.md` and approved artifacts instead of hardcoded
  Python test assumptions.
- `opencode-config/agents/specrepo-bootstrapper.md`: add the reusable agent
  responsible for creating a complete repo-specific SpecRepo structure when a
  target repository does not have one yet.
- `opencode-config/templates/specrepo/`: add reusable templates for the full
  generated SpecRepo structure.
- `specrepo/README.md`: state that `specrepo/` is repository-specific and that
  reusable opencode mechanics live in `opencode-config/`.
- `specrepo/workflow.md`: clarify that opencode agents are reusable executors
  while this file is the repo-specific state machine authority.
- `specrepo/agents/`: remove repo-local agent overlays. Reusable agent profiles
  live only under `opencode-config/agents/`.

## Questions Or Blockers

- None.

## Verification Plan

- `rg -n "LangChain|AutoCommit|autocommit|params.yaml|pytest|python3 -m py_compile|\\.venv/bin/pytest" opencode-config`
  should return no unintended repository-specific leakage.
- `rg -n "source_roots|test_roots|commands.test|specrepo/spec.yaml" opencode-config`
  should show that reusable agents point to the manifest for repository facts.
- `rg -n "reusable|repo-specific|opencode-config|specrepo" specrepo/README.md specrepo/workflow.md`
  should confirm the documented authority split.
- `git diff -- opencode-config specrepo` should show no changes under
  `autocommit/`, `tests/`, or runtime metadata.
- No `pytest` run is required because the approved change does not alter
  runtime code.

## Review Decision

Proceed
