# Approval Record: Include PyGithub In Development Requirements

Status: approved
Date: 2026-07-15
Approver: user (explicit requirements.txt authorization via @architecture-approver)
Request: `specrepo/requests/2026-07-15-pygithub-development-requirement.md`
Approved Proposal: `specrepo/proposals/2026-07-15-pygithub-development-requirement/architecture.md`

## Decision

Approved

## Approved Scope

- Add exactly one active `PyGithub>=2.0,<3.0` requirement to
  `requirements.txt` for the repository development environment.
- Rely on the existing `run_venv.sh` `pip install -r requirements.txt` step to
  provision PyGithub in newly recreated development environments.
- Verify that the `github` module is importable after installing the manifest,
  that the version range matches the existing `github` optional extra, and
  that the full test suite remains green.

## Conditions

- Keep `[project].dependencies` and all optional extras in `pyproject.toml`
  unchanged; PyGithub must remain optional for published-package consumers.
- Do not edit `run_venv.sh`, source code, tests, README documentation, runtime
  configuration, provider behavior, CLI behavior, or baseline specs as part of
  this change.
- Do not add `python-gitlab` or any other provider dependency to
  `requirements.txt`.
- Preserve the exact supported range `PyGithub>=2.0,<3.0` and do not add a
  duplicate active requirement.
- Run installation verification in an isolated environment if recreating the
  active `.venv` would disrupt the user's current environment.

## Notes

`requirements.txt` and `pyproject.toml` serve different audiences in this
repository. Installing PyGithub through the development manifest is consistent
with keeping the provider integration optional in the published package. The
user explicitly authorized adding PyGithub to `requirements.txt`; that
authorization is recorded here so implementation may proceed through the
remaining SpecRepo gates.
