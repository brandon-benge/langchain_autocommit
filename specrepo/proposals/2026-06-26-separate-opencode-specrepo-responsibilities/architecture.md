# Architecture Proposal: Separate opencode and SpecRepo responsibilities

Status: awaiting_approval
Date: 2026-06-26
Request: `specrepo/requests/2026-06-26-separate-opencode-specrepo-responsibilities.md`

## Summary

Make `opencode-config/` the reusable opencode bundle for SpecRepo-driven
development and keep `specrepo/` as the repository-specific source of truth.

The reusable bundle should define opencode agents, conservative permissions,
generic handoff prompts, and role behavior. It must not encode LangChain
AutoCommit package paths, Python-only verification commands, or project-specific
runtime assumptions. Agents should discover those facts from `specrepo/spec.yaml`,
`specrepo/workflow.md`, baseline specs, and the active request/proposal/approval
records.

## Current Architecture

The current repository has two overlapping workflow directories:

- `opencode-config/` contains opencode configuration files, opencode agent
  profiles, and an end-to-end feature-development guide.
- `specrepo/` contains the repo-specific SpecRepo manifest, workflow,
  baseline specs, request/proposal/approval/review directories, templates, and
  a second set of role notes under `specrepo/agents/`.

Scan findings:

- `opencode-config/README.md` describes a reusable opencode setup, but it also
  frames the bundle as "for this repository".
- `opencode-config/feature-development.md` correctly describes the reusable
  SpecRepo lifecycle, but it assumes exact `specrepo/` paths and uses `pytest`
  in examples.
- `opencode-config/opencode.yaml` hardcodes Python-oriented verification
  permissions such as `pytest*`, `.venv/bin/pytest*`, and
  `python3 -m py_compile*`.
- `opencode-config/agents/spec-reviewer.md` contains a repo-specific rule that
  forbids changes under `autocommit/`, `tests/`, or project runtime metadata.
- `opencode-config/agents/spec-coder.md` hardcodes `pytest` as the fallback
  verification command instead of reading the repo's command contract.
- `opencode-config/agents/test-reviewer.md` repeats repo-specific quality
  expectations that should come from `specrepo/specs/quality.md`.
- `specrepo/spec.yaml` already contains the repo-specific project facts:
  package name, language, source roots, test roots, default config, workflow
  directories, gates, default test command, and agent policy.
- `specrepo/specs/` already contains the LangChain AutoCommit product,
  architecture, quality, and glossary facts.
- `specrepo/agents/` duplicates reusable role instructions that are also
  represented in `opencode-config/agents/`.

## Proposed Architecture

### Directory Authority

`opencode-config/` becomes a reusable opencode workflow bundle. It may contain:

- opencode configuration syntax and agent registration.
- Generic SpecRepo role definitions for opencode agents.
- Conservative default tool and permission settings.
- Reusable workflow guidance, prompts, and examples.
- A contract that repo-specific facts must be read from `specrepo/`.

`opencode-config/` must not contain:

- Product names, package names, source roots, test roots, or runtime config
  paths for a specific repository.
- Repo-specific verification commands, language assumptions, or dependency
  commands as default behavior.
- Approval decisions, request records, architecture decisions, or implementation
  reviews.
- File write allowlists tied to a specific codebase.

`specrepo/` remains the repository-specific source of truth. It owns:

- `spec.yaml`: project metadata, source roots, test roots, default commands,
  workflow directories, and agent policy.
- `workflow.md`: this repository's accepted SpecRepo state machine and gates.
- `specs/`: approved product, architecture, quality, and terminology facts for
  this repository.
- `requests/`, `proposals/`, `approved/`, and `implementation-reviews/`:
  repo-specific decision trail and implementation gates.
- `templates/`: repo-specific artifact templates.
- Optional repo-specific agent overlays only if they encode local policy not
  already present in the reusable opencode bundle.

### Agent Fact Discovery Contract

Reusable opencode agents must read repository-specific facts before acting:

