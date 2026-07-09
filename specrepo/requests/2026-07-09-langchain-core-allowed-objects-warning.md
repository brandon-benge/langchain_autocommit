# Feature Request: Remove LangChain allowed_objects warning suppression

Status: requested
Date: 2026-07-09
Requester: Brandon Benge

## Summary

Remove the warning suppression currently required around the LangGraph import in
`autocommit/chains/commit_chain.py`.

Importing the commit chain currently triggers a
`LangChainPendingDeprecationWarning` from LangChain Core through LangGraph's
checkpoint/cache serializer import path:

```text
LangChainPendingDeprecationWarning: The default value of `allowed_objects` will
change in a future version. Pass an explicit value (e.g.,
allowed_objects='messages' or allowed_objects='core') to suppress this warning.
```

## Problem

The application code does not directly construct the warning-emitting
`Reviver`; the warning is emitted by dependency import side effects. The current
local workaround suppresses `LangChainPendingDeprecationWarning` in
`commit_chain.py`, which hides a dependency compatibility issue and makes the
module import behavior less transparent.

## Desired Behavior

Users and tests should be able to import `autocommit.chains.commit_chain`
without a LangChain pending deprecation warning and without an application-level
warning ignore filter in that module.

## Acceptance Criteria

- `autocommit/chains/commit_chain.py` no longer imports
  `LangChainPendingDeprecationWarning` only to suppress it.
- Importing `autocommit.chains.commit_chain` with LangChain pending
  deprecation warnings surfaced does not emit the `allowed_objects` warning.
- The approved LangGraph commit-message pipeline behavior remains unchanged.
- Dependency constraints continue to support Python 3.10+.
- The default verification command, `pytest`, passes or any exception is
  recorded.

## Constraints

- Do not change public API exports, CLI behavior, Git behavior, prompt behavior,
  or runtime config.
- Keep the existing approved LangGraph 0.x pipeline architecture unless a
  separate proposal approves a major LangGraph/LangChain migration.
- Avoid broad warning filters that could hide unrelated dependency or
  application warnings.
- Tests must remain deterministic and local.

## Non-Goals

- Migrating to LangGraph 1.x or LangChain 1.x.
- Changing graph topology, prompt templates, quality checks, or fallback LLM
  behavior.
- Adding new configuration keys.

## Impacted Areas

- Public API: no
- CLI: no
- Config: no
- LLM prompt/provider: no
- Git behavior: no
- Tests/docs: yes

## Notes

Observed installed versions in the local environment:

- `langgraph 0.6.11`
- `langgraph-checkpoint 3.0.1`
- `langchain-core 0.3.86`
- `langchain 0.3.30`

The warning is introduced by `langchain-core 0.3.85+` when
`langchain_core.load.load.Reviver()` is constructed without an explicit
`allowed_objects` value. LangGraph 0.6.11 imports
`langgraph.checkpoint.serde.jsonplus`, which constructs `LC_REVIVER =
Reviver()` at import time.
