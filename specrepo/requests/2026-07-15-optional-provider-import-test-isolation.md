# Feature Request: Isolate Optional Provider Import-Failure Tests

Status: requested
Date: 2026-07-15
Requester: brandonbenge

## Summary

Make the optional GitHub and GitLab provider-library missing tests deterministic
when those libraries are installed in the test environment. The tests must
force the selected import to fail instead of merely removing a fake module and
allowing Python to import the real installed package.

## Problem

`tests/test_pr_utils.py` installs fake `github` and `gitlab` modules for normal
provider tests. Its two missing-library tests currently remove the selected
module from `sys.modules` and expect the next import to fail. That assumption
holds only when the real optional dependency is absent.

After adding PyGithub to the development requirements, removing the fake
`github` module exposes the installed package. The GitHub missing-library test
then creates a real client with its fake token, attempts a remote API call, and
fails with HTTP 401 instead of exercising the intended `ImportError` branch.
The GitLab test has the same latent defect whenever `python-gitlab` is
installed.

## Desired Behavior

- The PyGithub-missing test deterministically raises an import failure for the
  `github` module even when PyGithub is installed or already imported.
- The python-gitlab-missing test provides the same isolation for `gitlab`.
- Both tests continue to verify the existing clear `RuntimeError` messages.
- Neither missing-library test can instantiate a real provider client or make
  a network request.
- Runtime source behavior remains unchanged.

## Acceptance Criteria

- `test_github_library_missing` passes in an environment where PyGithub is
  installed and importable.
- `test_gitlab_library_missing` does not depend on whether python-gitlab is
  installed, absent, or already present in `sys.modules`.
- The tests force `ModuleNotFoundError`/`ImportError` at import time using a
  scoped, automatically restored import block.
- Both tests retain their assertions for the provider-specific installation
  guidance raised by `create_pr()`.
- The complete test suite passes without provider credentials or network
  access.

## Constraints

- Limit implementation changes to `tests/test_pr_utils.py`.
- Do not change `autocommit/utils/pr_utils.py` or any runtime behavior.
- Do not uninstall provider libraries or make test outcomes depend on the
  environment's installed distributions.
- Restore interpreter import state after each test, including on assertion
  failure.
- Preserve the existing fake-module fixture used by successful provider tests.

## Non-Goals

- Changing optional dependency declarations or versions.
- Changing provider API adapters, error messages, or exception handling.
- Adding live GitHub or GitLab integration tests.
- Broadly blocking all network access in the suite.
- Refactoring unrelated provider or auto-merge tests.

## Impacted Areas

- Public API: no
- CLI: no
- Config: no
- LLM prompt/provider: no runtime provider change; test isolation only
- Git behavior: no
- Tests/docs: yes — two missing-library tests in `tests/test_pr_utils.py`

## Notes

The observed failure is
`tests/test_pr_utils.py::TestCreatePR::test_github_library_missing`: with
PyGithub installed, the test reaches GitHub using the fake token and receives
HTTP 401. The test should exercise the local import-error path regardless of
the installed environment.
