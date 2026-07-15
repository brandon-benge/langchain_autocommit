# Architecture Proposal: Recover AUTOCOMMIT_PARAMS config-path resolution

Status: awaiting_approval
Date: 2026-07-15
Request: `specrepo/requests/2026-07-15-autocommit-params-env-var.md`

## Summary

Resolve runtime YAML configuration paths centrally in
`autocommit/config.py` with the priority `config_path` >
`AUTOCOMMIT_PARAMS` > bundled `autocommit/params.yaml`. The existing CLI
already passes `--config-file` as `config_path`, so its explicit value wins
without parser or orchestration changes. Keep the exported `DEFAULT_CONFIG`
bound directly to the bundled file so ambient environment state cannot make
package import fail or prevent a valid explicit `--config-file` from being
processed.

This recovers the intent and focused test coverage from commit `db6884b`, while
adapting it to current `main`, adding the README documentation required by the
quality spec, and excluding the deleted branch's unrelated cleanup commit.

## Current Architecture

- `autocommit/config.py` owns `_resolve_path()`, `_load_file()`, `deep_merge()`,
  `load_config(config_path=None, overrides=None)`, and the public
  `DEFAULT_CONFIG` value.
- `load_config()` currently chooses an explicit truthy `config_path` or falls
  directly back to `_resolve_path()`, which finds the bundled file (including
  the existing frozen-application path handling).
- `autocommit/cli.py` parses `--config-file` and calls
  `load_config(config_path=args.config_file, overrides=config_overrides)`.
- `autocommit/core.py` passes its optional `config_path` into `load_config()`
  when callers do not provide an already-resolved config dictionary.
- Custom files replace the bundled base; `overrides` are deep-merged on top of
  the selected base file.
- `DEFAULT_CONFIG = load_config()` is evaluated during module import and today
  always represents the bundled file because no environment fallback exists.
- `tests/test_config.py` covers bundled and explicit path selection, missing
  files, malformed YAML, and deep merges. `tests/test_autocommit.py` confirms
  that `--config-file` reaches `load_config()`.
- Current `main` also includes auto-PR configuration and behavior. This change
  does not touch or reinterpret that configuration.

The prior commit `db6884b` inserted the environment lookup in `load_config()`
and added config tests. It did not update README documentation, and allowing
`DEFAULT_CONFIG = load_config()` to consume the environment at import time can
make an invalid ambient path fail before an explicit CLI argument is parsed.

## Proposed Architecture

### Runtime path resolution

`load_config()` remains the single runtime resolution boundary. When its
`config_path` argument is `None`, it reads `AUTOCOMMIT_PARAMS`; a non-empty
value becomes the base config path. If neither source provides a usable path,
it calls `_resolve_path()` for the bundled file.

The resulting precedence is:

1. Explicit `config_path`, supplied directly or by `--config-file`.
2. Non-empty `AUTOCOMMIT_PARAMS`, only when `config_path is None`.
3. Bundled `autocommit/params.yaml` from `_resolve_path()`.

After loading the selected file through the existing `_load_file()` helper,
the existing recursive `overrides` merge runs unchanged. Relative paths keep
the current `open()` behavior and resolve from the process working directory.
Missing or malformed environment-selected files propagate the same exceptions
as explicit paths; there is no silent fallback after a user selected a file.

### Stable import-time defaults

Initialize `DEFAULT_CONFIG` explicitly from `_resolve_path()` rather than
through environment-aware default resolution. `DEFAULT_CONFIG` therefore
continues to mean bundled defaults, remains deterministic across environments,
and cannot cause package import to fail merely because `AUTOCOMMIT_PARAMS` is
invalid. Runtime calls to `load_config()` still honor the environment.

This distinction also guarantees that a valid explicit `--config-file` can
override a bad environment value: argument parsing and the explicit runtime
load are reached without an earlier environment-dependent import failure.

### CLI and core integration

No parser, signature, or orchestration change is needed. The CLI's existing
`config_path=args.config_file` call and the core API's existing propagation
already converge on `load_config()`. The config layer supplies the new fallback
only when those explicit values are `None`.

### Documentation

Update README config documentation and the `--config-file` flag description to
state the three-tier resolution order and show how to export
`AUTOCOMMIT_PARAMS`. Clarify that a selected custom file replaces the bundled
base before dictionary/CLI overrides are applied.

## Scope

In scope:

- Add environment-aware runtime path selection to `load_config()`.
- Keep `DEFAULT_CONFIG` explicitly tied to the bundled config.
- Recover and adapt focused tests from `db6884b`.
- Make bundled-default tests hermetic by clearing `AUTOCOMMIT_PARAMS` where
  their premise requires an unset environment.
