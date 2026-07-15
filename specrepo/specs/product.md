# Product Spec

## Purpose

LangChain AutoCommit helps developers generate conventional Git commit messages
from the current repository diff. It provides both a Python library API and an
optional CLI.

## Primary Users

- Developers who want fast, consistent commit messages.
- Automation scripts that need a programmatic commit-message generator.
- Local workflows that prefer a hosted OpenAI-compatible provider but can fall
  back to a local Ollama model.

## User-Facing Capabilities

- Generate a `CommitMessage(subject, body)` from staged changes.
- Optionally stage all changes before generation.
- Infer conventional commit type from changed paths.
- Infer commit scope from the current working directory.
- Extract a ticket identifier from the current branch when configured.
- Apply the generated commit with optional signoff, amend, and push behavior.
- Run through CLI flags or the Python API.
- Automatically create a pull request against a configurable target branch
  after commit and push (requires optional ``PyGithub`` or ``python-gitlab``).
- Configure LLM and Git behavior through bundled defaults, a persistent custom
  YAML path selected by `AUTOCOMMIT_PARAMS`, an explicit `--config-file` or
  Python `config_path`, and deep-merge overrides. Explicit paths take priority
  over the environment, which takes priority over the bundled file.

## Public API

The stable public API is exported by `autocommit/__init__.py`:

- `generate_commit_message`
- `apply_commit`
- `generate_and_commit`
- `CommitMessage`
- `load_config`
- `DEFAULT_CONFIG`
- `deep_merge`

Changes to these names, signatures, or return types require an approved
architecture proposal.

## Non-Goals

- It is not a general Git porcelain replacement.
- It does not manage branches, merge pull requests, close pull requests, or
  manage releases. PR creation is supported only as an optional post-push step.
- It does not guarantee LLM availability.
- It does not require network access when the fallback local model is available.
