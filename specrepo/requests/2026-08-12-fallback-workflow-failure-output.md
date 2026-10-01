# Feature Request: Output fallback workflow failures

Status: requested
Date: 2026-08-12
Requester: brandonbenge

## Summary

When an LLM sub-task enters the configured fallback path and that fallback
attempt also fails, the script must output the fallback failure reason.

## Problem

`autocommit/chains/commit_chain.py::_call_with_fallback` currently emits a
warning containing the primary attempt's failure before invoking the fallback.
It then returns `fallback.result`. If the fallback call raises or produces an
unusable parsed result, `_call_llm` captures that reason in `fallback.error`,
but `_call_with_fallback` discards it. A run can therefore reach the
deterministic commit-message fallback without telling the user why the fallback
LLM failed.

## Desired Behavior

When the fallback LLM attempt returns no usable result, handle its failure the
same way the existing primary-failure path handles failures: use the same
bounded `_safe_error_text` formatting, warning structure and task label, and
`state.errors` enrichment pattern. Preserve the existing primary warning and
all existing fallback selection and deterministic recovery behavior.

## Acceptance Criteria

1. If a configured fallback LLM raises, output a `UserWarning` following the
   existing primary-failure warning pattern and containing the task label, the
   `_safe_error_text`-formatted failure reason, and wording that identifies it
   as a fallback LLM failure.
2. If the fallback LLM produces non-dict/unparseable output, output the same
   warning with the existing no-usable-result reason.
3. A primary failure followed by a fallback failure produces both diagnostics:
   the existing primary/falling-back warning and the new fallback-failed
   warning.
4. No fallback-failed warning is emitted when the fallback succeeds, the
   primary succeeds, or no fallback is configured.
5. The fallback failure reason is recorded in `state.errors` through the
   existing error callback, matching the primary entry pattern (for example,
   `"<task>: fallback failed (<reason>)"`) without removing existing entries.
6. Tests observe the output deterministically without network access or a
   running Ollama server.

## Constraints And Non-Goals

- Do not change when the fallback is selected.
- Do not change the deterministic fallback commit-message behavior.
- Do not add configuration, CLI flags, logging infrastructure, or public API
  changes.
- Format and truncate fallback exception text with the existing
  `_safe_error_text` path exactly as primary exception text is handled. Do not
  introduce separate fallback credential redaction or a new secret-safety
  guarantee; this change inherits the existing primary-error exposure model.
- Preserve Python 3.10+ support and thread-safe output from concurrent analysis
  tasks.

## Compatibility

This is an additive diagnostic behavior change. Successful return values,
fallback selection, public signatures, and configuration remain unchanged.
