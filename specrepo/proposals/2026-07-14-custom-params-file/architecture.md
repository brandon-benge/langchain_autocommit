# Architecture Proposal: Custom params.yaml file path

Status: awaiting_approval
Date: 2026-07-14
Request: `specrepo/requests/2026-07-14-custom-params-file.md`

## Summary

Extend `load_config()` with an optional `config_path` parameter so callers can
replace the bundled `autocommit/params.yaml` with an arbitrary YAML file. Add a
`--config-file` CLI flag that maps to the new parameter. Existing
`config_overrides` continue to deep-merge on top of whichever base file is
loaded.

## Current Architecture

Configuration loading lives in `autocommit/config.py`:

- `_resolve_path()` returns the bundled `params.yaml` path (PyInstaller-aware).
- `_load_file(path)` reads and parses a YAML file.
- `deep_merge(base, overrides)` performs a recursive dict merge.
- `load_config(overrides=None)` loads the bundled file, then optionally
  deep-merges overrides. There is no way to change the base file.
- `DEFAULT_CONFIG = load_config()` is evaluated at import time.

The CLI (`cli.py`) calls `load_config(config_overrides)` and passes the
resulting dict to `generate_commit_message(config=cfg, ...)`.

The core functions (`generate_commit_message`, `generate_and_commit`) accept a
`config` dict and optional `config_overrides` dict. When `config` is `None`,
they fall back to `load_config(config_overrides)`.

## Proposed Architecture

### 1. `load_config` gains an optional `config_path` parameter

```python
def load_config(config_path: str | None = None, overrides: dict | None = None) -> dict:
```

- **`config_path=None`** — load the bundled `autocommit/params.yaml` (current
  behavior, fully backward compatible).
- **`config_path=<path>`** — load the specified YAML file instead of the bundled
  one.
- **`overrides`** — deep-merged on top of whichever file was loaded, same as
  today.

Error handling:
- If the file does not exist, `open()` raises `FileNotFoundError` with the
  absolute path in the message.
- If the file is invalid YAML, `yaml.safe_load()` raises `yaml.YAMLError`. The
  error message includes the file path and the parse error detail.
- No explicit schema validation is performed; the caller is responsible for
  providing a file whose top-level keys match the expected structure (`llm`,
  `git`, `paths`, `project_name`, `python_version`).

`DEFAULT_CONFIG = load_config()` remains unchanged — it loads the bundled file
at import time.

### 2. CLI gains `--config-file` flag

A new flag `--config-file <path>` is added to the argument parser in
`cli.py`. The value is passed to `load_config` as `config_path`:

```python
cfg = load_config(config_path=args.config_file, overrides=config_overrides)
```

The `--config-file` flag does not interact with any other flag. If both
`--config-file` and individual override flags (e.g. `--model`, `--temperature`)
are given, the overrides are deep-merged on top of the custom file, with
individual flags winning.

### 3. Core functions propagate `config_path` (optional)

`generate_commit_message` and `generate_and_commit` gain an optional
`config_path` parameter:

```python
def generate_commit_message(
    *,
    config: dict | None = None,
    config_path: str | None = None,
    config_overrides: dict | None = None,
    ...
) -> CommitMessage:
```

Logic:

```python
if config is None:
    cfg = load_config(config_path, config_overrides)
else:
    cfg = config
    if config_overrides:
        cfg = deep_merge(cfg, config_overrides)
```

When `config_path` is provided and `config` is also provided, `config` takes
precedence (already-resolved dict wins). This avoids ambiguity.

`generate_and_commit` mirrors the same pattern.

### 4. Backward compatibility

- `load_config(overrides=...)` still works — no callers need updating.
- `generate_commit_message(config=cfg, config_overrides=...)` still works.
- `DEFAULT_CONFIG` is unchanged.
- No existing test breaks.

## Scope

In scope:

- New `config_path` parameter on `load_config`, `generate_commit_message`, and
  `generate_and_commit`.
- New `--config-file` CLI flag.
- Error handling for missing/malformed custom files.
- Updates to the architecture spec's "Configuration Contract" section.

Out of scope:

