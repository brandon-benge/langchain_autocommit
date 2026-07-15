# Implementation Review: Recover AUTOCOMMIT_PARAMS config-path resolution

Status: implementation_reviewed
Date: 2026-07-15
Reviewer: implementation-reviewer
Approval Record: `specrepo/approved/2026-07-15-autocommit-params-env-var/approval.md`

## Approved Architecture Readback

Runtime configuration selection remains centralized in
`autocommit/config.py`. `load_config()` must use this order:

1. An explicit `config_path`, including the value supplied by CLI
   `--config-file`.
2. A non-empty `AUTOCOMMIT_PARAMS` value, but only when `config_path is None`.
3. The bundled `autocommit/params.yaml` resolved by `_resolve_path()`.

The selected custom YAML file replaces the bundled base. Existing dictionary
and CLI-derived overrides are then deep-merged on top. Relative paths retain
the existing process-working-directory behavior, and missing or malformed
environment-selected files propagate the same `FileNotFoundError` or
`yaml.YAMLError` as explicit paths.

`DEFAULT_CONFIG` has a deliberately different contract from a runtime
no-argument `load_config()` call: it is a stable snapshot of the bundled file
and must not consult `AUTOCOMMIT_PARAMS` during module import. The concrete
implementation should bind it directly with
`DEFAULT_CONFIG = _load_file(_resolve_path())`. This preserves import
determinism and permits a valid explicit CLI path to override even an invalid
ambient environment path.

No CLI argument, core function, or public API signature changes are needed.
The existing CLI already passes `args.config_file` as `config_path`, and the
existing core paths already converge on `load_config()`.

## Consistency Check

- Product behavior is clear: yes
- Architecture boundaries are clear: yes
- Public API impact is clear: yes; exports and signatures stay stable while
  no-argument runtime resolution gains the approved environment tier
- CLI impact is clear: yes; behavior changes only through the existing config
  boundary and `--config-file` remains authoritative
- Config impact is clear: yes; this adds path selection, not a YAML key or a
  merge with the bundled file
- Test plan is clear: yes, with the existing bundled-default assertions in
  `tests/test_master.py` included in the isolation work

The approved request, proposal, approval, updated product/architecture
baselines, current source, and recovery evidence in `db6884b` agree on the
user-visible precedence. The old commit is useful only for its two-line
runtime lookup and focused tests. Its `DEFAULT_CONFIG = load_config()` line is
not suitable for recovery because it would make import depend on ambient
state. No later cleanup commit or old SpecRepo artifact should be restored.

## Implementation Map

- `autocommit/config.py`: when `config_path is None`, read
  `AUTOCOMMIT_PARAMS`; keep the existing truthy-path fallback so an empty
  environment value uses `_resolve_path()`; initialize `DEFAULT_CONFIG`
  directly with `_load_file(_resolve_path())`.
- `tests/test_config.py`: recover and adapt environment-path tests for valid
  selection, an explicit path winning over a different or invalid environment
  value, unset and empty fallback, arbitrary and relative filenames, missing
  files, malformed YAML, override merging, and stable `DEFAULT_CONFIG` under
  module reload. Existing tests whose premise is the bundled file must delete
  `AUTOCOMMIT_PARAMS` with `monkeypatch`.
- `tests/test_master.py`: locally isolate its four bundled-default
  `load_config()` assertions from the developer's shell by clearing
  `AUTOCOMMIT_PARAMS` for those tests. This file was not named in the proposal's
  initial expected-file list, but inspection shows it is necessary to satisfy
  the approved full-suite ambient-environment condition. It is a focused test
  isolation adjustment, not an architecture expansion.
- `tests/test_autocommit.py`: add a CLI-level precedence test with
  `AUTOCOMMIT_PARAMS` set and `--config-file` supplied. Prefer the existing
  `--show-config` early-exit path with temporary YAML files so the test proves
  the explicit file is actually loaded without invoking LLM or Git behavior.
- `README.md`: update only configuration-facing documentation: state the
  explicit-path > environment > bundled order, show an
  `AUTOCOMMIT_PARAMS` export example, explain that a custom file replaces the
  bundled base before overrides, and revise the `--config-file` description to
  say that it overrides the environment as well as the bundled default.
- `specrepo/specs/product.md`: preserve the already-prepared approved
  persistent-config-path and precedence update.
- `specrepo/specs/architecture.md`: preserve the already-prepared approved
  resolution-order, replacement-base, error, and stable-`DEFAULT_CONFIG`
  contract.
- `autocommit/params.yaml`: no change; it remains the bundled runtime source
  of truth and its current auto-PR settings must be preserved.
- `autocommit/cli.py`, `autocommit/core.py`, and `autocommit/__init__.py`: no
  change; current forwarding and exports already support the approved design.
- Root `params.yaml`: preserve its unrelated uncommitted deletion exactly as
  found.

## Questions Or Blockers

None.

The additional `tests/test_master.py` mapping is required by evidence in the
current suite and is covered by the approval's explicit test-isolation
condition. It does not change production design or broaden user-visible scope.
The current shell has `AUTOCOMMIT_PARAMS` set, which makes the two-environment
verification requirement directly testable after implementation.

## Verification Plan

Focused verification:

```bash
pytest tests/test_config.py tests/test_autocommit.py tests/test_master.py -v
```

Full verification without the environment tier active:

```bash
env -u AUTOCOMMIT_PARAMS pytest
```

Full verification with the developer's current ambient
`AUTOCOMMIT_PARAMS` left set:

```bash
pytest
```

The two full runs must both pass. Verification should also confirm that the
diff contains no change to `autocommit/params.yaml`, production CLI/core
signatures, providers, Git behavior, or the unrelated root `params.yaml`
deletion.

## Review Decision

Proceed
