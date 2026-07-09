# Architecture Proposal: LangGraph commit-message pipeline

Status: awaiting_approval
Date: 2026-07-09
Request: `specrepo/requests/2026-07-09-langgraph-commit-pipeline.md`

## Summary

Replace the single linear LangChain `RunnableSequence` in
`autocommit/chains/commit_chain.py` with a LangGraph `StateGraph` of three
specialized agents (diff analyzer, message writer, quality checker). The graph
adds parallel diff content analysis, automatic quality-loop retries, and
structured graph state, while keeping the public API, CLI, and Git behavior
identical from the caller's perspective.

## Current Architecture

The commit-message generation pipeline (lines 128-151 of `core.py`) currently:

1. Fetches the staged diff and infers type/scope/ticket from file paths and
   branch name using heuristic rules in `git_utils.py`.
2. Builds a single `RunnableSequence` in `build_chain(llm)`:
   ```
   RunnableMap → DEFAULT_PROMPT → llm → JsonOutputParser
   ```
3. Calls `chain.invoke(inputs)` once. On failure, retries once with a fallback
   Ollama LLM (same pipeline, same prompt).
4. Falls back to a deterministic body (`_build_fallback_body`) if both attempts
   fail or return unparseable output.
5. Truncates the subject and appends committer metadata.

Key characteristics of the current design:

- **Single-shot generation**: no feedback loop or iterative improvement.
- **Flat prompt context**: the entire diff patch is injected as a single
  `diff_summary` string; no structured content analysis is performed.
- **One LLM, many responsibilities**: the same call must infer commit type from
  content, identify scope, write a subject, and craft a multi-line body.
- **Heuristic-only pre-analysis**: type, scope, and ticket are inferred from
  paths/branch before the LLM runs and are injected as prompt variables, but
  the LLM never cross-checks or enriches them.
- **Module boundary**: `commit_chain.py` owns the prompt template and chain
  construction. `core.py` orchestrates config, git, fallback, and post-
  processing.

## Proposed Architecture

### New dependency

Add `langgraph>=0.3.0` to `pyproject.toml` and `requirements.txt`.

### Module changes

**`autocommit/chains/commit_chain.py`** is the primary target. It will be
restructured to export a `build_graph(llm, fallback_llm, config)` function
instead of `build_chain(llm)`. The graph is a `StateGraph` with typed state.

**`autocommit/core.py`** gets a focused update: the `chain.invoke(inputs)` call
becomes `graph.invoke(state)`. The fallback retry logic (try primary → catch →
try fallback) shifts into the graph itself because the graph can attempt each
LLM provider internally. The outer retry-on-exception wrapper in `core.py` is
removed and replaced by the graph's internal routing.

### Graph design

```
                           ┌──────────────────────────────────────────────┐
                           │              GRAPH STATE                     │
                           │  raw_diff, changed_files, user_context,      │
                           │  diff_analysis (optional dict),              │
                           │  draft_message (optional CommitMessage),     │
                           │  critique_history (list[str]),               │
                           │  retry_count (int),                          │
                           │  errors (list[str])                          │
                           └──────────────────────────────────────────────┘
                                        │
                                        ▼
                           ┌─────────────────────────┐
                           │     analyze_diff         │
                           │  (parallel sub-nodes)    │
                           │  ┌──────┐ ┌──────┐      │
                           │  │type  │ │scope │      │
                           │  │analy-│ │analy-│      │
                           │  │zer   │ │zer   │      │
                           │  └──────┘ └──────┘      │
                           └─────────┬───────────────┘
                                     │ state.diff_analysis populated
                                     ▼
                           ┌─────────────────────────┐
                           │      write_message       │
                           │  (prompt includes both   │
                           │   raw diff + structured  │
                           │   diff_analysis +        │
                           │   optional critique)     │
                           └─────────┬───────────────┘
                                     │ state.draft_message populated
                                     ▼
                           ┌─────────────────────────┐
                           │     check_quality        │
                           │  (rule-based checks)     │
                           └─────────┬───────────────┘
                                     │
                  ┌──────────────────┼──────────────────┐
                  │ passes           │ fails, retries    │ fails, no retries
                  ▼                  │ remaining         ▼
            ┌──────────┐            ▼             ┌──────────┐
            │  output   │   ┌──────────────┐      │  output   │
            │ (success) │   │ write_message │      │ (fallback │
            └──────────┘   │ (with critique │      │  or last  │
                           │  in state)     │      │  draft)   │
                           └──────────────┘      └──────────┘
```

#### Node details

**1. `analyze_diff` node**

