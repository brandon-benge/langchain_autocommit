# Feature Request: Relocate opencode config

Status: requested
Date: 2026-06-26
Requester: user

## Summary

The reusable opencode configuration bundle has been copied from the repository
root to `$HOME/.config/opencode`. The repository should stop carrying the
root-level `opencode-config/` directory and should update active references so
they point to the new external configuration location or describe it
generically.

## Problem

The repository currently contains `opencode-config/`, and active SpecRepo
documentation says reusable opencode mechanics live there. After the bundle is
moved to `$HOME/.config/opencode`, those references become stale and the old
directory becomes duplicate state.

## Desired Behavior

The repository should retain only repo-specific project and SpecRepo state.
Reusable opencode configuration should live outside the repository at
`$HOME/.config/opencode`, and active documentation/templates should not direct
agents or humans to use the removed root-level directory.

## Acceptance Criteria

- Active repository docs and templates no longer reference `opencode-config/`
  as an in-repository directory.
- Active references to reusable opencode mechanics identify
  `$HOME/.config/opencode` or a generic external opencode configuration
  location.
- The root-level `opencode-config/` directory is removed from the repository.
- Historical request, proposal, approval, and implementation-review records are
  preserved unless they are active guidance that would misdirect future work.
- Verification records the remaining `opencode-config` references and explains
  any preserved historical references.

## Constraints

- Preserve the LangChain AutoCommit public API, CLI, runtime config, provider
  behavior, and Git behavior.
- Do not require network access or external service calls.
- Do not modify the already copied `$HOME/.config/opencode` content from this
  repository task.

## Non-Goals

- Redesigning opencode agent profiles or permissions.
- Changing LangChain AutoCommit product behavior.
- Changing the SpecRepo state machine beyond the location of reusable opencode
  mechanics.

## Impacted Areas

- Public API: no
- CLI: no
- Config: yes
- LLM prompt/provider: no
- Git behavior: no
- Tests/docs: yes

## Notes

User context: `opencode-config` has already been copied to
`$HOME/.config/opencode`, and the repository copy should be removed after stale
references are fixed.
