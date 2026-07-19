# Feature Request: Apache-2.0 License And Dependency Governance

Status: requested
Date: 2026-07-16
Requester: Brandon Benge

## Summary

Establish a complete and verifiable Apache License 2.0 foundation for
LangChain AutoCommit, correct the project's dependency-license disclosures,
and introduce a maintainable process for reviewing dependency licenses over
time.

The project is not currently intended for sale, and this request does not add
a commercial distribution workflow. The selected Apache-2.0 license must,
however, remain the standard unmodified Apache License and must not include a
noncommercial or no-resale restriction. The repository, source distributions,
and wheels should consistently communicate the project's license, while
licenses belonging to dependencies, external services, and model artifacts
remain clearly distinguished from the license of this project.

## Problem

The repository currently declares Apache-2.0 in `pyproject.toml` and the
README, but it does not contain the full Apache License 2.0 text in a tracked
top-level license file. This makes the intended license less explicit to
repository users and creates uncertainty about whether built artifacts carry
the expected licensing material.

The README's dependency summary is incomplete and contains an inaccurate
abstraction around Ollama: the Ollama software and Python client have their own
license, while the configured fallback model has a separate model license.
The summary also omits resolved dependencies with weak-copyleft obligations,
including MPL-2.0 components, and optional provider integrations licensed
under LGPL-3.0-family terms.

Dependency resolution is not fully reproducible. `pyproject.toml` contains
supported version ranges, while `requirements.txt` is also used to bootstrap
development and includes test and provider dependencies without pinning the
complete transitive environment. A later installation can therefore resolve a
different dependency set with different licensing metadata or obligations.

There is no repository policy or repeatable verification step that identifies
new licenses, rejects licenses outside the project's policy, records reviewed
exceptions, or verifies that legal files are present in built distributions.
As a result, dependency changes can silently invalidate the current licensing
assessment.

## Desired Behavior

The repository should make the following facts clear and verifiable:

1. LangChain AutoCommit's own source and distributions are licensed under the
   unmodified Apache License 2.0.
2. The full Apache-2.0 license text is tracked in the repository and included
   in source and wheel distributions.
3. Project metadata uses current Python packaging conventions to identify the
   Apache-2.0 license and the legal files shipped with distributions.
4. Documentation distinguishes the project license from dependency licenses,
   model licenses, hosted-service terms, and generated-output considerations.
5. Direct runtime, optional provider, development/test, and material
   transitive dependencies have an accurate, maintainable license inventory.
6. Known MPL-2.0 and LGPL-3.0-family dependencies are treated as explicitly
   reviewed exceptions rather than being described as ordinary permissive
   dependencies.
7. The normal development setup resolves a reproducible dependency snapshot,
   while published package metadata retains appropriate supported version
   ranges and optional dependency boundaries.
8. A deterministic local verification step classifies resolved dependency
   licenses, reports unknown or ambiguous license metadata, rejects prohibited
   license categories, and verifies approved exceptions.
9. Built artifacts are checked for correct license metadata and required legal
   files before a release is considered ready.
10. Future dependency, provider, or default-model changes trigger a fresh
    license review and any necessary documentation updates.

## Acceptance Criteria

### Project license

- A tracked top-level `LICENSE` file contains the complete, unmodified Apache
  License, Version 2.0 text.
- `pyproject.toml` declares the distribution license with the SPDX identifier
  `Apache-2.0` using current supported packaging metadata.
- `pyproject.toml` explicitly identifies the legal files that must be included
  in built distributions.
- The build backend minimum version supports the selected license metadata
  format.
- Obsolete or conflicting license metadata is removed so built metadata has
  one unambiguous license expression.
- A built wheel and source distribution contain the project license file and
  report `License-Expression: Apache-2.0`, or the architecture proposal records
  an equivalent standards-compliant verification for supported tooling.
- Copyright attribution is accurate and does not imply ownership by an
  unidentified group when the repository history identifies the copyright
  holder.