A compound node that fans out to parallel analysis sub-nodes. Each sub-node
receives the raw diff and changed file list, and returns a structured analysis
fragment. The fan-in merges their outputs into `state.diff_analysis`.

Parallel sub-nodes (at least two, as required by the request):

| Sub-node | Input | Output |
|----------|-------|--------|
| `analyze_type` | Raw diff, changed files | Content-based conventional-commit type (string) with confidence |
| `analyze_scope` | Raw diff, changed files | Scope candidates (string) with rationale |

Additional sub-nodes may be added by the implementation (e.g., `analyze_risk`,
`extract_ticket_from_diff`).

**Implementation note:** LangGraph supports fan-out via `Send` (dynamic
parallelism) or by defining each sub-node as a regular node with edges to a
`gather` node that waits for all. The exact mechanism is an implementation
detail, not an architectural constraint.

**2. `write_message` node**

Consumes `state.diff_analysis` (from the analyzer), `state.raw_diff`,
`state.changed_files`, `state.user_context`, and optionally
`state.critique_history[-1]` (when retrying). Produces a draft commit message
as a `CommitMessage`-shaped dict (`{"subject": str, "body": str}`).

The prompt for this agent is narrower than today's `DEFAULT_PROMPT`: it
focuses on writing the message given structured analysis, rather than asking
the LLM to simultaneously analyze and write.

**3. `check_quality` node**

Runs deterministic (rule-based) checks on the draft:

- Subject line ≤ `max_subject_length`
- Subject matches `<type>(<scope>): <subject>` format (when conventional mode
  is on)
- Subject is not empty
- Body is not empty (or not trivially short)
- No boilerplate detected (e.g., "Update file", "Fix bug" with no detail)
- Body exceeds a minimum line count (configurable, default 3)

If all checks pass: route to output.

If checks fail and `state.retry_count < max_retries`: increment
`state.retry_count`, append critique to `state.critique_history`, route back
to `write_message`.

If checks fail and `state.retry_count >= max_retries`: route to output with
the best-effort draft (or fallback).

**Quality checks are deterministic.** They do not call an LLM. This keeps the
loop fast, testable, and predictable.

#### Graph output

The graph returns a dict matching today's `CommitMessage` shape:
```python
{"subject": str, "body": str}
```

If the graph encounters unrecoverable errors (all LLM calls fail, the fallback
LLM also fails), the output node returns the deterministic fallback from
`_build_fallback_body`.

### State schema

Defined in `commit_chain.py` (TypedDict or Pydantic BaseModel):

```python
class GraphState(TypedDict):
    # Immutable inputs
    raw_diff: str
    changed_files: list[str]
    user_context: str
    max_subject_length: int
    max_diff_chars: int
    max_changed_files: int
    diff_truncated: bool

    # Heuristic pre-analysis (carried forward from current behavior)
    heuristic_type: str
    heuristic_scope: str
    ticket: str
    conventional: bool

    # Populated by analyze_diff
    diff_analysis: NotRequired[dict]  # e.g. {"content_type": "...", "content_scope": "..."}

    # Populated by write_message
    draft_message: NotRequired[dict]  # {"subject": str, "body": str}

    # Quality loop state
    retry_count: int
    critique_history: list[str]
    errors: list[str]

    # LLM provider control (set before graph invocation)
    primary_llm: BaseChatModel
    fallback_llm: NotRequired[BaseChatModel | None]
```

### LLM provider fallback inside the graph

The graph is invoked with both `primary_llm` and `fallback_llm` pre-resolved
(by `resolve_llm` in `llm_provider.py`, same as today). Each agent node
(`analyze_diff`, `write_message`) attempts the `primary_llm` first. On
exception, the node retries with `fallback_llm`. If both fail, the node sets
an error in `state.errors` and the graph routes to the deterministic fallback
output.

This moves the LLM retry logic out of `core.py` and into the graph nodes,
simplifying `core.py`.

### Updated data flow in `core.py`

The current flow (lines 128-160) changes to:

```python
llm_model, provider_used = resolve_llm(llm_cfg)
fallback_llm = build_fallback_llm(llm_cfg)  # always build; graph uses only if primary fails

graph = build_graph(llm_model, fallback_llm, cfg)  # from commit_chain.py

initial_state = GraphState(
    raw_diff=diff,
    changed_files=files,
    user_context=context or "",
    max_subject_length=max_subject_length,
    max_diff_chars=max_diff_chars,
    max_changed_files=max_changed_files,
    diff_truncated=_diff_truncated,
    heuristic_type=type,
    heuristic_scope=scope,
    ticket=ticket,
    conventional=conventional,  # from git config
    primary_llm=llm_model,
    fallback_llm=fallback_llm,
    retry_count=0,
    critique_history=[],
    errors=[],
)

result = graph.invoke(initial_state)  # returns {"subject": ..., "body": ...}

if not result or not isinstance(result, dict):
    subject, body = _build_fallback_body(files, type, scope)
    return CommitMessage(subject=subject, body=body)

subject = (result.get("subject") or "").strip()
body = (result.get("body") or "").strip()
# ... same subject truncation and committer logic as today ...
```

