# Test Review: Isolate Optional Provider Import-Failure Tests

Status: pass
Date: 2026-07-15
Reviewer: @test-reviewer
Approval Record: `specrepo/approved/2026-07-15-optional-provider-import-test-isolation/approval.md`
Implementation Review: `specrepo/implementation-reviews/2026-07-15-optional-provider-import-test-isolation.md`

## Review Scope

Reviewed the approved request, architecture proposal, approval record,
implementation review, current `tests/test_pr_utils.py` diff, and the unchanged
runtime provider implementation.

The review independently verified:

- both missing-library tests force import failure with scoped
  `sys.modules[module] = None` sentinels;
- the GitHub test remains deterministic with PyGithub installed and imported;
- the GitLab test does not depend on package absence or prior module state;
- neither test instantiates a provider client or accesses the network;
- provider-specific installation-guidance assertions remain intact;
- import state is restored after normal and exceptional context exit;
- the provider module and complete suite remain green;
- the tracked implementation diff is limited exactly to
  `tests/test_pr_utils.py` and passes whitespace validation.

No implementation file was edited during this review.

## Implementation Assessment

The two approved tests now use:

```python
with patch.dict(sys.modules, {"github": None}):
    ...

with patch.dict(sys.modules, {"gitlab": None}):
    ...
```

Each mapping is limited to the selected top-level provider name and is nested
inside the existing `_run` mock. Python treats the `None` cache entry as a
halted import and raises `ModuleNotFoundError`, an `ImportError` subclass
already translated by the unchanged runtime code.

The previous manual `sys.modules.pop()` and conditional restoration blocks are
removed. The autouse fake-module fixture, successful GitHub/GitLab adapter
tests, auto-merge tests, remote URL mocks, call arguments, and provider-specific
error-message matches are unchanged.

## Verification Evidence

### Installed-PyGithub environment

The active environment imports the real package from:

```text
.venv/lib/python3.13/site-packages/github/__init__.py
```

Installed distribution version: PyGithub 2.9.1.

This reproduces the environment in which the old `sys.modules.pop()` technique
could import the real client and reach GitHub.

### Individual regression tests

Commands:

```bash
.venv/bin/python -m pytest -q \
  tests/test_pr_utils.py::TestCreatePR::test_github_library_missing

.venv/bin/python -m pytest -q \
  tests/test_pr_utils.py::TestCreatePR::test_gitlab_library_missing
```

Result: each test passed independently in 0.07 seconds. The GitHub test passed
with real PyGithub installed and importable; neither run emitted an HTTP or
provider response.

### Guarded no-client/no-network verification

Both tests were also run together in-process after:

- preloading real PyGithub;
- preloading a fake `gitlab` module;
- replacing both provider constructors with guards that raise if instantiated;
- replacing `socket.socket.connect` and `requests.Session.request` with guards
  that raise on any network attempt.

Result: 2 tests passed in 0.09 seconds. No constructor or network guard fired.
After pytest returned, the original real `github` module and preloaded fake
`gitlab` module were still the exact objects in `sys.modules`. After the outer
scope exited, the fake GitLab entry was removed and the original GitHub entry
remained.

A separate intentional-exception probe raised inside a `patch.dict` context
and confirmed that the original GitHub module was restored on exceptional
exit.

### Complete provider suite

Command:

```bash
.venv/bin/python -m pytest -q tests/test_pr_utils.py
```

Result: 25 tests passed in 0.14 seconds; `autocommit/utils/pr_utils.py` reached
91% statement coverage.

### Complete repository suite

Command:

```bash
.venv/bin/python -m pytest -q
```

Result:

- 211 tests passed in 2.75 seconds.
- Aggregate statement coverage: 89%.
- No provider credentials or live integration were required.

### Diff and scope validation

`git diff --check` passed with no whitespace errors.

`git diff --name-only` reported only:

```text
tests/test_pr_utils.py
```

The tracked implementation diff consists solely of replacing the two manual
module-removal/restoration blocks with the approved scoped sentinels. Runtime
source, manifests, scripts, configuration, README, baseline specs, and all
other tests are unchanged by this implementation.

The new SpecRepo request, proposal, approval, implementation review, and this
test review are workflow artifacts rather than implementation-scope expansion.

## Acceptance Coverage

| Approved criterion | Evidence | Assessment |
| --- | --- | --- |
| GitHub missing-library test passes with PyGithub installed | Real PyGithub 2.9.1 present; individual and guarded tests pass | Passed |
| GitLab test is independent of module availability/cache state | Sentinel test passes; guarded run preloaded and restored a GitLab module | Passed |
| Import failure is scoped and automatically restored | `patch.dict` implementation plus identity and exceptional-exit probes | Passed |
| Existing provider-specific guidance remains asserted | Original `pytest.raises(..., match=...)` checks retained | Passed |
| No real provider client can be instantiated | Constructor guards did not fire | Passed |
| No network access occurs | Socket and Requests guards did not fire | Passed |
| Successful provider and auto-merge mocks remain stable | Complete 25-test provider module passes | Passed |
| Complete suite remains deterministic | 211 tests pass without credentials/network | Passed |
| Implementation scope is exact | Only `tests/test_pr_utils.py` changed; diff check clean | Passed |

## Residual Risk

- These tests deliberately validate import-time absence, not live provider API
  behavior. Live GitHub/GitLab integration remains outside the approved local,
  credential-free test strategy.
- The `None` sentinel relies on Python's documented import-cache behavior;
  this is supported by the project's Python 3.10+ runtime range and directly
  exercised in the active Python 3.13 environment.
- The broader provider suite does not globally disable all networking. The two
  regression tests were independently run with network guards, and successful
  provider paths remain mocked as before.

These risks are non-blocking and consistent with the approved test-only scope.

## Recommendation

**Pass — ready to commit and push from current `main`.** The regression is
deterministically covered with installed PyGithub, provider clients and network
access are excluded, module state restoration is verified, the complete suite
passes, and the implementation diff is exactly within scope.
