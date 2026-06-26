# SpecRepo

This directory is the repository-specific source of truth for spec-driven
development in this repository. Feature work starts here, architecture changes
are approved here, and implementation agents use the approved records before
editing code.

Reusable opencode agent profiles, permissions, and general workflow guidance
live in `$HOME/.config/opencode`. This `specrepo/` directory owns the local
project facts and decision records those reusable agents must read before
acting.

## Current Project

- Product: LangChain AutoCommit
- Package: `autocommit`
- Primary runtime: Python 3.10+
- Test runner: `pytest`
- Current baseline architecture: `specrepo/specs/architecture.md`
- Workflow rules: `specrepo/workflow.md`

## Directory Map

| Path | Purpose |
| --- | --- |
| `spec.yaml` | Machine-readable project and workflow manifest. |
| `workflow.md` | Required state machine and agent handoff rules. |
| `specs/` | Approved baseline specs for the current project. |
| `requests/` | Incoming feature requests. Add one file per request. |
| `proposals/` | Draft architecture proposals created from requests. |
| `approved/` | Human-approved architecture records for implementation. |
| `implementation-reviews/` | Coding-agent reviews of approved architecture before code edits. |
| `templates/` | Copyable templates for each workflow artifact. |

## Quick Start For A Feature Request

1. Copy `templates/feature-request.md` into `requests/YYYY-MM-DD-short-name.md`.
2. Fill in the request, constraints, acceptance criteria, and user impact.
3. Ask a spec reviewer agent to process the request.
4. The spec reviewer updates `specs/` and creates a proposal in `proposals/`.
5. A human approves by creating an approval record in `approved/`.
6. A coding agent reads the approved record, writes an implementation review in
   `implementation-reviews/`, then implements the change.

No implementation work should begin until the relevant approved architecture
record exists.