- Add a CLI-level precedence test proving `--config-file` wins when the
  environment is set.
- Update README and baseline product/architecture specs.

Out of scope:

- Changes to CLI argument definitions, core function signatures, auto-PR
  behavior, provider selection, Git behavior, or `autocommit/params.yaml`.
- YAML schema validation or friendlier CLI exception formatting.
- Merging environment-selected YAML with the bundled YAML.
- Restoring any unrelated deletions or SpecRepo cleanup from the old branch.
- Changing or restoring the separately deleted root `params.yaml`.

## API, CLI, And Config Changes

- Public API: `load_config()` and `DEFAULT_CONFIG` signatures/exports are
  unchanged. Calling `load_config()` without an explicit path now consults
  `AUTOCOMMIT_PARAMS`; `DEFAULT_CONFIG` remains the bundled snapshot.
- CLI: no flag changes. `--config-file` remains the explicit highest-priority
  path; without it, `AUTOCOMMIT_PARAMS` may select the file.
- Config: adds an environment-variable resolution tier but no YAML key and no
  change to `autocommit/params.yaml`.
- Prompt/provider behavior: none.

## Files Expected To Change

- `autocommit/config.py`: implement path precedence and stable bundled
  `DEFAULT_CONFIG` initialization.
- `tests/test_config.py`: cover environment selection, explicit precedence,
  fallback, errors, arbitrary filenames, overrides, and import-time default
  stability; isolate ambient environment state.
- `tests/test_autocommit.py`: verify CLI `--config-file` remains dominant when
  `AUTOCOMMIT_PARAMS` is set.
- `README.md`: document the environment variable, priority order, replacement
  semantics, and usage.
- `specrepo/specs/product.md`: record the user-facing persistent config-path
  capability.
- `specrepo/specs/architecture.md`: record the config-resolution contract and
  bundled-only `DEFAULT_CONFIG` semantics.

## Test Plan

- `tests/test_config.py`: a valid `AUTOCOMMIT_PARAMS` file is used when
  `config_path` is `None`.
- `tests/test_config.py`: an explicit `config_path` wins over a different
  environment-selected file.
- `tests/test_config.py`: an unset or empty environment variable falls back to
  bundled `autocommit/params.yaml`.
- `tests/test_config.py`: missing and malformed environment-selected files
  raise `FileNotFoundError` and `yaml.YAMLError` respectively.
- `tests/test_config.py`: environment-selected files with arbitrary filenames
  work and dictionary overrides are still merged on top.
- `tests/test_config.py`: `DEFAULT_CONFIG` remains bundled/deterministic even
  when the environment is set before importing or reloading the config module.
- `tests/test_autocommit.py`: `--config-file` is passed as the explicit path
  and wins while `AUTOCOMMIT_PARAMS` is set.
- `pytest`: the full current suite, including auto-PR tests, passes in an
  environment both with and without `AUTOCOMMIT_PARAMS` set as appropriate to
  validate isolation.

## Risks And Mitigations

- Risk: A stale shell variable unexpectedly selects a different config.
  Mitigation: The feature is opt-in, the name is specific, and README documents
  the exact resolution order and ways to override/unset it.
- Risk: A missing or invalid environment-selected file breaks invocations.
  Mitigation: Propagate the same path-specific exceptions as `--config-file`;
  do not silently hide an explicitly configured error.
- Risk: Environment-aware module initialization could block explicit CLI
  overrides or make imports nondeterministic.
  Mitigation: Pin `DEFAULT_CONFIG` directly to `_resolve_path()` and limit
  environment resolution to runtime `load_config()` calls.
- Risk: Developer shell state makes tests flaky.
  Mitigation: Tests that assume bundled defaults explicitly clear the variable,
  while feature tests use pytest's `monkeypatch` isolation.
- Risk: Recovering the old branch reintroduces obsolete or destructive files.
  Mitigation: Reimplement only the approved files and behavior on current
  `main`; use `db6884b` as evidence, not a wholesale branch merge.

## Baseline Spec Updates

- Product spec: changed — add the environment-selected config capability and
  explicit precedence.
- Architecture spec: changed — define the resolution order and stable
  `DEFAULT_CONFIG` contract.
- Quality spec: unchanged — it already requires config-focused tests,
  deterministic local tests, and README updates for user-visible behavior.
- Glossary: unchanged — the environment variable is fully defined by the
  product and architecture contracts and does not require a workflow term.

## Approval Request

Approve this proposal before implementation begins. After approval, the
implementation reviewer should confirm the stable `DEFAULT_CONFIG` design and
test isolation before any source or test edits.
