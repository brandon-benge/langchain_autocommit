# Approval Record: Warning when falling back to the fallback LLM

Status: approved
Date: 2026-08-11
Approver: brandonbenge (via @spec-reviewer -> @architecture-approver automatic approval)
Request: `specrepo/requests/2026-08-11-fallback-llm-warning.md`
Approved Proposal: `specrepo/proposals/2026-08-11-fallback-llm-warning/architecture.md`

## Decision

Approved

## Approved Scope

- Change the private `_call_llm` in `autocommit/chains/commit_chain.py` to return
  a `_LLMCall` NamedTuple `(result, error)` instead of `dict | None`, capturing
  the primary failure reason (exception text via a bounded `_safe_error_text`
  helper, or the "no usable parsed result" reason for non-dict output).
- Add a required keyword-only `task_label` to `_call_with_fallback` and emit a
  `UserWarning` (via `warnings.warn`) when the fallback branch is entered
  (primary failed and `fallback_llm` is configured). Warning fires even when the
  fallback attempt itself fails; no warning on primary success or when
  `fallback_llm is None`.
- Pass `task_label` at the three call sites: `"analyze_type"` and
  `"analyze_scope"` in `analyze_diff_node` (concurrent `ThreadPoolExecutor`
  path), `"write_message"` in `write_message_node`.
- `_call_with_fallback` keeps its `dict | None` return contract; fallback
  selection logic, the fallback result usage, the deterministic
  `_build_fallback_body` path, the public API, and the CLI contract are
  unchanged.
- Enrich `state.errors` with the primary failure reason (e.g.,
  `"analyze_type: primary failed (ConnectionError: ...)"`) in
  `analyze_diff_node` / `write_message_node`, in addition to the existing
  `"<task>: no valid result"` entries. Purely additive; `errors` is never read
  downstream.
- Add deterministic, local tests (mocked LLMs, no network, no Ollama server) for
  warning emission in `tests/test_commit_chain.py`, including a graph-level test
  asserting the warning identifies the failing sub-task.
- Minimal README note acknowledging the warning may appear in CLI output when
  the primary fails and the fallback model is used.
- Update baseline specs: `product.md` (user-facing capability line),
  `architecture.md` (generation flow step 10: warning emission on fallback
  naming the failed agent and including the primary error), `quality.md`
  (warning-emission coverage for `tests/test_commit_chain.py`). Glossary
  unchanged.

## Conditions

- The `_call_llm` / `_LLMCall` refactor stays contained to `commit_chain.py`;
  no caller outside the module depends on `_call_llm`'s old return type
  (verified: only `_call_with_fallback` consumes it).
- The `state.errors` enrichment must preserve `_call_with_fallback`'s
  `dict | None` return contract (e.g., a private optional callback that receives
  the reason) and must keep the existing `"<task>: no valid result"` entries.
- The empty-dict `{}` primary-result edge case is NOT changed: it is treated as
  success today, no warning fires, and no fallback attempt occurs.
- No new config keys, no suppression/filtering controls, no logging
  infrastructure (`logging.basicConfig`, new loggers, handlers), and no changes
  to `core.py`, `cli.py`, `llm_provider.py`, `autocommit/__init__.py` exports,
  or `generate_commit_message` signatures/return shapes.
- Warning text must include the task label, the truncated primary error/reason
  (bounded ~300 chars; API key values must never be logged), and a fallback
  note. The fallback model name is NOT included.
- Tests assert warning presence per message, never inter-thread order; the full
  `pytest` suite must pass locally. The `state.errors` enrichment must be
  covered by a test assertion.

## Notes

- Warning wording approved as the proposed default:
  `"<task>: primary LLM call failed (<reason>); falling back to the fallback LLM."`
  Implementation may adjust wording only if it keeps the task label, the primary
  error/reason, and the fallback note. Non-blocking nuance: for the non-exception
  (unparseable result) case, phrasing such as "produced no usable result" reads
  better than "call failed"; keep the requested reason in the message.
- `stacklevel=2` is cosmetic (points at the graph-node caller frame) and may be
  adjusted during implementation.
- Existing `test_invoke_returns_subject_and_body` mocks `_call_with_fallback`
  entirely, so the new `task_label` keyword does not break it; all
  `TestCheckQuality` and `tests/test_core.py` tests are unaffected.

Next step: hand off to `@implementation-reviewer` to create the required
implementation review under `specrepo/implementation-reviews/` before any source
or test edits.
