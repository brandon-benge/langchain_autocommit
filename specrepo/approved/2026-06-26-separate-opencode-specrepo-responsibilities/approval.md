# Approval Record: Separate opencode and SpecRepo responsibilities

Status: approved
Date: 2026-06-26
Approver: user
Request: `specrepo/requests/2026-06-26-separate-opencode-specrepo-responsibilities.md`
Approved Proposal: `specrepo/proposals/2026-06-26-separate-opencode-specrepo-responsibilities/architecture.md`

## Decision

Approved

## Approved Scope

- Clarify `opencode-config/` as reusable opencode configuration, agent profiles, permissions, and workflow guidance across repositories.
- Clarify `specrepo/` as the repo-specific source of truth for project facts, workflow gates, specs, requests, proposals, approvals, implementation reviews, templates, and verification commands.
- Remove, parameterize, or move repo-specific assumptions currently present in `opencode-config/`.
- Update documentation and opencode config files listed in the approved proposal.
- Keep implementation limited to workflow documentation/config separation.

## Conditions

- Do not change LangChain AutoCommit runtime behavior.
- Do not change public Python APIs, CLI flags, LLM provider behavior, prompt behavior, Git behavior, or runtime config.
- Do not edit `autocommit/` or `tests/` unless a later approved proposal explicitly allows it.
- Create the required implementation review before implementation begins.
- Run the verification scans listed in the approved proposal, or record why they could not be run.

## Notes

This approval authorizes implementation of the proposal only within the documented scope. Human approval and merge decisions remain separate gates.