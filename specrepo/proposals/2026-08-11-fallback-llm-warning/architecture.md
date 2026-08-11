# Architecture Proposal: Warning when falling back to the fallback LLM

Status: awaiting_approval
Date: 2026-08-11
Request: `specrepo/requests/2026-08-11-fallback-llm-warning.md`

## Summary

Make degraded commit-message generation visible. When a primary LLM call inside
any graph agent node (`analyze_type`, `analyze_scope`, or `write_message`)
fails and a fallback LLM is configured, emit a `UserWarning` that includes the
primary attempt's error (the exception message, or the reason no usable parsed
result was produced) and a note that the tool is falling back. The fallback
retry decision, the fallback result usage, the deterministic `_build_fallback_body`
path, the public API, and the CLI contract all stay unchanged.

The warning mechanism is `warnings.warn(..., UserWarning)` emitted from a small
helper in `autocommit/chains/commit_chain.py`. Rationale: "warning" is the
request's own vocabulary and acceptance criteria; `pytest.warns` gives
deterministic local observability without stream-capture plumbing across
threads; the `warnings` module serializes dispatch internally so the concurrent
analyze sub-tasks cannot garble each other; and `UserWarning` is shown to stderr
by default with zero configuration, so CLI users see it without any logging
setup. Direct `print(file=sys.stderr)` (repo precedent in `llm_provider.py`) is
rejected because it couples the library layer to stream I/O policy and its test
observability depends on stream capture, which is weaker than warning-record
capture for the thread-pool path. `logging` is rejected because no
`basicConfig`/handler setup exists anywhere in the repo and relying on
`logging`'s lastResort handler would be subtle and unidiomatic here.

## Current Architecture

- `autocommit/chains/commit_chain.py` builds a LangGraph `StateGraph` via
  `build_graph(llm, fallback_llm, config)` with three LLM-touching call sites:
  - `analyze_diff_node` submits `_call_with_fallback(ANALYZE_TYPE_PROMPT, ...)`
    and `_call_with_fallback(ANALYZE_SCOPE_PROMPT, ...)` concurrently in a
    `ThreadPoolExecutor(max_workers=2)`.
  - `write_message_node` calls `_call_with_fallback(WRITE_MESSAGE_PROMPT, ...)`,
    possibly repeatedly through the quality loop.
- `_call_llm(chain, **kwargs)` wraps `chain.invoke(kwargs)` in
  `try/except Exception: return None`. It discards the exception and returns
  `None` both when the call raises and when the parser output is not a `dict`.
- `_call_with_fallback(prompt, llm, fallback_llm, **kwargs)` calls `_call_llm`
  on the primary chain; if the result is `None` and `fallback_llm is not None`,
  it silently retries via `prompt | fallback_llm | parser`. No message is
  emitted in either branch.
- When both attempts fail (or the node produces no valid result), the node
  records a bookkeeping error in `state.errors` (e.g., `"analyze_type: no valid
  result"`), and `core.py` ultimately returns the deterministic
  `_build_fallback_body` when the graph yields an empty draft.
- `state.errors` is written by the nodes but never read by any router, node, or
  `core.py`; it is purely diagnostic bookkeeping.
- Tests: `tests/test_commit_chain.py` mocks `_call_with_fallback` at module
  level for the graph-level test and has no direct tests of `_call_llm` /
  `_call_with_fallback` fallback behavior. `tests/test_core.py` mocks
  `build_graph` entirely.
- Repo precedent for user-facing fallback messaging is direct `print()` in
  `autocommit/utils/llm_provider.py` (out of scope for this request).
  `core.py` has an unconfigured `logger`; no `logging.basicConfig` exists.

## Proposed Architecture

All changes are confined to the private LLM-call helpers and their call sites
in `autocommit/chains/commit_chain.py` plus tests. No change to
`core.py`, `llm_provider.py`, `cli.py`, config, or public API.

### Capture the primary error: `_call_llm`

Change the private `_call_llm` to return a small result object instead of
`dict | None`:

```python
class _LLMCall(NamedTuple):
    result: dict | None   # parsed dict when the call succeeded
    error: str | None     # human-readable reason when result is None


def _call_llm(chain, **kwargs) -> _LLMCall:
    """Call an LLM chain and return parsed JSON plus a failure reason."""
    try:
        result = chain.invoke(kwargs)
        if isinstance(result, dict):
            return _LLMCall(result=result, error=None)
        return _LLMCall(result=None, error="returned non-dict output (unparseable)")
    except Exception as e:
        return _LLMCall(result=None, error=_safe_error_text(e))
```

