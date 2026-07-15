# Approval Record: Isolate Optional Provider Import-Failure Tests

Status: approved
Date: 2026-07-15
Approver: user (safe completion authorization via @architecture-approver)
Request: `specrepo/requests/2026-07-15-optional-provider-import-test-isolation.md`
Approved Proposal: `specrepo/proposals/2026-07-15-optional-provider-import-test-isolation/architecture.md`

## Decision

Approved

## Approved Scope

- Update `test_github_library_missing` in `tests/test_pr_utils.py` to
  temporarily map `sys.modules["github"]` to `None` with scoped
  `unittest.mock.patch.dict` state restoration.
- Update `test_gitlab_library_missing` identically for
  `sys.modules["gitlab"]`.
- Preserve both tests' provider-specific `RuntimeError` message assertions and
  verify the focused tests, the complete provider test module, and the full
  test suite.

## Conditions

- Limit implementation changes to `tests/test_pr_utils.py`; do not edit
  runtime source, dependency manifests, scripts, README documentation,
  configuration, or baseline specs.
- Preserve the autouse fake-module fixture and the successful provider and
  auto-merge tests.
- Use scoped `patch.dict` contexts that restore the exact prior `sys.modules`
  values even if an assertion fails.
- The missing-library tests must not instantiate real provider clients, access
  credentials, or perform network requests.
- Retain the existing mocked remote URL selection so each test reaches only
  the intended local import-error branch.

## Notes

The existing tests remove fake modules from `sys.modules`, which permits
Python to import a real installed provider library. PyGithub is installed in
the reproducing development environment, so that approach can reach GitHub
with the fake token instead of testing the missing-library error. A targeted
`None` sentinel makes Python raise `ModuleNotFoundError`, an `ImportError`
subclass already handled by the unchanged runtime code. This is deterministic
test isolation and does not alter product behavior.
