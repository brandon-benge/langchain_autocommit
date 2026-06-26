# Architecture Spec

## Overview

LangChain AutoCommit is a small Python package organized around three layers:

1. Public API and orchestration in `autocommit/core.py`.
2. Provider, Git, and keychain adapters in `autocommit/utils/`.
3. LangChain prompt and JSON parsing in `autocommit/chains/commit_chain.py`.

The package default configuration lives in `autocommit/params.yaml` and is
loaded by `autocommit/config.py`. The root `params.yaml` is a development
reference copy and should not be treated as the runtime source of truth unless a
future approved proposal changes that contract.

## Module Responsibilities

| Module | Responsibility |
| --- | --- |
| `autocommit/__init__.py` | Defines the package public API exports. |
| `autocommit/core.py` | Coordinates config loading, Git inspection, LLM generation, fallback commit body creation, and commit application. |
| `autocommit/config.py` | Loads bundled YAML config and deep-merges caller overrides without mutating the base config. |
| `autocommit/cli.py` | Parses CLI flags, translates them into config overrides and core API calls, prompts before committing unless skipped. |
| `autocommit/chains/commit_chain.py` | Builds the LangChain prompt pipeline and parses model output as JSON. |
| `autocommit/utils/git_utils.py` | Wraps Git subprocess calls and provides path-based commit type, scope, and ticket helpers. |
| `autocommit/utils/llm_provider.py` | Resolves primary OpenAI-compatible model access and local Ollama fallback. |
| `autocommit/utils/keychain.py` | Reads and writes API keys through the local keyring backend. |

## Commit Message Generation Flow

1. `generate_commit_message` resolves the working directory and effective
   config.
2. It validates that the working directory is inside a Git repository.
3. It optionally stages all changes based on explicit arguments or config.
4. It reads changed files and staged diff summary.
5. It returns an empty `CommitMessage("", "")` when there is no meaningful
   staged diff.
6. It resolves commit type, scope, branch ticket, diff truncation, and prompt
   inputs.
7. It builds the primary LLM through `resolve_llm` and invokes the LangChain
   commit chain.
8. If primary invocation fails and the primary provider was used, it retries
   with the fallback Ollama model.
9. If model output is missing or not a dict, it returns a deterministic fallback
   subject and body based on changed files.
10. It truncates the subject to the configured maximum and appends committer
    metadata when provided.

## Commit Application Flow

`apply_commit` validates that the message has a subject, runs `git commit` with
the generated subject and body, then optionally pushes.

`generate_and_commit` composes generation and application. It derives signoff,
amend, and push behavior from config unless explicit arguments are provided.

## LLM Provider Contract

The primary provider is OpenAI-compatible and configured by
`llm.primary.base_url`, `model`, `temperature`, `max_tokens`, and `timeout`.

Authentication must use exactly one of:

- `llm.primary.env_var`
- `llm.primary.keychain`

Configuring both is an error. Missing credentials cause a fallback to Ollama.

The fallback provider uses `llm.fallback.base_url`, `model`, `temperature`, and
`max_tokens`.

## Configuration Contract

`load_config(overrides=None)` loads `autocommit/params.yaml`. If overrides are
provided, it deep-merges nested dictionaries and replaces scalar or non-dict
values.

Feature work that adds config keys must update:

- `autocommit/params.yaml`
- README documentation when user-facing
- `specrepo/specs/architecture.md`
- Tests for default behavior and override behavior

## CLI Contract

The CLI entry point is `autocommit = "autocommit.cli:main"`.

CLI flags should remain thin adapters over core APIs. Business behavior belongs
in `autocommit/core.py` or lower-level utility modules unless an approved
proposal creates a new boundary.

## Extension Rules

- Keep the public API backward compatible unless a proposal explicitly approves
  a breaking change.
- Keep LLM provider decisions behind `autocommit/utils/llm_provider.py`.
- Keep Git subprocess behavior behind `autocommit/utils/git_utils.py`.
- Keep prompt and parsing changes in `autocommit/chains/commit_chain.py`.
- Add tests for every new public flag, config key, fallback path, or Git side
  effect.