`_safe_error_text(e)` formats the exception as
`f"{type(e).__name__}: {e}"`, strips whitespace, and truncates to a bounded
length (e.g., 300 chars). Truncation guards against dumping request bodies or
credentials into terminal output, honoring the quality-spec rule that API key
values must never be logged. `_LLMCall` is module-private; nothing outside
`commit_chain.py` consumes it.

### Emit the warning: `_call_with_fallback`

`_call_with_fallback` gains a required keyword-only `task_label` so the warning
can name which agent fell back, and emits the warning at the moment the fallback
branch is entered:

```python
def _call_with_fallback(prompt, llm, fallback_llm, *, task_label, **kwargs) -> dict | None:
    """Try primary LLM, then fallback. Returns parsed dict or None.

    Emits a UserWarning when the primary attempt fails and a fallback LLM is
    configured (the fallback branch is entered), regardless of whether the
    fallback attempt itself succeeds.
    """
    parser = JsonOutputParser()
    primary = _call_llm(prompt | llm | parser, **kwargs)
    if primary.result is not None:
        return primary.result
    if fallback_llm is not None:
        _warn_fallback(task_label, primary.error)
        fb = _call_llm(prompt | fallback_llm | parser, **kwargs)
        return fb.result
    return None
```

The helper:

```python
def _warn_fallback(task_label: str, reason: str) -> None:
    warnings.warn(
        f"{task_label}: primary LLM call failed ({reason}); "
        "falling back to the fallback LLM.",
        UserWarning,
        stacklevel=2,
    )
```

Behavior notes:

