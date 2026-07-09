# Architecture Proposal: Remove LangChain allowed_objects warning suppression

Status: awaiting_approval
Date: 2026-07-09
Request: `specrepo/requests/2026-07-09-langchain-core-allowed-objects-warning.md`

## Summary

Replace the local `LangChainPendingDeprecationWarning` suppression in
`autocommit/chains/commit_chain.py` with explicit dependency constraints that
avoid the known incompatible warning-emitting combination:

- LangGraph 0.x / `langgraph-checkpoint` 3.x
- `langchain-core >=0.3.85`

The proposed implementation caps `langchain-core` below `0.3.85` while keeping
the existing LangChain 0.3 and LangGraph 0.x architecture. This removes the
warning at the source for this dependency line and avoids a major LangChain or
LangGraph migration.

## Current Architecture

The approved commit-message pipeline uses LangGraph in
`autocommit/chains/commit_chain.py` and is documented in
`specrepo/approved/2026-07-09-langgraph-commit-pipeline/approval.md`.

Current dependency constraints:

- `langchain-core>=0.3.17,<0.4.0`
- `langchain-community>=0.3.7,<0.4.0`
- `langchain>=0.3.7,<0.4.0`
- `langchain-text-splitters>=0.3.0,<0.4.0`
- `langchain-ollama>=0.3.10,<0.4.0`
- `langchain-openai>=0.3.0,<0.4.0`
- `langgraph>=0.3.0,<1.0.0`

In the local environment, pip resolved:

- `langgraph 0.6.11`
- `langgraph-checkpoint 3.0.1`
- `langchain-core 0.3.86`
- `langchain 0.3.30`

Importing `langgraph.graph` pulls in `langgraph.cache.base`, which imports
`langgraph.checkpoint.serde.jsonplus`. In `langgraph-checkpoint 3.0.1`,
`jsonplus.py` constructs `LC_REVIVER = Reviver()` without an explicit
`allowed_objects` value. In `langchain-core 0.3.85+`, that default emits a
`LangChainPendingDeprecationWarning`.

`commit_chain.py` currently suppresses the warning with:

```python
from langchain_core._api.deprecation import LangChainPendingDeprecationWarning
...
warnings.simplefilter("ignore", LangChainPendingDeprecationWarning)
```

That suppression is local to this module but broad for the warning category.

## Proposed Architecture

### Dependency compatibility policy

Keep the approved LangChain 0.3 / LangGraph 0.x dependency family and add an
upper bound to `langchain-core`:

```text
langchain-core>=0.3.17,<0.3.85
```

The bound avoids `langchain-core` releases that warn when a dependency creates
`Reviver()` without passing `allowed_objects`. A dry-run resolver check on
2026-07-09 confirmed this constraint is satisfiable with the current dependency
family; pip would select `langchain-core 0.3.84` and `langchain 0.3.28`.

### Source cleanup

Remove the warning suppression from `autocommit/chains/commit_chain.py`.

No graph state, node behavior, prompt, parser, public API, CLI, Git behavior,
or runtime config behavior changes.

### Rejected alternatives

- **Keep the warning filter:** This preserves the symptom workaround the
  request explicitly wants removed and can hide unrelated pending deprecations.
- **Patch or monkeypatch LangGraph internals:** This is brittle and would couple
  application code to dependency implementation details.
- **Upgrade to LangGraph 1.x / LangChain 1.x:** This may be the longer-term
  direction, but it is a major dependency-family migration outside the narrow
  scope of removing this warning.

## Scope

In scope:

- Tighten `langchain-core` dependency constraints in package metadata.
- Mirror the dependency constraint in `requirements.txt`.
- Remove the warning suppression import, comments, and filter from
  `autocommit/chains/commit_chain.py`.
- Add a focused import-warning regression test.

Out of scope:

- Migrating to LangGraph 1.x or LangChain 1.x.
- Changing commit-message graph topology or prompts.
- Changing provider selection or fallback behavior.
- Adding configuration keys.
- Changing public API or CLI behavior.

## API, CLI, And Config Changes

- Public API: none
- CLI: none
- Config: none
- Prompt/provider behavior: none

## Files Expected To Change

- `pyproject.toml`: change `langchain-core` upper bound to `<0.3.85`.
- `requirements.txt`: change `langchain-core` upper bound to `<0.3.85`.
- `autocommit/chains/commit_chain.py`: remove warning suppression code.
- `tests/test_commit_chain.py`: add an import-warning regression test, or add a
  dedicated test module if isolation is clearer.

## Test Plan

- `pytest tests/test_commit_chain.py`: verifies the graph tests and the new
  import-warning regression.
- `pytest`: default repository verification.
- Manual dependency check:
  `python -m pip install --dry-run 'langchain-core>=0.3.17,<0.3.85' ...`
  confirms the dependency set resolves.

The import-warning regression should run the import in a subprocess or otherwise
isolate module import state, surface `LangChainPendingDeprecationWarning`, and
assert that importing `autocommit.chains.commit_chain` does not emit the
`allowed_objects` warning.

## Risks And Mitigations

- Risk: Capping `langchain-core` may downgrade transitive LangChain packages in
  fresh installs.
  Mitigation: Keep all packages within the existing 0.3 family and verify with
  `pytest`; the dry-run resolver selected compatible 0.3 releases.

- Risk: A future dependency requires `langchain-core >=0.3.85`.
  Mitigation: Treat that as a separate dependency-family upgrade proposal,
  likely involving LangGraph 1.x / LangChain 1.x compatibility review.

- Risk: The warning could reappear from another dependency path.
  Mitigation: Add the import-warning regression so recurrence is visible during
  tests rather than hidden by a warning filter.

## Baseline Spec Updates

- Product spec: unchanged
- Architecture spec: unchanged
- Quality spec: unchanged

The baseline architecture already records the LangGraph pipeline shape. This
proposal changes dependency constraints and removes a workaround without
changing approved product behavior, module responsibilities, or quality gates.

## SpecRepo Gate Notes

- `@spec-reviewer`: unavailable as a callable specialized agent in this
  session; this proposal was prepared manually following the spec-review path.
- `@architecture-approver`: unavailable as a callable specialized agent in this
  session; readiness was checked manually against the architecture proposal
  template and workflow requirements.

Manual architecture readiness check:

- The request file exists and captures problem, desired behavior, acceptance
  criteria, constraints, non-goals, impacted areas, and observed versions.
- Current specs and relevant source/dependency context were read.
- Proposal scope is narrow and maps to concrete files.
- Test plan includes both default verification and a targeted regression.
- Implementation is blocked until a human creates or authorizes an approval
  record under `specrepo/approved/`.

## Approval Request

Approve this proposal before implementation begins.
