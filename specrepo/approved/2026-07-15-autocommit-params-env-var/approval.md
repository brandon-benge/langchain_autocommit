# Approval Record: Recover AUTOCOMMIT_PARAMS config-path resolution

Status: approved
Date: 2026-07-15
Approver: user (explicit recovery-and-merge authorization via @architecture-approver)
Request: `specrepo/requests/2026-07-15-autocommit-params-env-var.md`
Approved Proposal: `specrepo/proposals/2026-07-15-autocommit-params-env-var/architecture.md`

## Decision

Approved

## Approved Scope

- Resolve the runtime base YAML path in `autocommit/config.py` using this
  priority: explicit Python `config_path` or CLI `--config-file`, then a
  non-empty `AUTOCOMMIT_PARAMS`, then bundled `autocommit/params.yaml`.
- Keep `DEFAULT_CONFIG` initialized directly from the bundled file so package
  imports are deterministic and independent of `AUTOCOMMIT_PARAMS`.
- Preserve the existing replacement-base semantics for custom YAML files and
  deep-merge in-memory or CLI-derived overrides on top of the selected file.
- Add isolated config and CLI tests for environment selection, explicit-path
  precedence, bundled fallback, arbitrary filenames, errors, override merging,
  and stable import-time defaults.
- Update README configuration documentation and the `--config-file` flag
  description with the resolution order and an `AUTOCOMMIT_PARAMS` example.
- Retain the proposal's product and architecture baseline-spec updates.

## Conditions

- Environment lookup occurs only when `config_path is None`; an explicit path
  must remain authoritative even when `AUTOCOMMIT_PARAMS` is invalid.
- An unset or empty `AUTOCOMMIT_PARAMS` must fall back to the bundled file.
- `DEFAULT_CONFIG` must not call the environment-aware no-argument
  `load_config()` path during import.
- Verification must include the full current suite with
  `AUTOCOMMIT_PARAMS` unset and with the developer's ambient variable set;
  bundled-default tests must isolate their environment assumptions.
- Preserve all current auto-PR configuration and behavior. Do not edit
  `autocommit/params.yaml`, CLI/core signatures, providers, or Git behavior.
- Recover only the approved feature from commit `db6884b`; do not cherry-pick
  its SpecRepo artifacts wholesale and do not restore the deleted branch's
  later cleanup commit.
- Preserve the unrelated uncommitted deletion of the root `params.yaml`.

## Notes

The user explicitly requested in this turn that the feature be recovered and
merged to `main`, which authorizes this approval record and subsequent
implementation within the scope above. The old implementation commit is
recovery evidence only: its `DEFAULT_CONFIG = load_config()` behavior is not
approved because ambient configuration could otherwise make package import
fail before an explicit `--config-file` is processed.
