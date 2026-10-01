# Architecture Proposal: Output fallback workflow failures

Status: awaiting_approval
Date: 2026-08-12
Request: `specrepo/requests/2026-08-12-fallback-workflow-failure-output.md`

## Summary

Extend the existing private fallback diagnostic path so that a failed fallback
LLM attempt is handled in the same pattern as a failed primary attempt: the
same bounded `_safe_error_text`, warning structure and task label, and
`state.errors` callback pattern. Preserve the existing primary-failure warning
and all generation/recovery behavior.

## Current Architecture

`_call_llm` in `autocommit/chains/commit_chain.py` returns a private
`_LLMCall(result, error)` value. `_call_with_fallback` invokes the primary,
warns when the primary fails and a fallback is configured, optionally reports
the enriched primary reason through `on_error`, and then invokes the fallback.
It returns `fallback.result` directly, discarding `fallback.error`.

Consequently, when both attempts fail, users see only the primary failure and
the statement that fallback is beginning. The existing
`test_warns_even_when_fallback_also_fails` codifies exactly one warning and
does not assert the fallback exception (`"fallback down"`). Graph nodes later
append generic `"<task>: no valid result"` bookkeeping and core may construct
a deterministic commit message, which hides the fallback provider's cause.

## Proposed Architecture

Keep the change inside `_call_with_fallback` and its existing diagnostic
helpers. After invoking the fallback:

1. Return immediately when `fallback.result` is not `None`.
2. When it is `None`, derive the reason exactly as for the primary: consume the
   `_LLMCall.error` produced by `_safe_error_text` for exceptions or
   `_NON_DICT_REASON` for non-dict output, with the same defensive default.
3. Emit a second `UserWarning` using the same warning structure and
   `task_label` convention as the primary warning, substituting fallback as the
   failed attempt. Generalize or reuse the private formatter rather than
   creating a parallel output policy.
4. Invoke the existing `on_error` callback with the matching additive state
   entry `"<task>: fallback failed (<reason>)"`, mirroring
   `"<task>: primary failed (<reason>)"`, then return `None`.

The warning is emitted only after an actual fallback attempt fails. The current
primary warning remains unchanged and continues to announce entry into the
fallback branch. `_safe_error_text` and `_NON_DICT_REASON` remain the source of
bounded exception and parse-failure text for both attempts. The fallback path
introduces no separate credential-redaction logic and makes no stronger
secret-safety guarantee than the existing primary-error path; it formats and
truncates captured exception text exactly the same way.

`warnings.warn(..., UserWarning, stacklevel=2)` remains the output mechanism.
It is already visible on stderr in ordinary CLI runs, observable via pytest,
and suitable for the concurrent diff-analysis tasks. Tests must assert warning
content, not cross-thread ordering.

## Scope

In scope:

- Output the fallback LLM's captured exception or no-usable-result reason using
  the existing primary-failure handling pattern.
- Preserve the separate existing primary-failure/falling-back warning.
- Add the fallback failure reason to `state.errors` through `on_error`.
- Add focused private-helper and graph-state tests.
- Update user-facing and architecture documentation.

Out of scope:

- Fallback selection, retries, timeouts, prompts, or model configuration.
- Deterministic fallback-body behavior in `autocommit/core.py`.
- CLI flags, config keys, logging setup, or warning suppression controls.
- Public API signatures, exports, or return types.
- Provider-setup output in `autocommit/utils/llm_provider.py`.

## API, CLI, And Config Changes

- Public API: none.
- CLI: no flags or exit-code changes; stderr gains a `UserWarning` when an
  attempted fallback LLM itself fails.
- Config: none.
- Prompt/provider behavior: none; only diagnostics after fallback failure are
  added.

## Files Expected To Change

- `autocommit/chains/commit_chain.py`: inspect `fallback.error`, reuse or
  generalize the primary warning structure for the fallback-failed warning,
  and send a matching enriched failure through the existing `on_error`
  callback.
- `tests/test_commit_chain.py`: assert two warnings and both failure reasons
  when both attempts fail; cover fallback non-dict output, no warning on
  fallback success, and graph-state enrichment.
- `README.md`: note that failure of the attempted fallback is also reported.
- `specrepo/specs/product.md`: describe fallback-attempt failure visibility.
- `specrepo/specs/architecture.md`: describe the second warning and error-state
  enrichment in the generation flow.
- `specrepo/specs/quality.md`: require coverage for fallback-attempt failure
  diagnostics.

## Test Plan

- `tests/test_commit_chain.py`: primary raises and fallback raises; assert two
  `UserWarning` records, with the first describing primary failure/fallback
  entry and the second containing the fallback exception and task label.
- `tests/test_commit_chain.py`: primary raises and fallback returns non-dict;
  assert the second warning reports the no-usable-result reason.
- `tests/test_commit_chain.py`: primary raises and fallback returns a valid
  dict; assert only the existing primary warning and unchanged returned dict.
- `tests/test_commit_chain.py`: primary succeeds or fallback is absent; assert
  no new fallback-failed warning.
- `tests/test_commit_chain.py`: graph invocation where both attempts fail;
  assert `state.errors` retains existing entries and includes the enriched
  fallback failure reason. Do not assert concurrent warning order.
- `pytest`: run the complete local suite.

## Risks And Mitigations

- Risk: two warnings may be perceived as noisy when both providers fail.
  Mitigation: they describe two distinct events and make the otherwise hidden
  fallback cause actionable; warnings remain filterable by standard Python
  mechanisms.
- Risk: as with primary errors, exception text may contain sensitive detail
  before truncation.
  Mitigation: route fallback exceptions through the same bounded
  `_safe_error_text` formatting used for primary exceptions. This proposal does
  not add separate credential redaction or claim an absolute no-secret-output
  guarantee.
- Risk: concurrent analyze warnings arrive in nondeterministic order.
  Mitigation: every warning includes its task label; tests assert content and
  counts without ordering across tasks.
- Risk: callback changes duplicate generic graph errors.
  Mitigation: keep enrichment additive and preserve all current
  `"<task>: no valid result"` entries for compatibility.

## Baseline Spec Updates

- Product spec: unchanged at proposal time; update during approved implementation.
- Architecture spec: unchanged at proposal time; update during approved implementation.
- Quality spec: unchanged at proposal time; update during approved implementation.
- Glossary: unchanged; no terminology change.

## Approval Request

Approve this proposal before implementation begins.