1. Read `AGENTS.md` when present.
2. Read `specrepo/spec.yaml` to discover project metadata, source roots, test
   roots, workflow directories, commands, and agent policy.
3. Read `specrepo/workflow.md` for the repository's state machine and gates.
4. Read the relevant baseline specs under `specrepo/specs/`.
5. Read the active request, proposal, approval record, implementation review,
   source files, and tests required by the current role.

Agents may refer to `specrepo/` as the conventional SpecRepo directory, but
they must not hardcode project facts that are supposed to come from the
manifest or specs.

### Role Responsibilities

| Role | Reusable responsibility in `opencode-config/` | Repo-specific authority in `specrepo/` | Must not do |
| --- | --- | --- | --- |
| Request author | Provide reusable prompt guidance for request creation. | Write request files with concrete repo behavior, acceptance criteria, constraints, and non-goals. | Approve architecture or start implementation. |
| `@spec-reviewer` | Define how an opencode agent turns a request into an architecture proposal. | Read current specs and request; write `proposals/.../architecture.md`; update baseline specs only when the proposed architecture changes approved understanding. | Edit implementation code or create approval records. |
| `@architecture-approver` | Define approval-readiness review behavior and optional approval-record writing mechanics. | Compare proposal, request, specs, and diffs; create an approval record only after explicit human approval. | Grant final human approval by itself or implement code. |
| Human approver | Reusable workflow guidance can remind humans where the gate is. | Own the final approve/revise/reject decision and approved scope. | Delegate final approval to an agent without explicit approval. |
| `@implementation-reviewer` | Define the pre-code review gate and expected review decision values. | Read approval and proposal; write the implementation review mapping approved scope to concrete repo files and verification commands. | Edit code or expand architecture. |
| `@spec-coder` | Define implementation discipline for approved SpecRepo work. | Implement only the approved repo-specific scope; run the verification plan from the approval/proposal/review or `specrepo/spec.yaml`. | Start before approval and implementation review exist; add unapproved API, CLI, config, provider, prompt, or Git behavior. |
| `@test-reviewer` | Define read-only verification review behavior. | Compare the current diff with the approved repo-specific artifacts and tests. | Edit files or treat missing verification as a pass. |
| Human merger | Reusable workflow guidance can describe final review. | Decide whether to merge the repo-specific diff and accept any residual risk. | Merge unrelated changes with approved feature work. |

### Handoff Boundaries

- A request is input only. It does not authorize implementation.
- A proposal documents architecture and expected verification. It does not
  authorize implementation until approved by a human.
- An approval record is the implementation authorization boundary.
- An implementation review is the pre-code sanity gate and may stop the work.
- Implementation must stay within the approved scope.
- Test review is read-only and may block merge readiness.
- Repo-specific verification commands come from the active SpecRepo artifacts,
  not from reusable opencode defaults.

## Scope

In scope:

- Clarify `opencode-config/` as reusable across repositories.
- Clarify `specrepo/` as repo-specific for this repository.
- Update opencode agent profiles to read project facts from SpecRepo instead
  of hardcoding LangChain AutoCommit paths or Python-only test commands.
- Remove or convert duplicate `specrepo/agents/` role notes so they are not a
  second reusable-agent authority.
- Update workflow documentation to describe role ownership and handoffs.
- Add verification scans that catch repo-specific leakage into
  `opencode-config/`.

Out of scope:

- Runtime behavior changes in `autocommit/`.
- Test behavior changes in `tests/`.
- Public Python API, CLI, LLM provider, prompt, Git behavior, or default
  runtime config changes.
- Replacing SpecRepo with another workflow system.
- Automating final human approval or merge decisions.

## API, CLI, And Config Changes

- Public API: none.
- CLI: none.
- Config: documentation and opencode configuration only. No runtime
  `autocommit/params.yaml` changes.
- Prompt/provider behavior: none.
- Git behavior: none.

## Files Expected To Change

