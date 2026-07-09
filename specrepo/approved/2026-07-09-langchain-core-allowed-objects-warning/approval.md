# Approval Record: Remove LangChain allowed_objects warning suppression

Status: approved
Date: 2026-07-09
Approver: brandonbenge
Request: `specrepo/requests/2026-07-09-langchain-core-allowed-objects-warning.md`
Approved Proposal: `specrepo/proposals/2026-07-09-langchain-core-allowed-objects-warning/architecture.md`

## Decision

Approved

## Approved Scope

- Tighten the `langchain-core` dependency constraint to
  `langchain-core>=0.3.17,<0.3.85` in package metadata.
- Mirror the same `langchain-core` constraint in `requirements.txt`.
- Remove the `LangChainPendingDeprecationWarning` suppression code from
  `autocommit/chains/commit_chain.py`.
- Add a focused regression test proving the commit chain import does not emit
  the `allowed_objects` pending deprecation warning when warnings are surfaced.

## Conditions

- Do not change public API, CLI behavior, runtime config, Git behavior, prompt
  behavior, graph topology, or fallback LLM behavior.
- Keep the existing approved LangChain 0.3 / LangGraph 0.x architecture.
- Run `pytest` or record why it could not be run.

## Notes

This approval intentionally chooses the narrow dependency-bound fix over a
major LangGraph or LangChain migration.
