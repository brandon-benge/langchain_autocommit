# Implementation Review: Warning when falling back to the fallback LLM

Status: implementation_reviewed
Date: 2026-08-11
Reviewer: implementation-reviewer (pre-code review of approved architecture)
Approval Record: `specrepo/approved/2026-08-11-fallback-llm-warning/approval.md`

## Approved Architecture Readback

Make degraded commit-message generation visible. When a primary LLM call inside
any graph agent node fails and a fallback LLM is configured, emit a
`UserWarning` naming the failed sub-task, including the primary attempt's error
(exception text via a bounded `_safe_error_text` helper, or the reason no
usable parsed result was produced), and noting the fallback. Concretely:

- `_call_llm` (private, `commit_chain.py`) changes its return type from
  `dict | None` to a `_LLMCall` NamedTuple `(result, error)`, where `error` is
  `_safe_error_text(e)` (`f"{type(e).__name__}: {e}"`, stripped, truncated to
  ~300 chars) on exception, or the non-dict-output reason when parsing fails.
- `_call_with_fallback` gains a required keyword-only `task_label` and emits
  the warning the moment the fallback branch is entered (primary failed and
  `fallback_llm` is configured), regardless of whether the fallback attempt
  itself succeeds. Its `dict | None` return contract, the fallback result
  usage, fallback selection, `_build_fallback_body`, the public API, and the
  CLI contract are unchanged. The three call sites pass
  `task_label="analyze_type"`, `"analyze_scope"` (concurrent
  `ThreadPoolExecutor` path), and `"write_message"`.
- The approved scope additionally requires enriching `state.errors` with the
  primary failure reason (e.g., `"analyze_type: primary failed
  (ConnectionError: ...)"`) in `analyze_diff_node` / `write_message_node`,
  alongside the existing `"<task>: no valid result"` entries — purely additive
  bookkeeping (errors is never read downstream) that must preserve
  `_call_with_fallback`'s `dict | None` return contract (e.g., via a private
  optional callback that receives the reason).
- Warning wording approved as
  `"<task>: primary LLM call failed (<reason>); falling back to the fallback
  LLM."` with the non-exception case phrased as "produced no usable result";
  the fallback model name is NOT included; `stacklevel=2` is cosmetic.
- Tests: a new `TestCallWithFallbackWarning` class (~6 unit tests) plus one
  graph-level sub-task-identification test in `tests/test_commit_chain.py`,
  all deterministic and local (mocked LLMs, no network, no Ollama server).
- Docs: one-line README acknowledgment; baseline-spec updates to
  `product.md`, `architecture.md`, `quality.md`; `glossary.md` unchanged.

## Consistency Check

- Product behavior is clear: yes
- Architecture boundaries are clear: yes
- Public API impact is clear: not applicable (unchanged)
- CLI impact is clear: yes (no flag changes; a `UserWarning` line may appear in
  CLI stderr when a fallback fires mid-generation)
- Config impact is clear: not applicable (no config keys, no `params.yaml`
  change)
- Test plan is clear: yes (with one required addition, see Questions Or
  Blockers)

## Implementation Map

| File | Planned change |
|------|----------------|
| `autocommit/chains/commit_chain.py` | Add `import warnings` and `from typing import NamedTuple`. Add module-private `_LLMCall` NamedTuple, `_safe_error_text`, `_warn_fallback`. Rewrite `_call_llm` to return `_LLMCall`. Rewrite `_call_with_fallback` to accept `*, task_label` (plus a private optional error callback used for `state.errors` enrichment) and warn when the fallback branch is entered. Pass `task_label` at the three call sites (two in `analyze_diff_node`, one in `write_message_node`). Enrich `state.errors` entries in the nodes. |
| `tests/test_commit_chain.py` | Add `TestCallWithFallbackWarning` unit tests (direct, no threads) and one graph-level test asserting the warning identifies the failing sub-task. Add a test assertion covering the `state.errors` enrichment (approval condition). Existing `test_invoke_returns_subject_and_body` (mocks `_call_with_fallback` wholesale) and all `TestCheckQuality` tests remain unchanged. |
| `README.md` | One-line acknowledgment (e.g., near "Graceful fallback"): when the primary LLM fails and the fallback model is used, a warning naming the failed step may appear in CLI output. |
| `specrepo/specs/architecture.md` | Update the commit-message generation flow (step 10) to state that falling back emits a warning naming the failed agent and including the primary error. |
| `specrepo/specs/product.md` | Add a user-facing capability line: the tool warns when the primary LLM fails and the fallback model is used. |
| `specrepo/specs/quality.md` | Extend the `tests/test_commit_chain.py` coverage area with deterministic warning-emission tests (mocked LLMs, no network). |

