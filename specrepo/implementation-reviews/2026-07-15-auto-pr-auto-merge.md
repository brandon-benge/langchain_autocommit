# Implementation Review: Auto-Merge Flag for Automated PR Creation

Status: implementation_reviewed
Date: 2026-07-15
Reviewer: brandonbenge (via @request-author; specialized @implementation-reviewer agent unavailable)
Approval Record: `specrepo/approved/2026-07-15-auto-pr-auto-merge/approval.md`

## Approved Architecture Readback

Extend the existing `git.auto_pr` PR-creation feature with an optional
auto-merge flag. When `git.auto_pr.auto_merge` is `true`, after a pull
request is created via the existing infrastructure, the tool calls the
provider's native auto-merge API (GitHub: `enable_auto_merge`, GitLab:
`merge_when_pipeline_succeeds`) and returns immediately. The merge
method is configurable via `git.auto_pr.merge_method`. The merge timeout
config key exists for future synchronous mode but is not used by the
native implementation.

## Consistency Check

- Product behavior is clear: yes
- Architecture boundaries are clear: yes
- Public API impact is clear: yes — `apply_commit()` gains 3 new
  keyword-only parameters (`auto_pr_auto_merge`,
  `auto_pr_merge_method`, `auto_pr_merge_timeout`). Return type
  unchanged (`str | None`). `generate_and_commit()` pass-through only.
- CLI impact is clear: yes — 4 new flags
  (`--auto-pr-auto-merge`, `--no-auto-pr-auto-merge`,
  `--auto-pr-merge-method`, `--auto-pr-merge-timeout`).
- Config impact is clear: yes — 3 new keys under `git.auto_pr`
  (`auto_merge`, `merge_method`, `merge_timeout`).
- Test plan is clear: yes — 13 test cases across 3 files with mocked
  library calls.

## Implementation Map

| File | Planned Change |
|---|---|
| `autocommit/utils/pr_utils.py` | Add `create_pr_and_auto_merge()` function that calls native auto-merge APIs after PR creation. Existing `create_pr()` unchanged. |
| `autocommit/core.py` | Add 3 new keyword parameters to `apply_commit()`; switch between `create_pr()` and `create_pr_and_auto_merge()` based on `auto_pr_auto_merge`; `generate_and_commit()` reads new config keys. |
| `autocommit/params.yaml` | Add `auto_merge: false`, `merge_method: merge`, `merge_timeout: 600` under `git.auto_pr`. |
| `autocommit/cli.py` | Add 4 new CLI flags; wire into `apply_commit()` call; update output message for auto-merge. |
| `specrepo/specs/product.md` | ✅ Already updated — non-goal narrowed. |
| `specrepo/specs/architecture.md` | ✅ Already updated — new config keys, `pr_utils.py` description, and flow added. |
| `tests/test_pr_utils.py` | Add tests for `create_pr_and_auto_merge()` with GitHub and GitLab mocks. |
| `tests/test_core.py` | Add tests for `apply_commit()` with auto-merge params; test `generate_and_commit()` pass-through. |
| `tests/test_autocommit.py` | Add tests for new CLI flags and output messages. |

## Questions Or Blockers

None. The approved architecture is internally consistent, fully maps to
concrete files, and all impacted areas have been identified.

## Verification Plan

```bash
pytest tests/test_pr_utils.py tests/test_core.py tests/test_autocommit.py
```

## Review Decision

Proceed
