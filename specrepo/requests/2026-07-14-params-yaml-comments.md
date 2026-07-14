# Feature Request: Inline documentation comments in params.yaml

Status: requested
Date: 2026-07-14
Requester: user

## Summary

Add a descriptive YAML comment next to every configuration key in the
bundled `autocommit/params.yaml` explaining what the key controls, its
expected values, and any relevant defaults or side effects.

## Problem

The bundled `autocommit/params.yaml` contains 22 config keys across four
sections (`llm`, `git`, `paths`, plus top-level `project_name` and
`python_version`), but only one key (`env_var`) currently has an inline
comment. Users who open the file to understand or change a setting must
either guess the meaning from the key name, read the source code, or
refer to external documentation. This increases the learning curve and
raises the risk of misconfiguration.

Because `params.yaml` is the shipped default that users are encouraged
to copy or override (via `--config-file` or the `config_path`
parameter), the file itself should be self-documenting.

## Desired Behavior

- Every key-value pair in `params.yaml` has an inline `#` comment on
  the same line (or the line immediately above if the line is too long)
  describing the key's purpose, accepted values, and any relevant
  defaults.
- The comments are written for a developer who is reading the file to
  understand or change behavior, not for a contributor editing the
  source code.
- Already-commented keys (currently `env_var`) are updated to match the
  same comment style if needed.

## Acceptance Criteria

1. Every leaf-level key in `params.yaml` has an explanatory comment.
2. Comments are precise about the effect of `true` vs `false` for
   boolean keys, the unit for numeric keys (e.g., seconds, tokens,
   characters), and any format expectations for string keys (e.g.,
   regex patterns, URL format).
3. Section headings (`llm:`, `git:`, `paths:`) may optionally have a
   preceding comment, but this is not required.
4. The file remains valid YAML after all comments are added (comments
   have no effect on parsing).
5. All existing default values remain unchanged — this is a
   documentation-only change.

## Constraints

- Comments must not break YAML parsing.
- Comments must be concise (ideally one line per key).
- The file must remain readable and not excessively cluttered.
- Comments should not repeat information that is already obvious from
  the key name (e.g., `# The project name` for `project_name` is
  unnecessary).

## Non-Goals

- No behavior changes to any config key.
- No restructuring or renaming of existing keys.
- No changes to the config loading or validation logic.
- No generation of config documentation outside the file itself.

## Impacted Areas

- Public API: no
- CLI: no
- Config: yes — the bundled `params.yaml` file gains inline comments,
  but no key names, values, or structure change.
- LLM prompt/provider: no
- Git behavior: no
- Tests/docs: unknown — no test changes needed (comments are invisible
  to the parser), but README documentation references to specific keys
  could be cross-checked for consistency.

## Notes

The current `params.yaml` has 22 keys without comments:

**Top level:** `project_name`, `python_version`

**`llm.primary`:** `base_url`, `model`, `temperature`, `max_tokens`,
`timeout`, (commented-out `keychain` block), `env_var`

**`llm.fallback`:** `base_url`, `model`, `temperature`, `max_tokens`

**`git`:** `autostage_all`, `signoff`, `push_after_commit`, `allow_amend`,
`conventional`, `default_type`, `scope_from_folder`, `max_subject_length`,
`max_diff_chars`, `max_changed_files`, `include_diff_patch`, `ticket_regex`

**`git.quality`:** `max_retries`, `min_body_lines`, `check_boilerplate`

**`paths`:** `logs_dir`, `temp_dir`

Only `env_var` currently has an inline comment (`# Alternative: read API
key from env var instead of keychain`).
