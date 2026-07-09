# Feature Request: LangGraph commit-message pipeline

Status: requested
Date: 2026-07-09
Requester: brandonbenge

## Summary

Replace the current linear LangChain `RunnableSequence` in
`autocommit/chains/commit_chain.py` with a LangGraph `StateGraph` that
orchestrates multiple specialized agents (diff analyzer, message writer, quality
checker) with conditional quality-loop retries and parallel diff analysis. The
change targets the internal generation pipeline only; the public API, CLI, and
config surface remain unchanged from the caller's perspective.

## Problem

The current commit-message pipeline is a single linear `RunnableSequence`
(RunnableMap → Prompt → LLM → `JsonOutputParser`). This design has several
limitations:

1. **No quality feedback** — The LLM produces one shot. If the message is too
   long, too vague, or deviates from conventional-commit format, there is no
   mechanism to detect or correct it without a separate retry by the user.

2. **Flat diff context** — Every changed file is poured into a single prompt as
   raw patch text. The model receives no structured analysis of the diff (e.g.,
   which areas are most impactful, what patterns emerge across files, which
   conventional-commit type best fits the *content* rather than the paths).

3. **Single-model responsibility** — One LLM call must simultaneously understand
   the diff, infer type/scope, write a subject, and draft a multi-line body.
   Splitting these concerns across specialized agents (each with a focused
   prompt) should produce more accurate results.

4. **No analytic insights used downstream** — Path-based type/scope/ticket
   inference (current `infer_type_from_paths`, `infer_scope_from_cwd`,
   `find_ticket`) is computed before the LLM runs and injected as prompt
   variables, but the LLM output is never cross-checked against these heuristics
   or enriched with content-based analysis.

## Desired Behavior

After this change, the internal commit-message generation uses a LangGraph
`StateGraph` with the following high-level nodes (executed in a stateful graph
rather than a pipeline):

- **Diff analyzer agent** — Examines the staged diff and produces structured
  analysis: inferred conventional-commit type (from content, not just paths),
  scope candidates, key changes per file, risk indicators, and any cross-file
  patterns.
- **Message writer agent** — Consumes the diff analysis (plus path-based
  heuristics as a fallback) and produces a draft `CommitMessage`.
- **Quality checker agent** — Evaluates the draft against defined quality rules
  (subject length, conventional-commit format compliance, boilerplate detection,
  body substance). If quality is insufficient and the retry budget allows, the
  graph routes back to the message writer with a critique embedded in the graph
  state.

After all retry attempts are exhausted (or quality passes), the graph returns a
`CommitMessage(subject, body)` identical in shape to today's output.

The graph may also run diff analysis sub-nodes in parallel (e.g., type inference
from content, scope inference from content, ticket extraction from diff text).

The fallback path (deterministic body generation when no valid LLM output is
produced) must still be reachable.

## Acceptance Criteria

1. **Internal pipeline is a LangGraph state graph.** The graph replaces the
   current `RunnableSequence` in `commit_chain.py`. The graph state carries
   diff analysis, draft messages, critique history, and retry count.

2. **Quality loop retries are automatic.** The quality checker can route back to
   the message writer with a critique. The retry budget is bounded by a config
   key (default 2 retries). No human approval is required or offered.

3. **Parallel diff analysis.** At least two aspects of the diff are analyzed
   concurrently (e.g., type inference from content and scope inference from
   content) before the message writer runs.

4. **Specialized agents.** The diff analyzer, message writer, and quality
   checker are distinct nodes with separate prompts and responsibilities. Each
   agent produces structured output consumed by downstream nodes.

5. **Public API unchanged.** `generate_commit_message`, `apply_commit`,
   `generate_and_commit`, and `CommitMessage` retain their current signatures.
   Old callers see no behavioral change they must adapt to.

6. **CLI gets new quality flags.** Three new CLI flags are added to override
   `git.quality.*` config keys, following the same pattern as existing git and
   LLM overrides.

7. **Fallback still works.** If all LLM agents fail or return garbage, the
   deterministic fallback body (`_build_fallback_body`) is returned.

8. **Tests pass with mocked LLM.** The existing test patterns (mock the LLM
   response) continue to work. Graph topology and routing are testable without
   real network calls.

## Constraints

- **No human-in-the-loop.** The entire pipeline runs unattended, same as today.
- **Backward-compatible public interface.** `autocommit/__init__.py` exports,
   `generate_commit_message` keyword arguments, and `apply_commit` arguments
   must not change.
- **Python 3.10+ support must be preserved.**
- **New dependency:** `langgraph` will be added to `pyproject.toml` and
   `requirements.txt`.
- **Existing config keys retain their behavior.** New config keys (e.g., retry
   budget, quality thresholds) must be optional with sensible defaults.
- **Tests must remain deterministic and local.** No real network calls or
   running Ollama servers.
- **API key handling unchanged.** Credential resolution stays in
   `llm_provider.py`; the graph should accept already-resolved LLM instances.

## Non-Goals

- **No human-in-the-loop approval before committing.** The generate-and-commit
  flow remains fully automatic.
- **No change to Git behavior** (autostage, signoff, amend, push all work as
  today).
- **No removal of the existing deterministic fallback.**
- **No support for switching between graph and non-graph modes.** This replaces
  the old pipeline; it does not add a toggle.
- **No changes to `autocommit/utils/git_utils.py`** beyond what the graph
  nodes consume as input.

## Impacted Areas

- Public API: no
- CLI: yes (new flags `--quality-max-retries`, `--min-body-lines`, `--check-boilerplate` / `--no-check-boilerplate`)
- Config: yes (new keys for retry budget, quality thresholds, etc.)
- LLM prompt/provider: yes (new agent-specific prompts, graph routing logic)
- Git behavior: no
- Tests/docs: yes (new tests for graph topology, routing, fallback; docs updated
  for new dependency and config keys)

## Notes

- The current `build_chain(llm)` in `commit_chain.py` would be replaced by a
  `build_graph(llm, fallback_llm)` that returns a compiled `StateGraph`.
- `generate_commit_message` in `core.py` would call `graph.invoke(state)`
  instead of `chain.invoke(inputs)`.
- The single `DEFAULT_PROMPT` may be replaced by multiple focused prompts for
  each agent (diff analyzer, message writer, quality checker).
- The `JsonOutputParser` would remain for parsing individual agent outputs but
  may be augmented with `PydanticOutputParser` for structured state types.