### Config additions

New optional keys under `git:` in `params.yaml`:

```yaml
git:
  # ... existing keys unchanged ...
  quality:
    max_retries: 2            # max quality-loop retries (default 2)
    min_body_lines: 3         # minimum body lines to pass quality check
    check_boilerplate: true   # reject generic messages with no detail
```

All are optional and default to sensible values, so no existing config breaks.

### CLI additions

Three new CLI flags mirror these config keys, following the same argument
patterns as existing git overrides (`--max-subject-length`, `--conventional` /
`--no-conventional`):

| Flag | Config key | Type |
|------|-----------|------|
| `--quality-max-retries` | `git.quality.max_retries` | int |
| `--min-body-lines` | `git.quality.min_body_lines` | int |
| `--check-boilerplate` / `--no-check-boilerplate` | `git.quality.check_boilerplate` | bool |

These flags are translated into config overrides by a new helper function
`_build_quality_overrides(args)` in `cli.py`, parallel to the existing
`_build_llm_overrides(args)`. The resulting dict is deep-merged into the
config at `load_config` time, so the graph reads them identically whether
set via `params.yaml` or CLI.

## Scope

In scope:

- Replace `build_chain(llm)` with `build_graph(llm, fallback_llm, config)` in
  `autocommit/chains/commit_chain.py`.
- Define a `GraphState` TypedDict and the three-node `StateGraph` (analyze,
  write, check) with quality-loop routing.
- Add parallel diff analysis (at minimum `analyze_type` and `analyze_scope`
  from content, running concurrently).
- Move LLM retry logic (primary → fallback) inside the graph nodes, removing
  the try/except wrapper from `core.py`.
- Add new optional config keys under `git.quality.*` in `params.yaml`.
- Add CLI flags `--quality-max-retries`, `--min-body-lines`,
  `--check-boilerplate` / `--no-check-boilerplate` to override quality config
  at the command line.
- Add `langgraph` dependency.
- Update tests for graph topology, routing, state propagation, and fallback.

Out of scope:

- **No human-in-the-loop.** The graph runs to completion without interrupts.
- **No changes to `autocommit/utils/git_utils.py`** beyond what graph nodes
  consume (the heuristic functions remain unchanged and are passed to the graph
  as initial state).
- **No changes to `autocommit/utils/llm_provider.py`** beyond ensuring
  `build_fallback_llm` is exported (it already is).
- **No changes to `autocommit/utils/keychain.py`**.
- **No changes to `autocommit/config.py`** (config loading stays unchanged).
- **No toggle** to switch between graph and non-graph mode.

## API, CLI, And Config Changes

- **Public API**: unchanged. `generate_commit_message`, `apply_commit`,
  `generate_and_commit`, and `CommitMessage` keep their current signatures.
  `build_chain` (not part of the public API) is replaced by `build_graph`.
- **CLI**: existing flags work identically. Three new flags added:
  `--quality-max-retries` (int), `--min-body-lines` (int),
  `--check-boilerplate` / `--no-check-boilerplate` (bool). Translated to
  config overrides via `_build_quality_overrides(args)` in `cli.py`.
- **Config**: new optional keys under `git.quality.*` — `max_retries` (int,
  default 2), `min_body_lines` (int, default 3), `check_boilerplate` (bool,
  default true). Overridable via CLI.
- **Prompt/provider behavior**: the single `DEFAULT_PROMPT` is replaced by
  three agent-specific prompts (diff analyzer, message writer, quality
  checker). The quality checker is rule-based, not LLM-based. The graph
  orchestrates which LLM (primary or fallback) each agent uses.

## Files Expected To Change

