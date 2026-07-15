# Feature Request: Include PyGithub In Development Requirements

Status: requested
Date: 2026-07-15
Requester: brandonbenge

## Summary

Add `PyGithub>=2.0,<3.0` to `requirements.txt` so the repository's standard
`run_venv.sh` bootstrap installs the GitHub integration used by automatic pull
request creation and auto-merge.

## Problem

The project declares PyGithub only in the `github` optional extra in
`pyproject.toml`. The development bootstrap installs `requirements.txt` and
then the project in editable mode without extras, so a freshly recreated
`.venv` does not contain PyGithub. When a contributor's configuration enables
GitHub auto-PR behavior, `autocommit` can successfully commit and push but then
fails during PR creation with an instruction to install PyGithub manually.

## Desired Behavior

- `requirements.txt` includes PyGithub using the same supported range already
  declared by the `github` optional extra: `PyGithub>=2.0,<3.0`.
- Running `run_venv.sh` installs PyGithub through its existing
  `pip install -r requirements.txt` step, so the recreated development
  environment can use GitHub auto-PR and auto-merge without an additional
  manual install.
- PyGithub remains an optional package dependency in `pyproject.toml`; normal
  package consumers who do not select the `github` or `auto-pr` extra are not
  required to install it.

## Acceptance Criteria

- `requirements.txt` contains exactly one active PyGithub requirement with the
  range `>=2.0,<3.0`.
- Installing `requirements.txt` makes the `github` Python module importable.
- `run_venv.sh` needs no manual follow-up install before GitHub PR creation can
  use PyGithub.
- The `github` and `auto-pr` optional extras in `pyproject.toml` remain
  unchanged, preserving package-install behavior for end users.
- The existing test suite continues to pass.

## Constraints

- Keep the version range synchronized with `pyproject.toml`.
- Do not promote PyGithub into `[project].dependencies`; this request changes
  the repository development environment, not the package's core runtime
  dependency contract.
- Do not add `python-gitlab` to `requirements.txt`; the reported failure and
  requested workflow use GitHub.
- Do not change auto-PR, auto-merge, CLI, configuration, or provider behavior.

## Non-Goals

- Changing optional-extra names or contents.
- Installing every supported PR provider in the development bootstrap.
- Changing `run_venv.sh` beyond relying on its existing requirements install.
- Changing runtime error handling for missing provider libraries.

## Impacted Areas

- Public API: no
- CLI: no
- Config: no
- LLM prompt/provider: no
- Git behavior: no
- Tests/docs: yes — dependency-install verification; no user-facing behavior
  documentation change is required

## Notes

`run_venv.sh` currently runs `pip install -r requirements.txt` before
`pip install -e "${REPO_ROOT}"`. Adding the requirement to the manifest is
therefore sufficient to make it available in every environment recreated by
that script.
