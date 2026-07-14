# Approval Record: Custom params.yaml file path

Status: approved
Date: 2026-07-14
Approver: user (via @architecture-approver)
Request: `specrepo/requests/2026-07-14-custom-params-file.md`
Approved Proposal: `specrepo/proposals/2026-07-14-custom-params-file/architecture.md`

## Decision

Approved

## Approved Scope

- New `config_path` parameter on `load_config()`, `generate_commit_message()`,
  and `generate_and_commit()`.
- New `--config-file <path>` CLI flag.
- Error handling for missing or malformed custom files (FileNotFoundError,
  YAML parse error).
- Updates to `specrepo/specs/architecture.md` (Configuration Contract section)
  — already applied.
- Tests for custom-file loading, error cases, override interaction, backward
  compatibility, CLI flag parsing, and core API integration.

## Conditions

None

## Notes

The proposal specifies that when both `config` (pre-loaded dict) and
`config_path` are passed to core functions, `config` takes precedence. The
implementation must preserve this rule.

Schema validation of the custom file is intentionally out of scope and should
be considered a separate follow-up if users find the raw KeyError diagnosis
insufficient.
