# Approval Record: LangGraph commit-message pipeline

Status: approved
Date: 2026-07-09
Approver: brandonbenge
Request: `specrepo/requests/2026-07-09-langgraph-commit-pipeline.md`
Approved Proposal: `specrepo/proposals/2026-07-09-langgraph-commit-pipeline/architecture.md`

## Decision

Approved

## Approved Scope

- Replace `build_chain` with `build_graph` in `autocommit/chains/commit_chain.py`.
- Three-node LangGraph `StateGraph`: `analyze_diff` (with parallel type/scope
  sub-nodes), `write_message`, `check_quality` (rule-based).
- Quality loop with configurable retry budget (default 2), no human-in-the-loop.
- Parallel diff analysis sub-nodes each receive the full truncated diff (no
  chunking).
- LLM fallback (primary → Ollama) moved inside graph nodes.
- New optional config keys under `git.quality.*` and corresponding CLI flags
  (`--quality-max-retries`, `--min-body-lines`, `--check-boilerplate` /
  `--no-check-boilerplate`).
- Add `langgraph>=0.3.0` dependency.
- Update tests and baseline specs (`architecture.md`, `quality.md`).
- Public API and Git behavior unchanged. CLI gains three new flags; all
  existing flags work identically.

## Conditions

- The deterministic fallback (`_build_fallback_body`) must remain reachable.
- All existing tests must continue to pass.
- No human-in-the-loop.

## Notes

The user explicitly confirmed the diff is NOT chunked for parallel sub-nodes;
each sub-node receives the full (truncated) diff with a different analytical
prompt.
