# Spec-Driven Workflow

This workflow keeps requested behavior, approved architecture, and code changes
separate. Agents must follow the gates below.

## Directory Authority

This file is the repository-specific state machine for SpecRepo work in this
repository. Reusable opencode agents may execute the roles, but they must read
`specrepo/spec.yaml`, this workflow, the baseline specs, and the active
request/proposal/approval/review records before acting.

Reusable opencode mechanics belong in `$HOME/.config/opencode`.
Repository-specific project facts, gates, decisions, templates, and
verification commands belong in `specrepo/`.

## State Machine

| State | Directory | Owner | Exit Criteria |
| --- | --- | --- | --- |
| `requested` | `requests/` | Request author | Feature request is clear enough to review. |
| `architecture_proposed` | `proposals/` | Spec reviewer | Proposal explains product, architecture, tests, and risks. |
| `awaiting_approval` | `proposals/` | Human approver | Human accepts, rejects, or asks for revision. |
| `approved` | `approved/` | Human approver | Approval record points to the accepted proposal. |
| `implementation_reviewed` | `implementation-reviews/` | Coding agent | Coding agent confirms the approved architecture is implementable. |
| `implementing` | source tree | Coding agent | Code and tests are updated within approved scope. |
| `verified` | source tree | Coding agent | Test results or verification exceptions are recorded. |
| `closed` | `approved/` | Human or coding agent | Final status and changed files are recorded. |

## Request Intake

Feature requests belong in `specrepo/requests/` and should use
`specrepo/templates/feature-request.md`.

The request must include:

- Problem or opportunity.
- Desired user-visible behavior.
- Acceptance criteria.
- Constraints or non-goals.
- Any known compatibility concerns.

## Architecture Proposal

The spec reviewer processes one request at a time.

Required actions:

1. Read `specrepo/spec.yaml`, `specrepo/specs/product.md`,
   `specrepo/specs/architecture.md`, and `specrepo/specs/quality.md`.
2. Read the relevant source files and tests.
3. Create `specrepo/proposals/YYYY-MM-DD-short-name/architecture.md` from
   `specrepo/templates/architecture-proposal.md`.
4. Update baseline specs only when the proposal changes approved project
   architecture, product behavior, quality gates, or terminology.
5. Stop and ask for human approval. Do not implement code.

The proposal must state whether baseline specs were changed.

## Approval

Human approval is recorded by creating an approval file from
`specrepo/templates/approval-record.md` under
`specrepo/approved/YYYY-MM-DD-short-name/approval.md`.

The approval record must include:

- Link to request.
- Link to approved proposal.
- Approval decision.
- Approved scope.
- Any conditions or required follow-up.

Implementation may not begin without this record.

## Coding-Agent Architecture Review

Before editing code, the coding agent must create an implementation review from
`specrepo/templates/implementation-review.md` under
`specrepo/implementation-reviews/YYYY-MM-DD-short-name.md`.

The review must confirm:

- Approved architecture is internally consistent.
- Approved scope maps to concrete files or modules.
- Public API, CLI, config, and tests impacted by the change are identified.
- Any unresolved issue is marked as a blocker.

If the implementation review finds that the approved architecture is incomplete
or unsafe, the coding agent stops and asks for a revised proposal instead of
changing code.

## Implementation

Implementation agents may edit code only inside the approved scope.

If implementation reveals that architecture must change materially, stop and
return to the proposal step. Do not silently expand the design.

## Verification

The default verification command is:

```bash
pytest
```

If tests cannot be run, record the reason in the implementation review or final
implementation notes.
