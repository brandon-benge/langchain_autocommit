# Architecture Proposal: Isolate Optional Provider Import-Failure Tests

Status: awaiting_approval
Date: 2026-07-15
Request: `specrepo/requests/2026-07-15-optional-provider-import-test-isolation.md`

## Summary

Replace the environment-dependent `sys.modules.pop()` logic in the two
optional-provider missing-library tests with scoped `sys.modules` import-block
sentinels. Mapping the selected module name to `None` makes Python raise
`ModuleNotFoundError` even when the real package is installed or cached. The
existing runtime code catches that `ImportError` subclass and returns the
provider-specific setup error under test, without constructing a client or
performing network I/O.

## Current Architecture

`autocommit/utils/pr_utils.py` imports provider libraries lazily inside
`_create_pr_raw()`:

- GitHub executes `from github import Github` and converts `ImportError` into a
  `RuntimeError` that recommends `autocommit[github]`.
- GitLab executes `import gitlab` and converts `ImportError` into a
  `RuntimeError` that recommends `autocommit[gitlab]`.

`tests/test_pr_utils.py` has an autouse `_fake_optional_modules` fixture. It
adds fake `github` and `gitlab` modules only when those names are absent from
`sys.modules`, allowing successful adapter tests to patch provider classes
without requiring both optional distributions.

The two missing-library tests currently pop the selected fake module from
`sys.modules`, call `create_pr()`, and restore the saved value in `finally`.
Popping a cache entry does not block imports; it asks Python to resolve the
module again. When PyGithub or python-gitlab is installed, Python imports the
real package and the test can reach the real provider API with a fake token.

## Proposed Architecture

In each missing-library test, replace the manual `pop`/`try`/`finally` block
with a nested `unittest.mock.patch.dict` context that temporarily maps only the
selected top-level module to the import-block sentinel `None`:

```python
with patch.dict(sys.modules, {"github": None}):
    with pytest.raises(RuntimeError, match="PyGithub is required"):
        create_pr(...)
```

Use the equivalent `{ "gitlab": None }` mapping for the GitLab test.

Python's import machinery treats a `None` entry in `sys.modules` as a halted
import and raises `ModuleNotFoundError`, which is a subclass of `ImportError`.
This directly exercises the existing runtime exception translation. The
scoped patch restores the prior value after the assertion whether that value
was a fake fixture module, a real imported module, or absent.

The existing `_run` mock remains in place so provider detection still selects
the intended branch without executing Git. The autouse fake-module fixture and
all successful PR/auto-merge mocks remain unchanged.

## Scope

In scope:

- Update `test_github_library_missing` to block `github` imports with a scoped
  `sys.modules` sentinel.
- Update `test_gitlab_library_missing` to block `gitlab` imports identically.
- Verify both focused tests with PyGithub installed.
- Run the full deterministic suite.

Out of scope:

- Any edit outside `tests/test_pr_utils.py`.
- Runtime source, provider adapter, exception, or message changes.
- Dependency, CLI, config, Git, README, or baseline-spec changes.
- Live provider calls, credentials, or network access.
- Refactoring the general fake-module fixture or successful provider tests.

## API, CLI, And Config Changes

- Public API: none
- CLI: none
- Config: none
- Prompt/provider behavior: none
- Runtime dependency behavior: none
- Test behavior: missing-library simulations become independent of installed
  optional providers and cannot fall through to real provider clients

## Files Expected To Change

- `tests/test_pr_utils.py`: replace manual module removal/restoration in the
  GitHub and GitLab missing-library tests with scoped import-block sentinels.

No runtime source or documentation file is expected to change.

## Test Plan

- `.venv/bin/python -c "import github; print(github.__file__)"`: establish that
  PyGithub is installed and importable in the reproducing environment.
- `.venv/bin/python -m pytest -q tests/test_pr_utils.py::TestCreatePR::test_github_library_missing`:
  verify the GitHub missing-library path passes even with PyGithub installed.
- `.venv/bin/python -m pytest -q tests/test_pr_utils.py::TestCreatePR::test_gitlab_library_missing`:
  verify the GitLab simulation passes independently of package availability.
- `.venv/bin/python -m pytest -q tests/test_pr_utils.py`: verify all provider
  creation and auto-merge unit tests remain deterministic and mocked.
- `.venv/bin/python -m pytest -q`: verify the complete suite passes with the
  development requirements, without credentials or network calls.
- `git diff --check`: verify no whitespace errors.

The focused tests must not instantiate the real `github.Github` or
`gitlab.Gitlab` classes. Passing with installed PyGithub and a fake token is
the direct regression proof that no real GitHub request occurs.

## Risks And Mitigations

- Risk: Mutating `sys.modules` can leak interpreter state between tests.
  Mitigation: Use nested `patch.dict` context managers, which restore the exact
  prior values even when an assertion raises.
- Risk: A global import hook could affect unrelated imports during the test.
  Mitigation: Use a targeted `sys.modules` sentinel for only `github` or
  `gitlab`; do not patch `builtins.__import__` globally.
- Risk: The nested sentinel could conflict with the autouse fake-module
  fixture.
  Mitigation: The inner patch temporarily overrides the fixture value and then
  restores it before the outer fixture cleanup runs.
- Risk: The tests could stop validating the user-facing error text while
  focusing on import mechanics.
  Mitigation: Retain the existing `pytest.raises(..., match=...)` assertions
  for both provider-specific messages.

## Baseline Spec Updates

- Product spec: unchanged
- Architecture spec: unchanged
- Quality spec: unchanged

The change enforces the existing quality requirement that tests remain local
and deterministic. It does not change the approved test strategy, runtime
architecture, user-visible behavior, or terminology.

## Approval Request

Approve this proposal before implementation begins.