- Multi-file config merging.
- Non-YAML config formats.
- Hot-reloading config.
- Schema validation of the custom file.
- A CLI flag to generate or dump a config template.
- Updating the root `params.yaml` (development reference copy).

## API, CLI, And Config Changes

- **Public API:**
  - `load_config` signature changes from
    `load_config(overrides: dict | None = None)` to
    `load_config(config_path: str | None = None, overrides: dict | None = None)`.
  - `generate_commit_message` and `generate_and_commit` gain an optional
    `config_path: str | None = None` parameter, added before
    `config_overrides` in the keyword-only list.
  - These are backward-compatible additions; existing callers passing
    keyword arguments do not break.

- **CLI:**
  - New flag `--config-file <path>`.
  - `--show-config` output reflects the custom file content (when used).

- **Config:** The loading pipeline is extended to accept an explicit path.
  No new config keys are added to `params.yaml`.

- **Prompt/provider behavior:** Unchanged.

## Files Expected To Change

| File | Change |
|---|---|
| `autocommit/config.py` | `load_config()` signature and logic; `_load_file()` may gain a helper for error wrapping. |
| `autocommit/core.py` | `generate_commit_message()` and `generate_and_commit()` gain `config_path` parameter; the "config is None" branch passes it to `load_config`. |
| `autocommit/cli.py` | New `--config-file` argument; `load_config` call passes its value. |
| `specrepo/specs/architecture.md` | Update "Configuration Contract" section to describe the new parameter. |
| `tests/` | New or updated tests for custom-file loading, error cases, and CLI flag. |

## Test Plan

| Test target | Behavior verified |
|---|---|
| `tests/test_config.py` (or config-focused file) | `load_config(config_path=...)` loads from the given path. |
| `tests/test_config.py` | `load_config(config_path=bad_path)` raises `FileNotFoundError`. |
| `tests/test_config.py` | `load_config(config_path=bad_yaml)` raises YAML parse error. |
| `tests/test_config.py` | `load_config(config_path=path, overrides=dict)` deep-merges on top of the custom file. |
| `tests/test_config.py` | `load_config()` with no arguments still loads the bundled file (backward compatible). |
| `tests/test_autocommit.py` | `--config-file <path>` CLI flag produces config from the custom file. |
| `tests/test_core.py` | `generate_commit_message(config_path=path, ...)` loads and uses custom config. |

## Risks And Mitigations

- **Risk: Custom file has an incompatible schema.** The tool accesses config
  keys like `llm.primary.base_url` and `git.quality.max_retries`. If a custom
  file omits required keys, the tool may raise `KeyError` or get `None` where it
  expects a value.
  **Mitigation:** The error message from a `KeyError` or `AttributeError` is
  usually enough to diagnose, and the bundled `params.yaml` serves as the
  documented contract. Schema validation is explicitly out of scope for now and
  could be added in a follow-up if users find this confusing.

- **Risk: `--config-file` path resolution confusion (relative vs absolute).**
  Users may pass a relative path that resolves differently than expected.
  **Mitigation:** The error message for a missing file includes the resolved
  absolute path. The CLI help text for the flag should say "Path to a custom
  YAML config file (absolute or relative to cwd)."

- **Risk: `DEFAULT_CONFIG` diverges from the custom-file config.** If a call
  site uses `DEFAULT_CONFIG` directly instead of loading the custom file,
  behavior would be inconsistent.
  **Mitigation:** `DEFAULT_CONFIG` is documented in the architecture spec as
  "the bundled default at import time." Adding `config_path` does not change
  this contract. Call sites that use `DEFAULT_CONFIG` (e.g. the public API
  exports) should continue to work as before. No existing call site uses
  `DEFAULT_CONFIG` in a way that would conflict.

## Baseline Spec Updates

- **Product spec:** unchanged — the capability is an extension of the existing
  "Configure LLM and Git behavior through bundled defaults plus deep-merge
  overrides" line.
- **Architecture spec:** changed — the "Configuration Contract" section must
  describe the new `config_path` parameter and `--config-file` flag.
- **Quality spec:** unchanged.

## Approval Request

Approve this proposal before implementation begins.
