# Test Review: Recover AUTOCOMMIT_PARAMS config-path resolution

Status: pass
Date: 2026-07-15
Reviewer: @test-reviewer
Approval Record: `specrepo/approved/2026-07-15-autocommit-params-env-var/approval.md`
Implementation Review: `specrepo/implementation-reviews/2026-07-15-autocommit-params-env-var.md`

## Review Scope

Reviewed the governing SpecRepo workflow and baseline specs, the approved
request/proposal/approval/implementation review, the current implementation,
tests and README diff, and commit `db6884b` only as historical recovery
evidence.

The review independently verified:

- explicit Python/CLI path > non-empty `AUTOCOMMIT_PARAMS` > bundled config;
- replacement-base behavior and override merging;
- stable bundled `DEFAULT_CONFIG` initialization;
- missing-file and malformed-YAML errors;
- real CLI precedence with an invalid ambient path;
- relative and arbitrary environment-selected filenames;
- test hermeticity with the variable unset and set to the developer's ambient
  global config;
- unchanged auto-PR source/config behavior and passing auto-PR tests;
- implementation scope and preservation of the unrelated root `params.yaml`
  deletion.

No source, test, or README files were edited during this review.

## Implementation Assessment

`autocommit/config.py` contains the approved production change:

1. `load_config()` reads `AUTOCOMMIT_PARAMS` only when `config_path is None`.
2. A truthy explicit or environment path is loaded through the existing
   `_load_file()` boundary; otherwise `_resolve_path()` selects the bundled
   file.
3. Existing deep-merge overrides run after the selected replacement base is
   loaded.
4. `DEFAULT_CONFIG` is initialized with
   `_load_file(_resolve_path())`, not the environment-aware no-argument
   `load_config()` path.

This intentionally differs from the historical `db6884b` implementation,
whose `DEFAULT_CONFIG = load_config()` made imports environment-dependent. No
historical cleanup or unrelated SpecRepo deletion was recovered.

## Verification Evidence

### Focused suite with AUTOCOMMIT_PARAMS unset

Command:

```bash
env -u AUTOCOMMIT_PARAMS .venv/bin/pytest -q \
  tests/test_config.py tests/test_autocommit.py tests/test_master.py
```

Result: 81 tests passed in 0.30 seconds.

### Focused suite with ambient AUTOCOMMIT_PARAMS

Command:

```bash
AUTOCOMMIT_PARAMS=/Users/brandonbenge/Desktop/GitProjects/global_autocommit.yaml \
  .venv/bin/pytest -q \
  tests/test_config.py tests/test_autocommit.py tests/test_master.py
```

Result: 81 tests passed in 0.31 seconds.

### Full suite with AUTOCOMMIT_PARAMS unset

Command:

```bash
env -u AUTOCOMMIT_PARAMS .venv/bin/pytest -q
```

Result:

- 193 tests passed in 2.57 seconds.
- Aggregate statement coverage: 89%.
- `autocommit/config.py`: 96%.
- Current core, CLI, token, provider, Git, and auto-PR tests all passed.

### Full suite with ambient AUTOCOMMIT_PARAMS

Command:

```bash
AUTOCOMMIT_PARAMS=/Users/brandonbenge/Desktop/GitProjects/global_autocommit.yaml \
  .venv/bin/pytest -q
```

Result:

- 193 tests passed in 2.56 seconds.
- Aggregate statement coverage: 89%.
- Results and coverage matched the unset-environment run.

The repository-declared bare `pytest` command is not on this shell's `PATH`;
the repository virtual environment was used directly.

### Fresh-process stable import

Command shape:

```bash
AUTOCOMMIT_PARAMS=/definitely/missing/config.yaml \
  .venv/bin/python -c 'import autocommit; ...'
```

Result: package import succeeded and exported `DEFAULT_CONFIG` retained the
bundled `project_name: LangChain AutoCommit`. An invalid ambient path therefore
cannot block import or prevent later explicit CLI processing.

### Independent runtime and real CLI precedence

Using temporary YAML files in a fresh Python process:

- `load_config()` selected the environment file when no explicit path was
  supplied.
- `load_config(config_path=...)` selected the explicit file over a different
  environment file.
- The explicit Python path continued to win after the environment was changed
  to a nonexistent path.
- Real `autocommit.cli.main(["--show-config", "--config-file", ...])` returned
  0 and printed the explicit file's JSON while the environment pointed to a
  nonexistent file.
- `DEFAULT_CONFIG` remained the bundled snapshot throughout.

### Diff and scope validation

`git diff --check` passed with no whitespace errors.

The feature diff changes only the approved config, documentation, baseline,
and test areas:

- `autocommit/config.py`
- `README.md`
- `specrepo/specs/product.md`
- `specrepo/specs/architecture.md`
- `tests/test_config.py`
- `tests/test_autocommit.py`
- `tests/test_master.py`

The `tests/test_master.py` edit only clears ambient `AUTOCOMMIT_PARAMS` for
bundled-default assertions, as anticipated by the implementation review.

There is no diff in `autocommit/params.yaml`, `autocommit/cli.py`,
`autocommit/core.py`, PR token/provider modules, or packaging metadata. The
root `params.yaml` remains deleted in the working tree as an unrelated user
change and is not part of this feature's approved implementation.

## Coverage Assessment

| Approved behavior | Evidence | Assessment |
| --- | --- | --- |
| Environment path is used without an explicit path | Config test plus independent runtime probe | Covered |
| Explicit Python path wins over environment | Invalid-environment config test plus independent probe | Covered |
| Real `--config-file` wins over environment | CLI `--show-config` test plus invalid-environment independent probe | Covered |
| Unset or empty environment falls back to bundled config | Parameterized config test | Covered |
| Relative paths and arbitrary filenames work | Config test using changed working directory | Covered |
| Custom file replaces bundled base | Exact-dictionary assertions for selected files | Covered |
| Overrides deep-merge on selected environment base | Nested override test | Covered |
| Missing environment file raises `FileNotFoundError` | Focused error test | Covered |
| Malformed environment YAML raises `yaml.YAMLError` | Focused error test | Covered |
| `DEFAULT_CONFIG` is bundled and import-stable | Module-reload test plus invalid-environment fresh-process import | Covered |
| Tests are hermetic under real shell state | Focused and full suites pass both unset and ambient | Covered |
| Current auto-PR behavior remains compatible | Protected source files unchanged; complete current suite passes in both states | Covered |
| README and baseline specs describe precedence | Documentation/spec diff | Covered |

## Residual Risk

- A selected custom file is intentionally a replacement base. If it omits
  keys required by a later runtime path, that path may fail; this matches the
  existing explicit-file contract and is documented.
- Relative environment paths intentionally resolve from the process working
  directory, so changing directories can select a different file.
- Missing files and malformed YAML surface the existing raw exceptions rather
  than a friendlier CLI wrapper. This is explicitly approved and consistent
  with explicit `config_path` behavior.
- The environment is read on each no-argument runtime `load_config()` call, so
  a process that mutates `AUTOCOMMIT_PARAMS` can change subsequent runtime
  selection. `DEFAULT_CONFIG` remains stable.

These risks are non-blocking and within the approved contract.

## Recommendation

**Pass — ready to merge within the approved AUTOCOMMIT_PARAMS recovery
scope.** Precedence, stable defaults, errors, real CLI behavior, test
isolation, documentation, and auto-PR compatibility are all verified. Keep the
unrelated root `params.yaml` deletion out of the feature commit unless the user
explicitly chooses to include it.
