# Implementation Review: Include PyGithub In Development Requirements

Status: implementation_reviewed
Date: 2026-07-15
Reviewer: implementation-reviewer
Approval Record: `specrepo/approved/2026-07-15-pygithub-development-requirement/approval.md`

## Approved Architecture Readback

The repository development environment should install the GitHub client used
by the existing automatic pull-request integration. Add exactly one active
`PyGithub>=2.0,<3.0` line to `requirements.txt`, using the same supported range
already declared by the `github` optional extra in `pyproject.toml`.

This changes only the repository bootstrap manifest. `run_venv.sh` already
installs `requirements.txt` before installing the project in editable mode, so
it will consume the new requirement without a script change. Published-package
consumers retain the existing optional dependency boundary: PyGithub must not
be added to `[project].dependencies`, and the optional extras remain unchanged.
There are no runtime, public API, CLI, configuration, provider, Git, or
user-facing documentation changes.

## Consistency Check

- Product behavior is clear: yes; this provisions an already-supported
  integration in contributor environments and does not change runtime behavior
- Architecture boundaries are clear: yes; the development manifest changes,
  while package metadata and the bootstrap script retain their current roles
- Public API impact is clear: not applicable; no exports or signatures change
- CLI impact is clear: not applicable; no flags or CLI behavior change
- Config impact is clear: not applicable; no config key or default changes
- Test plan is clear: yes; verify the exact manifest declaration, isolated
  installation and import, the full suite, and whitespace integrity

The current repository matches the proposal's premises. `requirements.txt`
does not declare PyGithub, `pyproject.toml` declares
`PyGithub>=2.0,<3.0` in the `github` optional extra, and `run_venv.sh` already
runs `pip install -r requirements.txt`. The current `.venv` does not have the
`PyGithub` distribution installed and importing `github` raises
`ModuleNotFoundError`, directly confirming the development-environment gap.

## Implementation Map

- `requirements.txt`: add one active `PyGithub>=2.0,<3.0` entry under a clear
  GitHub PR integration heading. Preserve all existing requirements and avoid
  adding `python-gitlab` or any other provider dependency.
- `pyproject.toml`: no change; use its existing
  `PyGithub>=2.0,<3.0` declaration as the synchronization reference and keep
  `[project].dependencies` and all optional extras byte-for-byte unchanged.
- `run_venv.sh`: no change; its existing requirements installation step will
  provision PyGithub in newly recreated development environments.
- Source files, tests, `README.md`, runtime configuration, and baseline specs:
  no change; the approval excludes behavior and documentation changes.

The implementation-review artifact itself is the only SpecRepo file created
by this gate. The separate auto-PR work on the current branch is not part of
this implementation and must not be modified.

## Questions Or Blockers

None.

The change is additive, bounded to one dependency-manifest line, and preserves
the optional published-package dependency contract. An isolated virtual
environment can verify installation without recreating or modifying the
user's active `.venv`.

## Verification Plan

First, statically verify that the development manifest contains exactly one
active declaration with the approved range and that the package metadata still
contains the matching optional declaration:

```bash
python3 - <<'PY'
from pathlib import Path
import tomllib

expected = "PyGithub>=2.0,<3.0"
requirements = [
    line.strip()
    for line in Path("requirements.txt").read_text().splitlines()
    if line.strip() and not line.lstrip().startswith("#")
]
assert requirements.count(expected) == 1, requirements

with Path("pyproject.toml").open("rb") as handle:
    project = tomllib.load(handle)["project"]
assert expected not in project["dependencies"]
assert project["optional-dependencies"]["github"].count(expected) == 1
PY
```

Then reproduce the relevant `run_venv.sh` installation flow in an isolated
temporary environment, verify the import used by `autocommit/utils/pr_utils.py`,
and run the complete existing suite there:

```bash
tmp_dir="$(mktemp -d)"
python3 -m venv "${tmp_dir}/venv"
"${tmp_dir}/venv/bin/python" -m pip install --upgrade pip
"${tmp_dir}/venv/bin/python" -m pip install -r requirements.txt
"${tmp_dir}/venv/bin/python" -m pip install -e .
"${tmp_dir}/venv/bin/python" -c "from github import Github; print(Github.__module__)"
"${tmp_dir}/venv/bin/python" -m pytest
rm -rf "${tmp_dir}"
```

Finally, verify patch hygiene and scope:

```bash
git diff --check
git diff -- requirements.txt pyproject.toml run_venv.sh
```

The final diff must show the approved `requirements.txt` addition and no
changes to `pyproject.toml` or `run_venv.sh`. If isolated installation or the
full suite cannot run, record the exact failure rather than treating the gate
as passed.

## Review Decision

Proceed