- `opencode-config/README.md`: define the reusable bundle contract, explain
  what belongs in the bundle, and state that repo-specific facts come from
  `specrepo/`.
- `opencode-config/feature-development.md`: make examples repository-neutral,
  replace hardcoded test-command assumptions with references to
  `specrepo/spec.yaml` and the approved verification plan, and clarify role
  handoffs.
- `opencode-config/opencode.yaml`: remove repo-specific command permissions or
  mark them as local customization examples outside the reusable default.
- `opencode-config/agents/spec-reviewer.md`: remove `autocommit/`, `tests/`,
  and runtime-metadata hardcoding; instruct the agent to use `source_roots`,
  `test_roots`, and commands from `specrepo/spec.yaml`.
- `opencode-config/agents/architecture-approver.md`: keep behavior generic and
  ensure references to approval sessions are repository-neutral.
- `opencode-config/agents/implementation-reviewer.md`: keep behavior generic
  and source file mappings from the approved proposal and manifest.
- `opencode-config/agents/spec-coder.md`: replace hardcoded fallback `pytest`
  with the active verification plan or `specrepo/spec.yaml.commands.test`.
- `opencode-config/agents/test-reviewer.md`: replace repo-specific testing
  expectations with instructions to read `specrepo/specs/quality.md` and the
  approved verification artifacts.
- `specrepo/README.md`: state that this directory is repo-specific and that
  reusable opencode mechanics live in `opencode-config/`.
- `specrepo/workflow.md`: optionally clarify that opencode agents are reusable
  executors while this file is the repo-specific state machine authority.
- `specrepo/agents/`: remove the duplicate generic role notes or replace them
  with a short repo-specific overlay README if local policy is still needed.

## Test Plan

- `rg -n "LangChain|AutoCommit|autocommit|params.yaml|pytest|python3 -m py_compile|\\.venv/bin/pytest" opencode-config`
  should return no unintended repo-specific leakage after implementation.
- `rg -n "source_roots|test_roots|commands.test|specrepo/spec.yaml" opencode-config`
  should show that reusable agents point to the manifest for repo-specific
  facts.
- `rg -n "reusable|repo-specific|opencode-config|specrepo" specrepo/README.md specrepo/workflow.md`
  should confirm the documented authority split.
- Review `git diff -- opencode-config specrepo` to verify there are no changes
  under `autocommit/`, `tests/`, or runtime metadata.
- No `pytest` run is required for this documentation/config separation unless
  implementation unexpectedly changes runtime code.

## Risks And Mitigations

- Risk: Generic opencode profiles become too vague to guide agents well.
  Mitigation: Keep the reusable role duties concrete, but require project facts
  to be loaded from `specrepo/spec.yaml`, workflow docs, specs, and active
  artifacts.
- Risk: Removing hardcoded test-command permissions makes opencode ask for more
  approvals in some repositories.
  Mitigation: Treat repository-specific command allowlists as local
  customization outside the reusable default, and keep approved verification
  commands in SpecRepo artifacts.
- Risk: Two role authorities remain if `specrepo/agents/` and
  `opencode-config/agents/` continue to duplicate each other.
  Mitigation: Make `opencode-config/agents/` the reusable opencode role source
  and reserve `specrepo/agents/` only for repo-specific overlays or remove it.
- Risk: Baseline specs drift if workflow documentation changes are mistaken for
  runtime architecture changes.
  Mitigation: Keep LangChain AutoCommit product, runtime architecture, and
  quality specs unchanged unless a later approved proposal changes application
  behavior.

## Baseline Spec Updates

- Product spec: unchanged.
- Architecture spec: unchanged.
- Quality spec: unchanged.

The proposed change affects SpecRepo/opencode workflow documentation and
opencode configuration. It does not change LangChain AutoCommit product
behavior, runtime architecture, public API, CLI, provider behavior, Git
behavior, or runtime verification requirements.

## Approval Request

Approve this proposal before implementation begins.