- A project `NOTICE` file is added only if required attribution content is
  identified; it is not created merely as a placeholder.

### Documentation and notices

- The README states that the project is Apache-2.0 licensed and links to the
  tracked license text.
- The README does not claim that the author's current decision not to sell the
  project restricts other Apache-2.0 permissions, including commercial use and
  redistribution.
- The README summarizes the obligations relevant to ordinary use and external
  redistribution without presenting the text as legal advice.
- A tracked third-party license inventory or notices document identifies, at
  minimum:
  - direct runtime dependencies;
  - optional GitHub and GitLab provider dependencies;
  - development and test dependencies included in the maintained development
    environment;
  - reviewed transitive dependencies with material weak-copyleft obligations;
  - the default fallback model separately from Ollama software; and
  - hosted LLM/API terms as a separate concern that is not governed by the
    repository's Apache-2.0 license.
- The inventory records package names, reviewed license expressions, dependency
  roles, and authoritative source or license references in a form that can be
  maintained when versions change.
- The documentation accurately identifies the currently known reviewed
  exceptions, including `certifi`, `tqdm`, and `orjson` under MPL-2.0 terms and
  `PyGithub` / `python-gitlab` under LGPL-3.0-family terms where applicable.
- The documentation explains that these licenses do not automatically
  relicense LangChain AutoCommit, while external redistribution or modification
  of the covered components can create additional obligations.
- The documentation distinguishes installing dependencies normally from
  bundling them into a container, frozen executable, appliance, or other
  redistributed combined product.

### Dependency manifests and reproducibility

- `pyproject.toml` remains the authoritative declaration of package runtime
  dependencies, supported version ranges, and optional extras.
- `PyGithub` and `python-gitlab` remain optional package dependencies for
  GitHub and GitLab PR features; neither becomes an unconditional runtime
  dependency for ordinary package consumers.
- The repository defines an explicit, documented development dependency input
  and a fully pinned resolved snapshot, or an equivalently reproducible design
  approved in the architecture proposal.
- The pinned snapshot covers the dependency sets exercised by the standard
  development and test workflow, including the GitHub integration currently
  expected by repository tests.
- The snapshot-generation command and update procedure are documented and can
  be run from a clean environment.
- `run_venv.sh` and the development-container bootstrap install the intended
  reproducible development dependency set rather than independently resolving
  open-ended transitive versions on every setup.
- Dependency resolution succeeds on the supported Python baseline or any
  supported-version limitations are explicitly documented and tested.
- Generated dependency files are clearly marked so contributors know which
  source file to edit and which command regenerates the snapshot.

### License policy and automated review

- The repository contains a machine-readable license policy or an equivalently
  deterministic representation reviewed in the architecture proposal.
- The policy distinguishes at least:
  - approved permissive licenses;
  - explicitly reviewed weak-copyleft exceptions;
  - prohibited strong-copyleft, source-available, noncommercial, or
    field-of-use-restricted licenses; and
  - unknown, missing, custom, or ambiguous license metadata requiring manual
    review.
- AGPL, SSPL, Commons Clause, noncommercial restrictions, and unreviewed
  proprietary licenses cannot silently pass the automated policy check.
- GPL-family licenses that are not explicitly approved for a particular
  dependency cannot silently pass solely because a package classifier is
  incomplete or ambiguous.
- Reviewed MPL-2.0 and LGPL-3.0-family dependencies are allowlisted narrowly by
  normalized package identity and expected license expression rather than by a
  blanket approval of every package using those licenses.
- The check reports at least package name, resolved version, detected license
  expression or evidence, dependency role/set, and policy result.
- Missing or unparseable license metadata produces a failure that requires a
  recorded manual decision; it is not automatically treated as permissive.
- The license check is deterministic, local after dependency installation, and
  does not require credentials or calls to LLM, GitHub, GitLab, or Ollama
  services.
- The process documents how a maintainer adds, updates, or removes a reviewed
  exception and how the corresponding third-party inventory is kept aligned.

