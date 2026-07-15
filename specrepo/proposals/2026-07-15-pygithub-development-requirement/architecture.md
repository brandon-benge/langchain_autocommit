# Architecture Proposal: Include PyGithub In Development Requirements

Status: awaiting_approval
Date: 2026-07-15
Request: `specrepo/requests/2026-07-15-pygithub-development-requirement.md`

## Summary

Add `PyGithub>=2.0,<3.0` to the repository-level `requirements.txt`. The
existing `run_venv.sh` bootstrap already installs that manifest, so a newly
created contributor environment will include the GitHub client required by
the implemented auto-PR and auto-merge paths. Keep PyGithub in the existing
optional `github` extra in `pyproject.toml`, rather than promoting it to a core
package dependency.

## Current Architecture

The dependency manifests serve two related but distinct audiences:

- `pyproject.toml` defines the installable package contract. PyGithub is
  declared as `PyGithub>=2.0,<3.0` under the optional `github` extra, and the
  `auto-pr` extra aliases that GitHub integration. Package consumers who do
  not request either extra do not install PyGithub.
- `requirements.txt` is the repository development/bootstrap manifest. It
  includes core runtime and test dependencies, but not PyGithub.
- `run_venv.sh` recreates `.venv`, installs `requirements.txt`, and then
  installs the project with `pip install -e "${REPO_ROOT}"` without optional
  extras.
- `autocommit/utils/pr_utils.py` imports PyGithub only when the detected
  provider is GitHub. If the library is absent, it raises a clear setup error.

Consequently, the package's optional dependency boundary works as designed,
but the standard contributor bootstrap does not provision the GitHub
integration needed when the local auto-PR configuration is enabled.

## Proposed Architecture

Add one active requirement under a clearly labeled GitHub integration section
in `requirements.txt`:

```text
# GitHub PR integration for development
PyGithub>=2.0,<3.0
```

No `run_venv.sh` edit is necessary because its existing requirements install
will consume the new entry. No `pyproject.toml` edit is proposed: keeping
PyGithub in an optional extra preserves the approved auto-PR dependency model
for package consumers while allowing this repository's fuller development
environment to install it by default.

This is a development dependency-manifest change only. It does not alter when
auto-PR runs, provider detection, token handling, CLI behavior, configuration,
or the errors raised by installations that omit the optional integration.

## Scope

In scope:

- Add `PyGithub>=2.0,<3.0` to `requirements.txt`.
- Verify that installing the manifest makes `github` importable.
- Verify that the requirement range remains synchronized with the
  `pyproject.toml` `github` extra.
- Run the existing test suite.

Out of scope:

- Editing `run_venv.sh`; it already installs `requirements.txt`.
- Editing `pyproject.toml` or changing PyGithub's optional status for package
  consumers.
- Adding `python-gitlab` to the contributor requirements.
- Changing source code, tests of runtime behavior, CLI flags, or configuration.
- Changing README install guidance; package consumers still install the
  provider-specific optional extra exactly as documented.

## API, CLI, And Config Changes

- Public API: none
- CLI: none
- Config: none
- Prompt/provider behavior: none
- Package dependency contract: unchanged; PyGithub remains optional in
  `pyproject.toml`
- Repository development environment: PyGithub is installed by default through
  `requirements.txt` and therefore by `run_venv.sh`

## Files Expected To Change

- `requirements.txt`: add `PyGithub>=2.0,<3.0` for the repository development
  environment.

No source, test, script, README, `pyproject.toml`, or baseline-spec file is
expected to change.

## Test Plan

- `python -m pip install -r requirements.txt`: verify the development manifest
  resolves and installs successfully in the active or an isolated environment.
- `python -c "from github import Github; print(Github.__module__)"`: verify the
  installed import used by `autocommit/utils/pr_utils.py` is available.
- A focused manifest check: verify `requirements.txt` and the `github` optional
  extra both specify `PyGithub>=2.0,<3.0`, with no duplicate active requirement.
- `python -m pytest`: verify the complete existing suite remains green.
- `git diff --check`: verify the manifest and SpecRepo artifacts contain no
  whitespace errors.

## Risks And Mitigations

- Risk: The PyGithub range could drift between the development manifest and
  package metadata.
  Mitigation: Use the identical `>=2.0,<3.0` range and include a focused
  verification check comparing both declarations.
- Risk: Contributors who never use GitHub PR creation install an additional
  dependency and its transitive packages.
  Mitigation: Limit the broader installation to this repository's development
  manifest. Keep the published package dependency optional.
- Risk: Adding PyGithub to `requirements.txt` could be misunderstood as making
  it mandatory for all package users.
  Mitigation: Explicitly leave `[project].dependencies` and optional extras
  unchanged and document the audience distinction in this proposal.
- Risk: A full `run_venv.sh` verification recreates the developer's active
  virtual environment.
  Mitigation: Verify the same install command in an isolated environment when
  preserving the current `.venv` matters; the script itself is unchanged.

## Baseline Spec Updates

- Product spec: unchanged
- Architecture spec: unchanged
- Quality spec: unchanged

The baseline specs describe product behavior, runtime/package architecture,
and verification expectations. This proposal changes only the repository's
development dependency manifest and does not revise any approved user-visible
capability, module boundary, public API, CLI/config contract, provider logic,
Git behavior, or test strategy.

## Approval Request

Approve this proposal before implementation begins.
