# Feature Request: Recover AUTOCOMMIT_PARAMS config-path resolution

Status: requested
Date: 2026-07-15
Requester: user

## Summary

Recover the previously implemented `AUTOCOMMIT_PARAMS` environment variable so
users can select a persistent YAML configuration file without passing a CLI
option on every invocation. An explicit `--config-file` CLI argument or
`config_path` Python argument must take precedence, while the bundled
`autocommit/params.yaml` remains the final fallback.

## Problem

The feature existed in the recoverable Git commit `db6884b`, but its branch was
deleted without merging the feature commit into the current `main`. Current
`main` therefore contains `--config-file` support but no reference to
`AUTOCOMMIT_PARAMS`. Users must either repeat `--config-file` on each invocation
or modify the package-managed bundled configuration.

## Desired Behavior

The runtime config path is resolved in this order:

1. An explicit `--config-file <path>` or Python `config_path=<path>`.
2. A non-empty `AUTOCOMMIT_PARAMS` environment variable.
3. The bundled `autocommit/params.yaml`.

The selected custom file replaces the bundled base config, just as
`--config-file` does today. Existing in-memory `overrides` and CLI-derived
overrides are then deep-merged on top of the selected file.

## Acceptance Criteria

- `AUTOCOMMIT_PARAMS=/path/to/custom.yaml autocommit ...` loads that YAML file
  when `--config-file` is absent.
- `--config-file /other/config.yaml` wins when `AUTOCOMMIT_PARAMS` is also set.
- `load_config(config_path="/other/config.yaml")` wins over the environment in
  the Python API.
- With no explicit path and no non-empty `AUTOCOMMIT_PARAMS`, the bundled
  `autocommit/params.yaml` is loaded exactly as it is today.
- Files selected through `AUTOCOMMIT_PARAMS` support arbitrary filenames and
  the same relative-path behavior as `--config-file`.
- Missing files and malformed YAML selected through the environment use the
  same `FileNotFoundError` and `yaml.YAMLError` behavior as explicit paths.
- `DEFAULT_CONFIG` remains a stable snapshot of the bundled configuration and
  does not make package import depend on an ambient environment variable.
- README documentation explains the resolution order and includes an
  `AUTOCOMMIT_PARAMS` usage example.
- Focused tests are isolated from the developer's real environment, including
  when the developer has `AUTOCOMMIT_PARAMS` set in their shell.
- The full `pytest` suite passes on the current auto-PR-enabled `main` branch.

## Constraints

- The explicit CLI/Python path must always have higher priority than the
  environment variable.
- The environment-selected file is a replacement base, not a partial merge
  with the bundled file.
- No public function signatures or existing CLI flags may change.
- Existing behavior must remain unchanged for users who do not set
  `AUTOCOMMIT_PARAMS`.
- Preserve Python 3.10+ compatibility and avoid any new dependency.
- Preserve the current auto-PR configuration and behavior.

## Non-Goals

- Multiple config files, config directories, or layered YAML-file merging.
- New config file formats or schema validation.
- Hot reloading or watching config files.
- Renaming `AUTOCOMMIT_PARAMS` or changing `--config-file` syntax.
- Restoring the later destructive SpecRepo cleanup commit from the deleted
  branch.

## Impacted Areas

- Public API: yes — `load_config()` default path resolution changes, while its
  signature remains stable.
- CLI: yes — no parser change, but invocations without `--config-file` can now
  resolve a path through the environment.
- Config: yes — a new path-resolution tier is added.
- LLM prompt/provider: no
- Git behavior: no
- Tests/docs: yes — config tests and README documentation are required.

## Notes

Commit `db6884b` is useful recovery evidence, but it predates the current
auto-PR work and omitted README documentation. Implementation should recover
only the intended config behavior and tests, adapted to current `main`; it
must not restore unrelated branch cleanup.