- **Warning fires when the fallback path is entered** (primary failed and
  `fallback_llm` is configured), not only when the fallback succeeds. This
  matches the acceptance-criteria trigger ("primary failure ... and a fallback
  LLM is configured") and also surfaces the primary error in the both-fail →
  `_build_fallback_body` case, which is exactly when diagnosis matters most.
- **No warning on primary success** (`primary.result is not None` returns
  early).
- **No warning when `fallback_llm is None`** (the fallback branch is skipped).
- **Return contract unchanged**: `dict | None`; the fallback result is still
  returned and consumed exactly as today, so downstream node logic and
  `core.py` behavior are byte-for-byte identical.
- **Fallback selection unchanged**: the empty-dict edge (primary returns `{}`,
  which is "no usable parsed result" but not `None`) is a pre-existing quirk —
  `_call_with_fallback` treats `{}` as a successful primary return and does not
  fall back. This proposal does **not** change that behavior (the request
  forbids changing fallback selection); it is recorded as an observed edge case
  in Risks and left out of scope.

### Call-site updates

- `analyze_diff_node` passes `task_label="analyze_type"` for the type sub-task
  and `task_label="analyze_scope"` for the scope sub-task (each submitted to the
  `ThreadPoolExecutor`).
- `write_message_node` passes `task_label="write_message"`.

### Thread-safety of concurrent sub-tasks

- The `warnings` module guards filter/registry mutation with an internal lock
  and `warnings.warn` is thread-safe; concurrent `warn()` calls from the two
  analyze worker threads are serialized and cannot corrupt each other.
- Each message embeds its `task_label`, so even when two warnings land back to
  back, each line identifies the agent that fell back — the sub-task can never
  be hidden by interleaving.
- Test capture: `pytest.warns` / `recwarn` install a global `showwarning` that
  appends to a list; `list.append` is atomic in CPython, so warnings emitted
  from worker threads while `graph.invoke` is awaited are captured. Record order
  between the two sub-tasks is nondeterministic; tests assert presence per
  message, never order.

### Optional (flagged): enrich `state.errors`

`_call_with_fallback` is not currently told which node it serves beyond
`task_label`. Optionally, `analyze_diff_node` / `write_message_node` could
append the enriched reason to `state.errors` (e.g., `"analyze_type: primary
failed (ConnectionError: ...)"`) in addition to the existing
`"analyze_type: no valid result"`. `state.errors` is never read downstream, so
this is purely additive bookkeeping. This is a proposal-time open question (see
Open Questions); the default recommendation is to include it because it makes
the graph state self-describing and costs nothing.

## Scope

In scope:

- Capture the primary failure reason in `_call_llm` (exception message or
  non-dict-parse reason).
- Emit a `UserWarning` (via `warnings.warn`, `UserWarning`) from
  `_call_with_fallback` when the fallback branch is entered, naming the failed
  sub-task and including the primary error plus a fallback note.
- Add `task_label` to the three call sites.
- Add deterministic local tests for warning emission (mocked LLMs, no network,
  no Ollama server).
- Minimal README note that a warning may appear in CLI output when the primary
  provider fails and the fallback model is used.
- Update baseline specs that describe the fallback flow and test coverage.

Out of scope:

- **No new config keys or suppression controls** (request constraint).
- **No change to fallback selection logic, the deterministic
  `_build_fallback_body` path, or the both-fail fallback body behavior** (request
  constraints).
- **No change to provider-setup messaging in `llm_provider.py`** (e.g.,
  "Primary provider setup failed") — that path is explicitly out of scope.
- **No retry or timeout policy changes.**
- **No change to `core.py`, `cli.py`, `autocommit/__init__.py` exports, or
  `generate_commit_message` signatures/return shapes.**
- **No logging infrastructure** (no `logging.basicConfig`, no new logger).
- **No change to the empty-dict `{}` fallback-selection edge case.**

## API, CLI, And Config Changes

- Public API: none. `autocommit/__init__.py` exports, `generate_commit_message`
  keyword arguments, and return shapes are unchanged.
- CLI: no flag changes. CLI output may now contain a `UserWarning` line
  (Python renders it to stderr with a `commit_chain.py:<line>: UserWarning:`
  prefix) when a fallback fires mid-generation.
- Config: none. No keys added, no `params.yaml` change, no override behavior
  change.
- Prompt/provider behavior: prompts are unchanged. The fallback call path in
  `commit_chain.py` now emits a warning; the retry decision and returned value
  are identical.

## Files Expected To Change

| File | Change |
|------|--------|
| `autocommit/chains/commit_chain.py` | Add `import warnings` and `from typing import NamedTuple`. Add `_LLMCall` NamedTuple, `_safe_error_text`, `_warn_fallback`. Rewrite `_call_llm` to return `_LLMCall` with an error reason. Rewrite `_call_with_fallback` to accept `* , task_label` and warn when entering the fallback branch. Pass `task_label` at the three call sites (two in `analyze_diff_node`, one in `write_message_node`). Optionally enrich `state.errors` entries. |
| `tests/test_commit_chain.py` | Add `TestCallWithFallbackWarning` unit tests (direct, no threads) and a graph-level test asserting the warning identifies the sub-task. Existing graph test mocks `_call_with_fallback`, so it continues to pass unchanged. |
| `README.md` | One-line acknowledgment in a troubleshooting/notes section: when the primary LLM fails and the fallback model is used, a warning naming the failed step may appear in CLI output. |
| `specrepo/specs/architecture.md` | Update the commit-message generation flow (step 10) to state that falling back emits a warning naming the failed agent and including the primary error. |
| `specrepo/specs/product.md` | Add a user-facing capability line: the tool warns when the primary LLM fails and the fallback model is used. |
| `specrepo/specs/quality.md` | Add warning-emission tests (deterministic, mocked LLMs, no network) to the required coverage for `tests/test_commit_chain.py`. |

`autocommit/core.py`, `autocommit/cli.py`, `autocommit/utils/llm_provider.py`,
`autocommit/config.py`, and `autocommit/params.yaml` do **not** change.

## Test Plan

All tests are deterministic and local; LLM calls are mocked; no network or
running Ollama server is required.

- `tests/test_commit_chain.py` — `TestCallWithFallbackWarning`:
  - `test_warns_and_uses_fallback_on_exception`: primary chain raises
    (`RuntimeError("boom")`); fallback returns a valid dict. Assert
    `pytest.warns(UserWarning)` captures exactly one warning whose message
    contains the task label, `"boom"`, and `"falling back"`; assert the
    returned value is the fallback dict (acceptance criteria 1 and 5).
  - `test_warns_on_unparseable_primary_result`: primary `chain.invoke` returns
    a non-dict (e.g., a list); fallback returns a valid dict. Assert the
    warning notes "no usable parsed result" wording and the returned value is
    the fallback dict (criterion 2).
  - `test_no_warning_on_primary_success`: primary returns a valid dict; assert
    no warning and the primary result is returned (criterion 3).
  - `test_no_warning_when_fallback_none`: primary raises, `fallback_llm=None`;
    assert no warning and `None` returned (criterion 4).
  - `test_warns_even_when_fallback_also_fails`: primary and fallback both
    raise; assert the warning still fires with the primary error (documented
    trigger condition) and the function returns `None`.
  - `test_error_text_truncated`: primary raises with a very long message;
    assert the warning text is bounded (safety rule: no credential dump).
- `tests/test_commit_chain.py` — graph-level:
  - `test_analyze_fallback_warning_identifies_subtask`: build a graph with a
    primary `BaseChatModel` whose `invoke` raises and a fallback whose `invoke`
    returns valid JSON; invoke the graph under `pytest.warns`; assert a warning
    containing `"analyze_type"` is present (sub-task identification for the
    concurrent path).
  - Existing `test_invoke_returns_subject_and_body` (mocks
    `_call_with_fallback`) and all `TestCheckQuality` tests keep passing
    unchanged — no modification expected.
- `tests/test_core.py`: unchanged. Existing `TestGenerateCommitMessageLlmFallback`
  mocks `build_graph` and verifies the deterministic fallback body; the graph
  change does not affect `core.py`.
- `pytest`: full suite passes locally with mocked LLMs.

## Risks And Mitigations

- **Regression in fallback behavior.** `_call_llm`'s return type changes from
  `dict | None` to `_LLMCall`. Mitigation: `_call_llm` is module-private and
  its only consumer is `_call_with_fallback`; `_call_with_fallback`'s return
  contract (`dict | None`) and all call sites are unchanged; the existing graph
  test that mocks `_call_with_fallback` still passes. The full suite guards the
  fallback result path.
- **Warnings may be suppressed by consumer filters.** An embedding app or
  `python -W ignore` can hide `UserWarning`. Mitigation: this is the standard
  Python warning contract and acceptable here; the request's non-goals forbid a
  suppression control, and default CLI runs show `UserWarning`.
- **`warnings` dedup hides a repeated warning.** The default filter shows each
  unique message once per location, so a quality-loop retry that fails with the
  same primary error warns once. Mitigation: acceptable and arguably desirable
  (no spam); each distinct sub-task/error still warns. Tests use
  `warnings.simplefilter("always")` via `pytest.warns`, so dedup never weakens
  assertions.
- **Concurrent sub-task output garbling.** Two `warnings.warn` calls from the
  `ThreadPoolExecutor` could in principle interleave. Mitigation: the `warnings`
  module serializes dispatch, each single-line message is emitted atomically,
  and every message embeds its `task_label` so the failed sub-task is always
  identifiable. Tests assert message presence, not order.
- **Sensitive data in the error text.** Exception text can contain request
  details. Mitigation: `_safe_error_text` truncates to ~300 chars and never
  includes headers or key values; quality-spec "no API key logging" rule is
  preserved.
- **README/spec drift.** User-visible behavior changes require docs.
  Mitigation: minimal README note plus baseline-spec updates listed below.
- **Observed edge case (unchanged by design): empty-dict primary result.**
  Today a primary result of `{}` is treated as success by
  `_call_with_fallback` (no fallback attempt), then flagged as "no valid
  result" by the node and routed to the deterministic body. This proposal does
  not alter that selection (the request forbids changing fallback selection),
  so no warning fires in that specific case. Mitigation: documented here as a
  known pre-existing behavior; a future request can decide whether `{}` should
  trigger the fallback.

## Open Questions

- **Should the primary error also be recorded in `state.errors`?** Recommended:
  yes, append the enriched reason (e.g., `"analyze_type: primary failed
  (ConnectionError: ...)"`) in `analyze_diff_node` / `write_message_node`
  alongside the existing `"<task>: no valid result"` entries. Purely additive;
  `errors` is never read downstream. Approver confirmation requested.
- **Exact warning wording.** Proposed default:
  `"<task>: primary LLM call failed (<reason>); falling back to the fallback
  LLM."` The implementation may adjust wording as long as it includes the task
  label, the primary error/reason, and the fallback note.
- **Should the warning name the fallback model?** Recommended: no — keeps the
  message attribute-independent and matches the request ("a note that it is
  falling back").
- **`stacklevel` behavior.** `stacklevel=2` points the warning at
  `_call_with_fallback`'s caller frame, which is a graph-node closure; the exact
  location shown is cosmetic and may be adjusted during implementation.

## Baseline Spec Updates

- Product spec: **changed** — add a user-facing capability line stating that
  the tool warns when the primary LLM fails and the fallback model is used.
- Architecture spec: **changed** — update the commit-message generation flow
  (step 10) to describe warning emission on the fallback path, including the
  failed-agent name and primary error.
- Quality spec: **changed** — extend the `tests/test_commit_chain.py` coverage
  area to include deterministic warning-emission tests with mocked LLMs.
- Glossary: **unchanged** — no new terms.

## Approval Request

Approve this proposal before implementation begins. After approval, the
implementation reviewer should confirm the `_LLMCall` refactor is contained to
`commit_chain.py`, that no caller depends on `_call_llm`'s old return type, and
that warning-emission tests are fully mocked and local before any source or
test edits.
