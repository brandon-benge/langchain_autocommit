# Implementation Review: Custom params.yaml file path

Status: implementation_reviewed
Date: 2026-07-14
Reviewer: @implementation-reviewer
Approval Record: `specrepo/approved/2026-07-14-custom-params-file/approval.md`

## Approved Architecture Readback

The approved design adds an optional `config_path` parameter to the config
loading pipeline:

1. `load_config(config_path=None, overrides=None)` — if `config_path` is given,
   load that file instead of the bundled `autocommit/params.yaml`; overrides
   are still deep-merged on top.
2. CLI `--config-file <path>` — maps to the `config_path` parameter.
3. `generate_commit_message` and `generate_and_commit` gain an optional
   `config_path` parameter for callers who want lazy loading.
4. When both `config` (pre-loaded dict) and `config_path` are passed to a core
   function, `config` takes precedence.
5. Error handling: `FileNotFoundError` for missing files, `yaml.YAMLError` for
   malformed YAML — both with file path in the message.
6. Fully backward compatible — existing callers see zero change.

## Consistency Check

- Product behavior is clear: **yes**
- Architecture boundaries are clear: **yes**
- Public API impact is clear: **yes** — `load_config` signature changes;
  `generate_commit_message` and `generate_and_commit` gain a parameter
- CLI impact is clear: **yes** — new `--config-file` flag
- Config impact is clear: **yes** — loading pipeline extended; no new config
  keys
- Test plan is clear: **yes** — 7 scenarios across 3 test files

## Implementation Map

### `autocommit/config.py` (lines 29–33)

**Current:**
```python
def load_config(overrides: dict | None = None) -> dict:
    cfg = _load_file(_resolve_path())
    if overrides:
        cfg = deep_merge(cfg, overrides)
    return cfg
```

**Target:**
```python
def load_config(config_path: str | None = None, overrides: dict | None = None) -> dict:
    path = config_path if config_path is not None else _resolve_path()
    cfg = _load_file(path)
    if overrides:
        cfg = deep_merge(cfg, overrides)
    return cfg
```

`_load_file()` and `_resolve_path()` stay as-is.

---

### `autocommit/core.py` — `generate_commit_message` (lines 45–69)

**Current signature (lines 46–48):**
```python
def generate_commit_message(
    *,
    config: dict | None = None,
    config_overrides: dict | None = None,
```

**Target:** Add `config_path` after `config`, before `config_overrides`.

**Current config-loading logic (lines 63–69):**
```python
    if config is None:
        cfg = load_config(config_overrides)
    else:
        cfg = config
        if config_overrides:
            from autocommit.config import deep_merge
            cfg = deep_merge(cfg, config_overrides)
```

**Target:** Pass `config_path` through when falling back to `load_config`:
```python
    if config is None:
        cfg = load_config(config_path, config_overrides)
    else:
        cfg = config
        if config_overrides:
            from autocommit.config import deep_merge
            cfg = deep_merge(cfg, config_overrides)
```

The `config_path` parameter is silently ignored when `config` is explicitly
provided (per the approved rule).

---

### `autocommit/core.py` — `generate_and_commit` (lines 200–226)

Identical pattern to `generate_commit_message`:
- Add `config_path` parameter.
- Change `load_config(config_overrides)` to `load_config(config_path, config_overrides)`.

---

### `autocommit/cli.py` — new flag and call site (lines 161–177)

**Add argument** (after existing flags, around line 170 before `parse_args`):
```python
ap.add_argument("--config-file", type=str, default=None,
                help="Path to a custom YAML config file (absolute or relative to cwd)")
```

**Update load_config call** (line 177):
```python
cfg = load_config(config_path=args.config_file, overrides=config_overrides)
```

No other CLI code changes needed. `--show-config` already prints whatever
`load_config` returns, so it naturally reflects the custom file content.

---

### Tests

| New test location | What it verifies |
|---|---|
| `tests/test_config.py` — `test_load_config_with_config_path` | Custom file loads correctly |
| `tests/test_config.py` — `test_load_config_config_path_not_found` | `FileNotFoundError` for missing path |
| `tests/test_config.py` — `test_load_config_config_path_bad_yaml` | YAML parse error for malformed file |
| `tests/test_config.py` — `test_load_config_config_path_with_overrides` | Overrides deep-merge on top of custom file |
| `tests/test_config.py` — `test_load_config_default_still_works` | No-arg call still loads bundled file |
| `tests/test_autocommit.py` — CLI flag test | `--config-file <path>` produces config from custom file |
| `tests/test_core.py` — core API test | `generate_commit_message(config_path=path, ...)` loads and uses custom config |

---

### Spec updates already applied

- `specrepo/specs/architecture.md` — Configuration Contract section updated.

## Questions Or Blockers

**Minor edge case (not a blocker):** An empty-string `--config-file ""` or
`config_path=""` would currently try to open the current directory as a YAML
file, producing a confusing error. The implementation should treat
`config_path=""` the same as `config_path=None` (i.e., fall back to the
bundled file), OR let it naturally fail with a clear `FileNotFoundError`. The
proposal does not specify this case; the coding agent should pick one approach
and document it.

No other questions or blockers.

## Verification Plan

```bash
pytest -v
```

The existing test suite must pass unchanged. New tests (listed above) should
be added and passing.

## Review Decision

**Proceed** — the approved architecture is internally consistent, maps to
concrete file-level changes in 3 source files plus tests, and has no blocking
issues.
