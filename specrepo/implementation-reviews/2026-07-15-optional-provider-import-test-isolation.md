# Implementation Review: Isolate Optional Provider Import-Failure Tests

Status: implementation_reviewed
Date: 2026-07-15
Reviewer: implementation-reviewer
Approval Record: `specrepo/approved/2026-07-15-optional-provider-import-test-isolation/approval.md`

## Approved Architecture Readback

The two optional-provider missing-library tests must simulate an import failure
without depending on whether PyGithub or python-gitlab is installed. In each
test, temporarily map only the selected top-level module name in `sys.modules`
to `None` with `unittest.mock.patch.dict`. Python then raises
`ModuleNotFoundError`, an `ImportError` subclass already translated by the
unchanged runtime code into the provider-specific `RuntimeError` under test.

The scoped mapping replaces the current manual `sys.modules.pop()` and
`try`/`finally` restoration. `patch.dict` restores the exact prior module value
after the assertion, including when the value came from the autouse fake-module
fixture or when the assertion fails. The existing `_run` mocks, provider URL
selection, fake-module fixture, successful provider tests, runtime source, and
user-facing error assertions remain unchanged.

## Consistency Check

- Product behavior is clear: yes; runtime behavior is unchanged and only test
  isolation becomes deterministic
- Architecture boundaries are clear: yes; implementation is limited to the
  two existing tests in `tests/test_pr_utils.py`
- Public API impact is clear: not applicable; no exports or signatures change
- CLI impact is clear: not applicable; no CLI code or behavior changes
- Config impact is clear: not applicable; no configuration changes
- Test plan is clear: yes; reproduce with PyGithub installed, run both focused
  tests, the provider test module, and the complete suite

The observed failure confirms the approved diagnosis. In the current `.venv`,
`github` imports from the installed PyGithub distribution. Running
`test_github_library_missing` removes the fixture module, imports that real
distribution, constructs `Github("fake")`, and reaches GitHub before failing
with HTTP 401. The existing runtime catches import errors correctly; the test's
module-removal technique is the only defect.

## Implementation Map

- `tests/test_pr_utils.py::TestCreatePR::test_github_library_missing`: replace
  lines 159-172's manual `sys.modules.pop("github", None)`, `try`/`finally`, and
  conditional restoration with:

  ```python
  with patch.dict(sys.modules, {"github": None}):
      with pytest.raises(RuntimeError, match="PyGithub is required"):
          create_pr(...)
  ```

  Preserve the `_run` mock's GitHub remote, fake token, call arguments, and
  provider-specific message assertion.
- `tests/test_pr_utils.py::TestCreatePR::test_gitlab_library_missing`: replace
  lines 179-192's equivalent manual removal/restoration with a scoped
  `patch.dict(sys.modules, {"gitlab": None})` context. Preserve the `_run`
  mock's GitLab remote, fake token, call arguments, and
  `python-gitlab is required` assertion.
- `tests/test_pr_utils.py::_fake_optional_modules`: no change; the nested
  per-test sentinel temporarily overrides and then restores whatever module
  value the fixture established.
- `autocommit/utils/pr_utils.py`, dependency manifests, scripts, README,
  configuration, baseline specs, and all other tests: no change.

The implementation-review artifact itself is the only SpecRepo file created
by this gate.

## Questions Or Blockers

None.

`patch` is already imported from `unittest.mock`, so the approved edit needs no
new import. The targeted `None` mappings cannot resolve a real provider package
and are automatically restored when each context exits.

## Verification Plan

First establish the regression environment and confirm that PyGithub is
installed and importable:

```bash
.venv/bin/python -c "import github; print(github.__file__)"
```

Run each missing-library test independently:

```bash
.venv/bin/python -m pytest -q \
  tests/test_pr_utils.py::TestCreatePR::test_github_library_missing
.venv/bin/python -m pytest -q \
  tests/test_pr_utils.py::TestCreatePR::test_gitlab_library_missing
```

The GitHub test must pass in this installed-PyGithub environment without an
HTTP warning, provider exception, or network response. The GitLab test must
pass whether its real optional package is installed or absent.

Then verify all provider mocks and the complete deterministic suite:

```bash
.venv/bin/python -m pytest -q tests/test_pr_utils.py
.venv/bin/python -m pytest -q
```

Finally, verify whitespace and approved scope:

```bash
git diff --check
git diff -- tests/test_pr_utils.py autocommit/utils/pr_utils.py \
  requirements.txt pyproject.toml run_venv.sh README.md \
  specrepo/specs/product.md specrepo/specs/architecture.md \
  specrepo/specs/quality.md
```

For this follow-up, the implementation diff must contain only the two scoped
test-body edits in `tests/test_pr_utils.py`. Existing changes from the preceding
approved development-requirement work must be distinguished from this
tests-only patch rather than attributed to this approval.

## Review Decision

Proceed