`autocommit/core.py`, `autocommit/cli.py`, `autocommit/utils/llm_provider.py`,
`autocommit/config.py`, `autocommit/params.yaml`, and
`specrepo/specs/glossary.md` do **not** change.

Verification of the containment and isolation claims:

- `_call_llm` is module-private and has exactly one consumer:
  `_call_with_fallback` (`commit_chain.py:174,179`). No test or other module
  references `_call_llm`, `_LLMCall`, `_safe_error_text`, or `_warn_fallback`.
  The `_LLMCall` refactor cannot leak outside the module.
- `core.py` imports only `build_graph` from `commit_chain` (`core.py:6`), so
  `tests/test_core.py` (which mocks `autocommit.core.build_graph` entirely with
  `_MockGraph`, `test_core.py:137`) is unaffected by the refactor.
- The only existing test touching `_call_with_fallback` is
  `test_invoke_returns_subject_and_body`, which mocks it wholesale via
  `mocker.patch(...)` (a `MagicMock`); `MagicMock` accepts arbitrary keyword
  arguments, so the new required `task_label` kwarg cannot break it.
- `state.errors` is written by the nodes and read only at
  `commit_chain.py:431` for appending; it is never read for control flow, so
  the enrichment is additive and behavior-neutral.

## Questions Or Blockers

None blocking. The approved architecture is internally consistent, the scope
maps to concrete files, and the test plan is executable. Required conditions
for implementation:

1. **`state.errors` enrichment test (approval condition, gap in the proposal's
   Test Plan).** The approval record requires the enrichment AND that it be
   covered by a test assertion ("The `state.errors` enrichment must be covered
   by a test assertion"), but the proposal's Test Plan lists no explicit
   assertion for it. The implementation must add one — e.g., the graph-level
   test asserts `"analyze_type: primary failed"` appears in `result["errors"]`
   alongside the existing `"analyze_type: no valid result"` entry, or a unit
   test asserts the private error callback fires with the primary reason. This
   is a test-coverage addition, not a design change.
2. **Enrichment mechanism must preserve the `dict | None` contract.** Use a
   private optional callback that receives the reason (per the approval
   condition); `_call_with_fallback`'s return type and the existing
   `"<task>: no valid result"` entries stay unchanged. In `analyze_diff_node`
   the callback appends to a list read only after both futures complete, so
   thread safety holds (`list.append` is atomic in CPython).
3. **Warning wording.** Keep the task label, the truncated primary
   error/reason, and the fallback note; do NOT name the fallback model. For the
   non-exception (unparseable result) case, use "produced no usable result"
   phrasing per the approval notes rather than "call failed". `stacklevel=2`
   is cosmetic and adjustable.
4. **Empty-dict `{}` primary-result edge case must NOT change** (treated as
   success today; no warning, no fallback attempt).
5. **Thread-safety of test capture.** The graph-level test runs the real
   `ThreadPoolExecutor` path; `warnings.warn` dispatch is serialized by the
   `warnings` module and `pytest.warns` captures from worker threads (the main
   thread blocks on `future.result()` while workers warn). Assert warning
   presence per message, never inter-thread order.
6. **Environment note (non-code).** The baseline suite could not be executed in
   this review environment because no Python environment with `pytest` is
   available (no `.venv`; system `python3.13` lacks pytest). This is recorded
   as the verification exception per `tests_run_or_exception_recorded`; the
   implementation's verification step must run `pytest` in a configured
   environment.

## Verification Plan

Default command per `specrepo/spec.yaml`:

```bash
pytest
```

Focused scope for this change:

```bash
pytest tests/test_commit_chain.py
```

Required coverage:

- `TestCallWithFallbackWarning` unit tests: warning on primary exception with
  fallback used and fallback result returned; warning on unparseable primary
  result ("produced no usable result" wording); no warning on primary success;
  no warning when `fallback_llm is None`; warning still fires when the fallback
  also fails (returns `None`); warning text bounded for a very long exception
  (~300-char truncation).
- Graph-level test: primary model `invoke` raises, fallback returns valid JSON,
  graph invoked under `pytest.warns`, assert a warning containing
  `"analyze_type"` is present.
- `state.errors` enrichment assertion (required condition 1 above).
- Existing `test_invoke_returns_subject_and_body` and all `TestCheckQuality`
  tests pass unchanged; `tests/test_core.py` passes unchanged.
- All tests deterministic and local: mocked LLMs, no network calls, no running
  Ollama server (per `specrepo/specs/quality.md`).

## Review Decision

Proceed