| File | Change |
|------|--------|
| `autocommit/chains/commit_chain.py` | Replace `build_chain` with `build_graph`. Add `GraphState`, three-node graph, agent prompts, quality rules, parallel fan-out logic. |
| `autocommit/core.py` | Replace `chain.invoke` with `graph.invoke`. Remove outer retry try/except (moved into graph). Remove import of `build_chain`; import `build_graph` instead. |
| `autocommit/cli.py` | Add `--quality-max-retries`, `--min-body-lines`, `--check-boilerplate` / `--no-check-boilerplate` flags and `_build_quality_overrides(args)` helper. Merge quality overrides into `config_overrides`. |
| `autocommit/params.yaml` | Add `git.quality.*` config keys with defaults. |
| `pyproject.toml` | Add `langgraph>=0.3.0` dependency. |
| `requirements.txt` | Add `langgraph>=0.3.0`. |
| `tests/test_commit_chain.py` | Replace chain tests with graph tests (topology, routing, state propagation, quality loop, parallel nodes). |
| `tests/test_core.py` | Update LLM-fallback tests to reflect that retry logic lives in the graph, not in core. Verify graph invocation. |
| `specrepo/specs/architecture.md` | Update module responsibilities and flow description (see below). |
| `specrepo/specs/quality.md` | Add test coverage area for graph topology and parallel routing. |

## Test Plan

| Test file | New or modified tests |
|-----------|----------------------|
| `tests/test_commit_chain.py` | **`TestBuildGraph`**: `test_returns_compiled_state_graph` — verifies `build_graph` returns a `CompiledStateGraph`. **`TestGraphTopology`**: `test_has_analyze_node`, `test_has_write_node`, `test_has_quality_node`, `test_quality_loop_edge_exists`, `test_parallel_analyze_nodes` — verifies nodes and edges. **`TestQualityLoopRouting`**: `test_passes_goes_to_output`, `test_fails_routes_back_to_write`, `test_exhausted_retries_goes_to_output` — verifies correct routing by mocking the quality checker. **`TestParallelAnalysis`**: `test_analyze_type_and_scope_run_concurrently` — verifies both sub-nodes execute. **`TestGraphFallback`**: `test_all_agents_fail_returns_fallback_body` — verifies deterministic fallback when LLMs fail. **`TestStateSchema`**: `test_state_initialization`, `test_retry_count_increments`. |
| `tests/test_core.py` | Update `TestGenerateCommitMessageLlmFallback` to mock `build_graph` instead of `build_chain`. Add test verifying `graph.invoke` is called with the correct initial state. Add test verifying the deterministic fallback is still reachable when the graph returns empty/none. |
| `tests/test_autocommit.py` | Add `TestBuildQualityOverrides` for the new helper function. Add CLI integration tests verifying `--quality-max-retries`, `--min-body-lines`, `--check-boilerplate` / `--no-check-boilerplate` produce correct config overrides. |
| `tests/test_master.py` or new config test | Test that new `git.quality.*` keys load with defaults and accept overrides. |

Tests must remain deterministic and local. All LLM calls must be mocked.
Graph routing must be testable without real LangGraph runtime by verifying
conditional edge functions with known state values.

## Risks And Mitigations

| Risk | Mitigation |
|------|------------|
| **Increased latency from multi-agent calls** — Three LLM calls (analyze, write, verify) instead of one, plus possible retries. | Quality checker is deterministic (no LLM). Parallel analysis sub-nodes run concurrently, so their combined wall time is roughly one LLM call. Worst case: ~3 LLM calls (analyze + write + retry write). This is acceptable because the current system already does 1–2 calls. |
| **LangGraph API instability** — Early major version may have breaking changes. | Pin `langgraph>=0.3.0,<1.0` initially. The graph abstraction is isolated to `commit_chain.py`, so upgrades are scoped. |
| **Graph debugging complexity** — Stateful graphs are harder to debug than linear pipelines. | Add `state.errors` accumulation. Each node captures exceptions into state rather than raising. Add optional verbose logging in the graph for troubleshooting. |
| **Quality loop never converges** — Bad messages keep retrying without improvement. | Bounded retry budget (default 2). Exhaustion routes to output. The critique from `check_quality` is concrete and actionable, guiding the writer toward improvement. |
| **Regression in existing behavior** — Any change to the internal pipeline risks breaking the fallback or post-processing. | All existing tests in `test_core.py` for subject truncation, committer appending, fallback bodies, and early exits must still pass with the graph replacement. The core.py integration test pattern (mock the chain/graph) remains the same. |
| **New dependency weight** — `langgraph` adds install size. | `langgraph` is a lightweight orchestration library (no GPU deps, no models). Its transitive dependencies (mostly `langchain-core` already present) are minimal. |

## Baseline Spec Updates

- **Product spec**: unchanged. No new user-facing capabilities are added or
  removed. The public API surface is identical.
- **Architecture spec**: **changed**. The module responsibilities table and the
  commit-message generation flow (sections 4 and 5) must be updated to reflect
  the graph-based pipeline, the new agent roles, and the config keys.
- **Quality spec**: **changed**. Add `tests/test_commit_chain.py` to the
  required coverage areas list. Add note that graph topology and routing must
  be tested with mocked LLMs.

## Approval Request

Approve this proposal before implementation begins.
