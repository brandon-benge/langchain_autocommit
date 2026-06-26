# Agent Instructions

This repository uses the SpecRepo workflow in `specrepo/`.

## Default Rule

For feature work, behavior changes, public API changes, CLI changes, config
changes, provider changes, Git behavior changes, or test strategy changes, do
not start implementation until there is an approved architecture record under
`specrepo/approved/`.

## Spec Review Path

When asked to review a feature request or update architecture:

1. Read `specrepo/spec.yaml`, `specrepo/workflow.md`, and the baseline specs in
   `specrepo/specs/`.
2. Read the request from `specrepo/requests/`.
3. Create or update an architecture proposal under `specrepo/proposals/`.
4. Update baseline specs only if the proposed architecture changes the approved
   understanding of the project.
5. Stop and ask for human approval. Do not implement code.

## Implementation Path

When asked to implement an approved change:

1. Read the approval record under `specrepo/approved/`.
2. Read the approved proposal referenced by that approval record.
3. Read the current baseline specs in `specrepo/specs/`.
4. Create an implementation review under `specrepo/implementation-reviews/`.
5. Implement only within the approved scope.
6. Run the approved verification plan or record why it could not be run.

If the approved architecture is incomplete, inconsistent, or requires material
changes during implementation, stop and return to the proposal workflow.

## Current Project Shape

- Package root: `autocommit/`
- Tests: `tests/`
- Runtime config source of truth: `autocommit/params.yaml`
- Default verification: `pytest`
