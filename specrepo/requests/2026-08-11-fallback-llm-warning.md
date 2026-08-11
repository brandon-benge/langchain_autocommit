# Feature Request: Warning when falling back to the fallback LLM

Status: requested
Date: 2026-08-11
Requester: brandonbenge

## Summary

When the commit-message pipeline's primary LLM call fails and the pipeline
falls back to the configured fallback LLM, the tool should emit a warning
message that includes the error from the primary attempt and a note that it is
falling back. Today the fallback happens silently, which makes degraded
generation (primary down, slow, or misconfigured) invisible to the user.

## Problem

`autocommit/chains/commit_chain.py` currently swallows primary-LLM failures:

- `_call_llm` wraps `chain.invoke(...)` in a bare `try/except Exception` and
  returns `None` on any failure, discarding the exception entirely.
- `_call_with_fallback` retries with the fallback LLM whenever the primary
  returns `None`, but emits no message about why or what happened.

When the primary provider fails mid-generation (network error, rate limit,
authentication failure, timeout, malformed JSON output), the user only sees the
final commit message. There is no way to know that the fallback model produced
it, or that the primary is misconfigured or unavailable. This hides operational
problems and makes support and diagnosis harder.

## Desired Behavior

When a primary LLM call fails and a fallback LLM is available and used, the run
emits a warning that:

1. Includes the error from the primary attempt (the exception message, or the
   reason no parsed result was produced when the call returned without raising).
2. Notes explicitly that the tool is falling back to the fallback LLM.

When the primary call succeeds, no fallback warning is emitted. When no
fallback LLM is configured, no fallback warning is emitted and current behavior
is unchanged.

## Acceptance Criteria

1. **Warning on primary failure with fallback used.** If the primary LLM call
   for any agent node (analyze type, analyze scope, or write message) raises an
   exception, and a fallback LLM is configured, the run emits a warning that
   includes the primary error message and a note that it is falling back.

2. **Warning on failed primary result without exception.** If the primary call
   returns no usable parsed result (e.g., parser output is not a dict), and a
   fallback LLM is configured, the run emits a warning that notes the fallback
   and the reason no result was produced.

3. **No warning on success.** When the primary LLM call succeeds, no fallback
   warning is emitted.

4. **No warning without fallback.** When `fallback_llm` is `None`, no fallback
   warning is emitted and behavior is unchanged.

5. **Fallback result still used.** The warning does not change the generated
   commit message; the fallback LLM's result is still used when the primary
   fails, and downstream quality-loop and deterministic-fallback behavior are
   unchanged.

6. **Observable through tests.** The warning is emitted in a way that existing
   and new tests can observe deterministically (e.g., captured output or a
   warning/log record), without real network calls or a running Ollama server.

## Constraints

- **No new config keys.** The warning is always on; no flag or config key is
  introduced to enable or disable it in this request.
- **No behavior change to fallback selection.** The decision of when to fall
  back, and the deterministic `_build_fallback_body` path in `core.py`, remain
  as they are today.
- **Backward-compatible public interface.** `autocommit/__init__.py` exports,
  `generate_commit_message` keyword arguments, and return shapes must not
  change.
- **Python 3.10+ support must be preserved.**
- **Tests must remain deterministic and local.** No real network calls or
  running Ollama servers.
- **Thread-safety of output.** The diff-analysis sub-tasks run in a
  `ThreadPoolExecutor`; the warning must not garble or interleave in a way that
  hides which sub-task failed.

## Non-Goals

- **No change to the deterministic fallback body.** When both primary and
  fallback fail, `_build_fallback_body` still produces the final message as
  today.
- **No change to provider-setup fallback messaging.** Messages already printed
  during LLM construction in `autocommit/utils/llm_provider.py` (e.g., "Primary
  provider setup failed") are out of scope; this request covers the
  mid-generation retry path inside the graph nodes.
- **No retry or timeout policy changes.**
- **No suppression or filtering controls** for the new warning.
- **No documentation of the warning as a public contract** beyond acknowledging
  it may appear in CLI output.

## Impacted Areas

- Public API: no
- CLI: yes (warning appears in CLI output when the fallback fires)
- Config: no
- LLM prompt/provider: yes (the fallback call path in
  `autocommit/chains/commit_chain.py`)
- Git behavior: no
- Tests/docs: yes (new tests for warning emission; docs updated if user-facing
  behavior is described)

## Notes

- `_call_llm` currently discards exceptions, so capturing the primary error
  requires surfacing it (e.g., returning the exception along with the result or
  logging it at the point of failure). The exact mechanism is an implementation
  detail for the proposal.
- The warning should identify which attempt failed when multiple sub-tasks run
  concurrently (analyze type vs. analyze scope vs. write message) so the user
  can tell which agent fell back.
- Mechanism choice (direct print, `warnings.warn`, or `logging`) is left to the
  architecture proposal; the acceptance criteria above hold for any of them as
  long as the message is observable and includes the primary error and the
  fallback note. Repo precedent exists for direct `print` in
  `llm_provider.py`; `core.py` holds an unconfigured logger.