### Build and verification

- The approved verification plan includes the complete pytest suite and
  package dependency consistency checks.
- The project can build both a wheel and source distribution from a clean
  environment using the documented build process.
- Automated or scripted artifact inspection confirms the required project
  license and third-party notice files are included in both distribution
  formats.
- Artifact metadata inspection confirms the intended SPDX license expression
  and contains no conflicting legacy free-text license declaration.
- Installation from the built wheel succeeds in an isolated environment.
- The dependency-license policy passes for every dependency set approved by
  the architecture proposal, including optional provider sets that are
  supported by this repository.
- Tests and license checks do not make network calls or require secrets after
  their input artifacts and dependencies have been installed.
- Existing public API, CLI behavior, configuration semantics, Git behavior,
  LLM prompts, and provider fallback behavior remain unchanged.

### Ongoing governance

- `specrepo/specs/quality.md` defines license review as a required part of
  dependency, provider, and default-model changes.
- The quality rules require regeneration of the reproducible dependency
  snapshot and rerunning of the license-policy check when dependency inputs
  change.
- The quality rules require third-party documentation updates whenever a
  dependency's reviewed license, role, or version materially changes.
- New weak-copyleft, strong-copyleft, source-available, noncommercial, custom,
  or unknown licenses require explicit review before implementation or release.
- Model licenses and hosted-provider terms are reviewed separately from Python
  package licenses whenever the default provider or model changes.

## Constraints

- Preserve the standard Apache License 2.0 without adding noncommercial,
  no-resale, field-of-use, or other custom restrictions.
- Do not describe this project as proprietary or dual-license it as part of
  this change.
- Preserve Python 3.10+ compatibility unless the architecture proposal
  identifies a tooling constraint and receives separate approval for a
  compatibility change.
- Preserve all existing public API exports, function signatures, CLI flags,
  configuration keys, Git side effects, provider behavior, and default runtime
  behavior.
- Do not remove GitHub or GitLab PR functionality merely to avoid documenting
  LGPL obligations.
- Keep optional provider libraries replaceable and separately installed for
  package consumers.
- Do not vendor third-party source code or dependency license texts into the
  `autocommit` package unless the architecture proposal demonstrates that it is
  necessary for compliance or artifact distribution.
- Do not treat Python package metadata alone as infallible when it conflicts
  with an authoritative upstream license file; record reviewed evidence for
  ambiguous cases.
- Use authoritative upstream license texts and documentation when establishing
  the project license and reviewed dependency classifications.
- The license check must be suitable for local development and future CI use,
  but adding or changing a hosted CI service is not required by this request.
- Generated dependency snapshots must have a documented regeneration process;
  contributors must not be expected to edit transitive pins manually.
- Avoid adding runtime dependencies solely to implement development-time
  license governance.
- Follow the SpecRepo workflow: no implementation may begin until an
  architecture proposal is reviewed and a human approval record exists.

## Non-Goals

- Restricting commercial use, resale, modification, sublicensing, or
  redistribution otherwise permitted by Apache-2.0.
- Selling the project, creating paid tiers, introducing a commercial EULA, or
  designing a proprietary distribution strategy.
- Providing a legal opinion, legal warranty, or guarantee that the inventory
  replaces review by qualified counsel for a future distribution scenario.
- Relicensing third-party dependencies, Ollama software, models, hosted APIs,
  or generated outputs under Apache-2.0.
- Publishing source for dependencies that are merely installed from their
  normal upstream distributions as part of local development.
- Building a universal software-bill-of-materials or enterprise compliance
  platform.
- Adding container, frozen executable, desktop application, appliance, or
  other bundled-product distribution in this change.
- Automatically accepting every OSI-approved license; copyleft scope and
  redistribution obligations still require policy review.
- Replacing current LLM providers or the fallback model solely because they
  have separate terms or licenses.
- Changing application runtime behavior, prompts, commit generation, pull
  request creation, auto-merge behavior, or Git operations.
