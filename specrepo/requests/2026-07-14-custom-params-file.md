# Feature Request: Custom params.yaml file path

Status: requested
Date: 2026-07-14
Requester: user

## Summary

Add a mechanism (CLI flag and/or Python API parameter) that lets a user point to
an arbitrary YAML file and use it as the full configuration source instead of the
bundled `autocommit/params.yaml`. Existing per-key overrides (`config_overrides`)
continue to apply on top of the custom file.

## Problem

The bundled `autocommit/params.yaml` is always the base configuration. Callers
who want a different base — for example, a project-specific config checked into
a repository, an environment-specific config for CI versus local development, or
a shared team config — have no way to replace the bundled defaults. They can
only pass individual key overrides through `load_config(overrides=...)` or CLI
flags, which is brittle and does not scale to large config changes.

## Desired Behavior

- A caller can specify a path to a custom YAML file (e.g. via a CLI flag or a
  new parameter in the Python API).
- When a custom file path is given, the tool loads that file as the base config
  instead of the bundled `autocommit/params.yaml`.
- Any existing `config_overrides` dict mechanism (or CLI-equivalent override
  flags) still deep-merges on top of the custom-file config, with overrides
  taking precedence.
- When no custom file path is given, behavior is identical to today (bundled
  `params.yaml` is loaded as before).
- If the specified file does not exist or contains invalid YAML, the tool raises
  a clear, actionable error before any generation or commit attempt.

## Acceptance Criteria

1. A user can pass `--config-file /path/to/custom.yaml` (or similar) to the CLI
   and all configuration values are read from that file instead of the bundled
   `params.yaml`.
2. A user can call `load_config(config_path="/path/to/custom.yaml")` (or
   similar) from the Python API and get a config dict that was loaded from the
   custom file, not from the bundled default.
3. When both a custom file and explicit `config_overrides` are provided, the
   overrides correctly override individual keys from the custom file (deep-merge
   behavior).
4. Specifying a non-existent file produces a `FileNotFoundError` (or a clear
   custom error message).
5. Specifying a file with malformed YAML produces a clear YAML parse error.
6. Existing callers that do not use a custom file see zero change in behavior
   (backward compatible).

## Constraints

- The custom file must be a valid YAML file with the same top-level schema as
  the bundled `params.yaml` (`llm`, `git`, `paths`, `project_name`,
  `python_version`).
- The feature must be opt-in; the default must remain the bundled
  `autocommit/params.yaml`.
- The mechanism must work for both CLI users and Python API consumers.
- Error messages for missing or invalid files must be specific enough to
  diagnose without reading source code.

## Non-Goals

- Support for non-YAML config formats (JSON, TOML, INI, etc.).
- Loading or merging multiple config files.
- Partial config files that deep-merge with the bundled defaults (the custom
  file replaces the entire bundled base).
- Hot-reloading or watching the custom file for changes.
- A CLI flag to write or generate a config file.

## Impacted Areas

- Public API: yes — `load_config` signature would gain a new parameter (e.g.
  `config_path`).
- CLI: yes — a new flag such as `--config-file` or `--params` is needed.
- Config: yes — the config loading pipeline changes to support a configurable
  base path.
- LLM prompt/provider: unknown
- Git behavior: no
- Tests/docs: unknown — config-loading tests and README updates will be needed.

## Notes

The current `autocommit/config.py` loads the bundled file via `_resolve_path()`.
The architecture proposal should decide the exact parameter name, the priority
order between custom file and overrides, and how the custom path is threaded
through `core.py` and `cli.py`.
