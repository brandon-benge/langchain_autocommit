# Architecture Spec

## Overview

LangChain AutoCommit is a small Python package organized around three layers:

1. Public API and orchestration in `autocommit/core.py`.
2. Provider, Git, and keychain adapters in `autocommit/utils/`.
3. LangChain prompt and JSON parsing in `autocommit/chains/commit_chain.py`.

The package default configuration lives in `autocommit/params.yaml` and is
loaded by `autocommit/config.py`. This is the single source of truth for
runtime defaults.

## Module Responsibilities

| Module | Responsibility |
| --- | --- |
| `autocommit/__init__.py` | Defines the package public API exports. |
| `autocommit/core.py` | Coordinates config loading, Git inspection, LLM generation, fallback commit body creation, and commit application. |
| `autocommit/config.py` | Resolves explicit, environment-selected, or bundled YAML config and deep-merges caller overrides without mutating the base config. |
| `autocommit/cli.py` | Parses CLI flags, translates them into config overrides and core API calls, prompts before committing unless skipped. |
| `autocommit/chains/commit_chain.py` | Builds the LangGraph `StateGraph` with three specialized agents (diff analyzer, message writer, quality checker), parallel diff analysis, and quality-loop routing. Exports `build_graph(llm, fallback_llm, config)`. |
| `autocommit/utils/git_utils.py` | Wraps Git subprocess calls and provides path-based commit type, scope, and ticket helpers. |
| `autocommit/utils/llm_provider.py` | Resolves primary OpenAI-compatible model access and local Ollama fallback. |
| `autocommit/utils/keychain.py` | Reads and writes API keys through the local keyring backend. |
| `autocommit/utils/pr_utils.py` | PR creation with provider detection (GitHub via PyGithub, GitLab via python-gitlab). |
| `autocommit/utils/pr_token.py` | PR API token resolution via environment variable or macOS Keychain. |

## Commit Message Generation Flow

1. `generate_commit_message` resolves the working directory and effective
   config.
2. It validates that the working directory is inside a Git repository.
3. It optionally stages all changes based on explicit arguments or config.
4. It reads changed files and staged diff summary.
5. It returns an empty `CommitMessage("", "")` when there is no meaningful
   staged diff.
6. It resolves commit type (from file paths), scope (from folder), branch
   ticket, diff truncation, and conventional-mode flag.
7. It builds the primary and fallback LLMs through `resolve_llm` and
   `build_fallback_llm`, then constructs a compiled LangGraph `StateGraph`
   via `build_graph(llm, fallback_llm, config)`.
8. It invokes the graph with an initial `GraphState` dict containing the raw
   diff, changed files, heuristic type/scope/ticket, LLM instances, and
   quality-loop bookkeeping.
9. The graph executes three nodes in sequence:
   - **analyze_diff** — runs `analyze_type` and `analyze_scope` LLM sub-tasks
     concurrently. Each receives the full (truncated) diff with a focused
     prompt. Results are gathered into `state.diff_analysis`.
   - **write_message** — consumes the structured analysis plus the raw diff
     and produces a draft `CommitMessage`-shaped dict.
   - **check_quality** — runs deterministic (rule-based) checks on the draft.
     If checks fail and the retry budget (`git.quality.max_retries`, default 2)
     is not exhausted, the graph routes back to `write_message` with a
     critique. Otherwise it routes to output.
10. Each LLM agent node tries the primary provider first; on failure it retries
    with the fallback Ollama model. If both fail, the node records an error.
11. If the output is missing or empty, `generate_commit_message` returns a
    deterministic fallback subject and body based on changed files.
12. It truncates the subject to the configured maximum and appends committer
    metadata when provided.

## Commit Application Flow

`apply_commit` validates that the message has a subject, runs `git commit` with
the generated subject and body, then optionally pushes.

When pushing (`push_after=True`), the function accepts a
`push_set_upstream` parameter (default `True`). If the current branch has
no upstream tracking branch and `push_set_upstream` is `True`, the push
automatically sets the tracking reference (`git push --set-upstream origin
<branch>`) before pushing. If `push_set_upstream` is `False` and the
branch lacks an upstream, the push fails with an error.

When `git.auto_pr.enabled` is `true`, `apply_commit` optionally creates a pull
request after a successful push. It detects the hosting provider (GitHub /
GitLab) from the ``origin`` remote URL, resolves an API token via env-var or
macOS Keychain, and uses the appropriate Python library (``PyGithub`` /
``python-gitlab``) to create the PR. If the current branch matches
``git.auto_pr.target_branch``, the PR creation is skipped. The PR title and
body default to the commit message and can be overridden via keyword arguments.
The PR URL is returned from ``apply_commit`` (``str | None``).

`generate_and_commit` composes generation and application. It derives signoff,
amend, push, push-set-upstream, and auto-PR behavior from config unless
explicit arguments are provided. The `git.push_set_upstream` config key
defaults to `true` in the bundled `params.yaml`.

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

`load_config(config_path=None, overrides=None)` resolves the base YAML path in
this priority order:

1. An explicit `config_path`, supplied by the Python API or `--config-file`.
2. A non-empty `AUTOCOMMIT_PARAMS` environment variable when `config_path` is
   `None`.
3. Bundled `autocommit/params.yaml` when neither higher-priority source selects
   a file.

A custom file replaces the bundled base; it is not implicitly merged with the
bundled YAML. If overrides are provided, they are deep-merged on top of the
selected base file (nested dicts are merged recursively; scalar and non-dict
values are replaced). Missing files and malformed YAML selected through the
environment propagate the same errors as an explicit custom path.

The exported `DEFAULT_CONFIG` is always initialized directly from the bundled
file. It is deterministic and does not read `AUTOCOMMIT_PARAMS` at import time;
runtime `load_config()` calls perform environment-aware selection. This keeps
package import independent of ambient configuration and ensures an explicit
`--config-file` can override an invalid environment value.

The `--config-file <path>` CLI flag maps to the `config_path` parameter.

The following `git` keys control commit-and-push behavior:

| Key | Default | Purpose |
| --- | --- | --- |
| `git.push_after_commit` | `true` | Run `git push` after a successful commit. |
| `git.push_set_upstream` | `true` | When pushing and the branch has no upstream, automatically set the upstream tracking reference. Ignored when `push_after_commit` is `false`. |
| `git.signoff` | `true` | Add a `Signed-off-by` trailer to the commit. |
| `git.allow_amend` | `false` | Allow amending the previous commit instead of creating a new one. |
| `git.auto_pr.enabled` | `false` | Enable automatic PR creation after a successful commit and push. |
| `git.auto_pr.target_branch` | `"main"` | Target branch for the auto-created pull request. |
| `git.auto_pr.token_env_var` | `"GITHUB_TOKEN"` | Environment variable name containing the PR API token. |

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