- Resolving trademark, patent-clearance, privacy, export-control, security
  vulnerability, or hosted-service contractual questions beyond documenting
  them as distinct review areas.

## Impacted Areas

- Public API: no
- CLI: no
- Config: no
- LLM prompt/provider: no runtime change; documentation must distinguish
  provider terms and model licensing
- Git behavior: no
- Tests/docs: yes — packaging metadata, legal files, dependency manifests,
  license-policy verification, artifact verification, README, and quality spec

## Compatibility Concerns

- Moving from legacy free-text license metadata to an SPDX license expression
  requires a sufficiently recent build backend.
- A generated pinned development snapshot may resolve differently across
  Python versions or platforms if markers and platform-specific dependencies
  are not designed explicitly.
- `requirements.txt` currently serves as a development bootstrap and includes
  `PyGithub`, while `pyproject.toml` correctly treats it as optional for package
  consumers. The new design must preserve that distinction.
- License metadata is inconsistent across some Python packages and package
  versions. The policy needs an auditable exception mechanism without broadly
  suppressing unknown licenses.
- MPL and LGPL obligations become more consequential if a future release
  bundles dependencies into a single executable or other redistributed
  product. That scenario requires a new review rather than relying solely on
  this local-development assessment.
- Adding legal files to distribution metadata changes artifact contents even
  though it does not change runtime behavior; wheel and source-distribution
  layouts must therefore be verified directly.

## Impacted Areas And Candidate Artifacts

The architecture proposal should evaluate, but is not pre-authorized to change
beyond the approved scope, the following likely artifacts:

- `LICENSE`: complete Apache License 2.0 text.
- `pyproject.toml`: modern license metadata, build-backend support, dependency
  inputs, and development tooling declarations.
- `requirements.txt` and/or generated requirement snapshots: reproducible
  development dependencies.
- `run_venv.sh`: installation of the approved development snapshot.
- `.devcontainer/devcontainer.json`: alignment with the approved bootstrap.
- `README.md`: accurate project, dependency, model, and service licensing
  guidance.
- `THIRD_PARTY_NOTICES.md` or an approved equivalent: reviewed inventory and
  redistribution guidance.
- `scripts/`: local dependency-license and artifact-verification tooling.
- `tests/`: focused deterministic tests for policy and artifact behavior where
  appropriate.
- `specrepo/specs/quality.md`: ongoing dependency-license review gate.
- Other baseline specs only if the architecture proposal changes an approved
  product or architecture contract.

## Verification Evidence Expected

The proposal must define exact commands and expected evidence for at least:

- parsing and validating project metadata;
- regenerating or validating the pinned dependency snapshot;
- installing the approved development dependency sets;
- running `python -m pip check` or an approved equivalent;
- running the complete `pytest` suite;
- running the dependency-license policy check for core, test, GitHub, and
  GitLab sets as applicable;
- building a wheel and source distribution;
- inspecting both artifacts for legal files and license metadata; and
- installing and importing the built wheel in an isolated environment.

If any verification cannot be deterministic across all supported platforms,
the proposal must identify the limitation, choose an authoritative test
environment, and preserve a documented manual review path.

## Notes

- The current repository metadata declares `Apache-2.0`, but no top-level
  `LICENSE` or `NOTICE` file is tracked.
- The current README lists only a small subset of dependencies and conflates
  the Ollama software license with the separately licensed fallback model.
- The dependency review performed on 2026-07-16 found a predominantly
  permissive installed environment with reviewed MPL-2.0 components and
  optional LGPL-3.0-family provider libraries. That review is a point-in-time
  input, not a substitute for reproducible resolution and ongoing checks.
- Apache-2.0 permits commercial use and redistribution. The requester's choice
  not to sell the project is a project intention, not an additional license
  restriction.
- This request authorizes architecture review only. It does not authorize
  edits to project code, dependency manifests, packaging metadata, legal
  files, or documentation until the required proposal and human approval
  record exist.
