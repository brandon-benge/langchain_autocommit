# Implementation Review: LangGraph commit-message pipeline

Status: implementation_reviewed
Date: 2026-07-09
Reviewer: request-author (acting as implementation-reviewer; specialized agent unavailable)
Approval Record: `specrepo/approved/2026-07-09-langgraph-commit-pipeline/approval.md`

## Approved Architecture Readback

Replace the single linear `RunnableSequence` in `commit_chain.py` with a
LangGraph `StateGraph`. The graph has three nodes:

1. **`analyze_diff`** — fans out to parallel sub-nodes `analyze_type` and
   `analyze_scope`. Each receives the full (truncated) diff with a focused
   prompt. Results are gathered into `state.diff_analysis`.
2. **`write_message`** — consumes the structured analysis plus the raw diff and
   produces a draft `CommitMessage`-shaped dict.
3. **`check_quality`** — rule-based (no LLM). Checks subject length, format,
   boilerplate, body substance. Routes back to `write_message` with a critique
   if checks fail and the retry budget (`max_retries`, default 2) is not
   exhausted. Routes to output otherwise.

LLM fallback (primary → Ollama) moves inside each agent node. Public API and
Git behavior unchanged. CLI gains three new quality override flags.
New optional config keys under `git.quality.*`.
New dependency: `langgraph>=0.3.0`.

## Consistency Check

- Product behavior is clear: yes
- Architecture boundaries are clear: yes
- Public API impact is clear: not applicable (unchanged)
- CLI impact is clear: yes
- Config impact is clear: yes
- Test plan is clear: yes

## Implementation Map

| File | Planned change |
|------|----------------|
| `autocommit/chains/commit_chain.py` | Replace `build_chain(llm)` with `build_graph(llm, fallback_llm, config)`. Add `GraphState` TypedDict. Add three agent prompts (diff analyzer type, diff analyzer scope, message writer). Add `_check_quality(state)` function with rule-based checks. Build `StateGraph` with parallel fan-out (via `Send` or parallel node edges), conditional quality-loop routing, and fallback handling. Export `build_graph`. |
| `autocommit/core.py` | Change import from `build_chain` to `build_graph`. Replace `chain = build_chain(llm_model)` with `graph = build_graph(llm_model, fallback_llm, cfg)`. Build `GraphState` dict and call `result = graph.invoke(state)`. Remove the outer try/except retry wrapper (lines 145-156). Keep subject truncation and committer appending unchanged. |
| `autocommit/cli.py` | Add `--quality-max-retries`, `--min-body-lines`, `--check-boilerplate` / `--no-check-boilerplate` flags. Add `_build_quality_overrides(args)` returning `{"git": {"quality": {...}}}`. Merge quality overrides with LLM overrides before `load_config`. |
| `autocommit/params.yaml` | Add `git.quality` block: `max_retries: 2`, `min_body_lines: 3`, `check_boilerplate: true`. |
| `pyproject.toml` | Add `langgraph>=0.3.0` to `[project.dependencies]`. |
| `requirements.txt` | Add `langgraph>=0.3.0`. |
| `tests/test_commit_chain.py` | Full rewrite: `TestBuildGraph` (returns CompiledStateGraph), `TestGraphTopology` (nodes and edges exist), `TestQualityLoopRouting` (pass → output, fail → retry, exhausted → output), `TestParallelAnalysis` (both sub-nodes run), `TestGraphFallback` (deterministic fallback when LLMs fail), `TestStateSchema` (initialization, retry increment). |
| `tests/test_core.py` | Update `TestGenerateCommitMessageLlmFallback` and `TestGenerateCommitMessageSubjectTruncation` to mock `build_graph` instead of `build_chain`. Add test verifying `graph.invoke` called with correct initial state. Add test verifying deterministic fallback reachable when graph returns empty. |
| `tests/test_autocommit.py` | Add `TestBuildQualityOverrides` for the new helper function. Add tests verifying `--quality-max-retries`, `--min-body-lines`, `--check-boilerplate` / `--no-check-boilerplate` produce correct config overrides. |
| `specrepo/specs/architecture.md` | Update module responsibilities table (commit_chain.py row). Update commit-message generation flow (steps 7-9). Add `GraphState` and graph topology description. |
| `specrepo/specs/quality.md` | Add `tests/test_commit_chain.py` to required coverage areas. Add note that graph topology and conditional routing must be tested with mocked LLMs. |

## Questions Or Blockers

None. The approved architecture is internally consistent, the scope maps to
concrete files, and the test plan is detailed.

One implementation note (not a blocker): `build_graph` must accept `config` as
a parameter so it can read `git.quality.*` and `git.conventional` for the
quality checker's rule logic and for determining whether to enforce
conventional-commit format.

## Verification Plan

```bash
pytest
```

Existing tests must pass with the mocked graph. New tests must cover:
graph topology, routing branches, parallel execution, state mutations,
fallback behavior, and CLI quality flag parsing. No real network calls.

## Review Decision

Proceed
