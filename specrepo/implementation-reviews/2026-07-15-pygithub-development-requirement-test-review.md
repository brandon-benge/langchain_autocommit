# Test Review: Include PyGithub In Development Requirements

Status: pass
Date: 2026-07-15
Reviewer: @test-reviewer
Approval Record: `specrepo/approved/2026-07-15-pygithub-development-requirement/approval.md`
Implementation Review: `specrepo/implementation-reviews/2026-07-15-pygithub-development-requirement.md`

## Review Scope

Reviewed the approved request, proposal, approval record, implementation
review, current `requirements.txt` diff, unchanged `pyproject.toml` and
`run_venv.sh`, and the implementation verification plan.

The review independently verified:

- exactly one active `PyGithub>=2.0,<3.0` development requirement;
- exact range synchronization with the unchanged `github` optional extra;
- unchanged core dependencies and `auto-pr` optional extra;
- no `python-gitlab` or other provider requirement added;
- successful requirements installation and `github` import in an isolated
  temporary virtual environment;
- no mutation of the user's existing `.venv`;
- the complete current pytest suite;
- diff validity and approved file scope.

No implementation file was edited during this review.

## Manifest Assessment

The active, non-comment lines in `requirements.txt` contain exactly one
PyGithub declaration:

```text
PyGithub>=2.0,<3.0
```

Parsing `pyproject.toml` with `tomllib` confirmed:

- `[project].dependencies` does not contain PyGithub;
- `project.optional-dependencies.github` remains exactly
  `['PyGithub>=2.0,<3.0']`;
- `project.optional-dependencies.auto-pr` remains exactly
  `['autocommit[github]']`.

The active development requirements contain no `python-gitlab` entry.

SHA-256 comparisons against `HEAD` confirmed that `pyproject.toml` and
`run_venv.sh` are byte-for-byte unchanged. The existing bootstrap still runs
`pip install -r requirements.txt` before the editable project install, so it
will consume the new entry without a script change.

## Verification Evidence

### Isolated install and import

A temporary environment was created under `/tmp`, then the development
manifest was installed with:

```bash
python3 -m venv <temporary-directory>/venv
<temporary-directory>/venv/bin/python -m pip install \
  --disable-pip-version-check -q -r requirements.txt
```

The isolated interpreter then successfully executed:

```python
from github import Github
```

Observed result:

```text
PyGithub=2.9.1
Github.__module__=github.MainClass
```

The installed major version satisfies the approved `>=2.0,<3.0` range. The
temporary environment was removed automatically after verification.

The user's `.venv` still could not import `github` after the isolated check,
matching its pre-review state and proving that the verification did not modify
the active development environment.

### Complete test suite

Command:

```bash
.venv/bin/python -m pytest -q
```

Result:

- 211 tests passed in 2.79 seconds.
- Aggregate statement coverage: 89%.
- Current config, core, CLI, Git, token, PR-provider, and auto-merge tests all
  passed.

### Diff and scope validation

`git diff --check` passed with no whitespace errors.

The tracked implementation diff contains only `requirements.txt`, adding one
comment heading and the approved requirement. There are no tracked changes to:

- `pyproject.toml`;
- `run_venv.sh`;
- source code or tests;
- README or baseline specs;
- CLI, configuration, provider, Git, auto-PR, or auto-merge behavior.

The new SpecRepo request, proposal, approval, implementation review, and this
test review are workflow artifacts rather than implementation-scope expansion.

## Acceptance Coverage

| Approved criterion | Evidence | Assessment |
| --- | --- | --- |
| Exactly one active approved requirement | Case-insensitive active-line manifest check | Passed |
| Range matches `github` optional extra | Parsed manifests both contain exact `PyGithub>=2.0,<3.0` | Passed |
| Installing requirements makes `github` importable | Isolated full-manifest install imported `Github` from PyGithub 2.9.1 | Passed |
| `run_venv.sh` needs no follow-up install | Script unchanged and already installs `requirements.txt` | Passed |
| Package consumers retain optional dependency boundary | Core dependencies and optional extras unchanged | Passed |
| No GitLab/provider scope expansion | No active `python-gitlab` development requirement; source unchanged | Passed |
| Existing behavior remains green | 211-test full suite passed | Passed |
| Patch is clean and bounded | `git diff --check` passed; only manifest implementation changed | Passed |

## Residual Risk

- `requirements.txt` is a ranged development manifest rather than a lockfile,
  so future clean bootstraps can resolve newer compatible PyGithub 2.x and
  transitive dependency versions.
- Fresh bootstrap installation still depends on package-index availability and
  network access when packages are not cached.
- GitLab remains intentionally absent from the default development manifest;
  contributors testing GitLab integration must install its optional extra.

These risks are non-blocking and consistent with the approved development-only
dependency contract.

## Recommendation

**Pass — ready to commit and push on the current
`request/auto-pr-auto-merge` branch.** The manifest contains exactly the
approved requirement, isolated installation provides the runtime import, the
published package dependency model remains unchanged, and the complete suite
and patch checks pass.
