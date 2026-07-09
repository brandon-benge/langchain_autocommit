# Implementation Review: Remove LangChain allowed_objects warning suppression

Status: implementation_reviewed
Date: 2026-07-09
Reviewer: codex
Approval Record: `specrepo/approved/2026-07-09-langchain-core-allowed-objects-warning/approval.md`

## Approved Architecture Readback

The approved change removes the local warning suppression in
`autocommit/chains/commit_chain.py` by avoiding the dependency combination that
emits the warning at import time. The implementation must cap
`langchain-core` below `0.3.85` in both dependency files, remove the
`LangChainPendingDeprecationWarning` filter from the commit chain module, and
add a deterministic import-warning regression test. Public API, CLI behavior,
runtime config, Git behavior, prompt behavior, graph topology, and fallback LLM
behavior must remain unchanged.

## Consistency Check

- Product behavior is clear: yes
- Architecture boundaries are clear: yes
- Public API impact is clear: not applicable
- CLI impact is clear: not applicable
- Config impact is clear: not applicable
- Test plan is clear: yes

## Implementation Map

- `pyproject.toml`: change the `langchain-core` dependency upper bound from
  `<0.4.0` to `<0.3.85`.
- `requirements.txt`: mirror the same `langchain-core` upper bound.
- `autocommit/chains/commit_chain.py`: remove the warning-specific import,
  comments, and `warnings.simplefilter` call.
- `tests/test_commit_chain.py`: add a subprocess-based import-warning
  regression test.

## Questions Or Blockers

- None.

## Verification Plan

- `python -m pip install -e .[test]` if the local environment still has
  `langchain-core>=0.3.85`.
- `pytest tests/test_commit_chain.py`
- `pytest`

## Verification Evidence

- `python -m pip install -e .[test]`: passed; local environment now resolves
  `langchain-core 0.3.84`, `langchain 0.3.28`, `langgraph 0.6.11`, and
  `langgraph-checkpoint 3.0.1`.
- `pytest tests/test_commit_chain.py`: passed, 16 tests.
- `pytest`: passed, 122 tests.

## Test Review

Coverage is appropriate for the approved scope. The new regression test imports
`autocommit.chains.commit_chain` in a subprocess with
`LangChainPendingDeprecationWarning` surfaced and fails specifically if an
`allowed_objects` warning is emitted. Existing graph tests continue to verify
that the LangGraph pipeline compiles and invokes as expected.

Residual risk: the fix intentionally relies on a dependency upper bound rather
than a LangGraph/LangChain major-version migration. A future dependency update
that requires `langchain-core>=0.3.85` should return to the proposal workflow.

## Review Decision

Proceed

## SpecRepo Gate Notes

- `@implementation-reviewer`: unavailable as a callable specialized agent in
  this session; this implementation review was prepared manually following the
  implementation-review gate.
- `@spec-coder`: unavailable as a callable specialized agent in this session;
  implementation was performed manually within the approved scope.
- `@test-reviewer`: unavailable as a callable specialized agent in this
  session; test coverage and residual risk were reviewed manually above.
