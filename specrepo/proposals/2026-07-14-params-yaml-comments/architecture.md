# Architecture Proposal: Inline documentation comments in params.yaml

Status: awaiting_approval
Date: 2026-07-14
Request: `specrepo/requests/2026-07-14-params-yaml-comments.md`

## Summary

Add a concise inline YAML comment (`#`) on the same line as every
leaf-level configuration key in `autocommit/params.yaml` describing the
key's purpose, accepted values, and default. No key names, values, or
structure change. No code or test changes.

## Current Architecture

The bundled `autocommit/params.yaml` contains 22 configuration keys
across four sections (`llm`, `git`, `paths` plus `project_name` and
`python_version`). Only one key (`env_var`) has an inline comment:

```yaml
env_var: "OPENCODE_API_KEY"    # Alternative: read API key from env var instead of keychain
```

The file is the shipped default and serves as both the runtime config
source (loaded by `autocommit/config.py`) and the primary documentation
users see when they open the project or copy a config for customization.

## Proposed Architecture

Each leaf-level key gets a single-line `#` comment explaining its
purpose. The comment is placed on the same line as the key-value pair
(separated by two spaces, then `#`, then one space, then the comment).

The existing `env_var` comment is retained and re-styled to match.

Purely a documentation change — no behavior, parsing, or structure is
affected.

### Comment style

```
key: value  # <purpose and accepted values>
```

- **Booleans:** State what `true` enables vs `false` disables.
  - `autostage_all: true  # Auto-stage all unstaged files before commit`
- **Strings:** State the expected format and default where relevant.
  - `base_url: "https://..."  # Base URL for the OpenAI-compatible API`
- **Numbers:** State the unit and what the value controls.
  - `max_tokens: 512  # Max tokens in the LLM response`
  - `max_subject_length: 100  # Max characters for commit subject line`
- **Regex:** State what it matches against.
  - `ticket_regex: '[A-Z]{2,}-\\d+'  # Regex to extract ticket ID from branch name`

### Comment content per key

Below is the complete set of comments proposed for each key:

```
# Top-level
project_name: "LangChain AutoCommit"  # Display name for logs and metadata
python_version: "3.10"                # Minimum supported Python version

# llm.primary
base_url: "https://opencode.ai/zen/go/v1"  # Base URL for the primary LLM API
model: "deepseek-v4-flash"                  # Model identifier for the primary LLM
temperature: 0.2                            # LLM sampling temperature (0.0–1.0)
max_tokens: 512                             # Max tokens in the LLM response
timeout: 60                                 # Request timeout in seconds
# keychain:                                 # (disabled) Uncomment to use macOS Keychain
#   service: "langchain_autocommit"
#   key: "opencode_api_key"
env_var: "OPENCODE_API_KEY"                 # Env var name for API key (alternative to keychain)

# llm.fallback
base_url: "http://localhost:11434"   # Base URL for the fallback Ollama API
model: "qwen3:8b"                     # Model identifier for the fallback LLM
temperature: 0.2                      # LLM sampling temperature (0.0–1.0)
max_tokens: 4096                      # Max tokens in the fallback LLM response

# git
autostage_all: true      # Auto-stage all unstaged files before generating commit
signoff: true            # Add Signed-off-by trailer to the commit
push_after_commit: true  # Run git push after successful commit
allow_amend: false       # Allow amending the previous commit instead of creating a new one
conventional: true       # Enforce conventional commit format (type(scope): subject)
default_type: "chore"    # Fallback commit type when type cannot be inferred
scope_from_folder: true  # Infer commit scope from the current working directory name
max_subject_length: 100  # Max characters for the commit subject line
max_diff_chars: 8000     # Max characters of staged diff sent to the LLM
max_changed_files: 20    # Max changed files to include in the LLM context
include_diff_patch: true # Include the full diff patch in the LLM prompt
ticket_regex: '[A-Z]{2,}-\d+'  # Regex pattern to extract ticket ID from branch name

# git.quality
max_retries: 2       # Max quality-check retries when the draft fails validation
min_body_lines: 3    # Min body lines required for the quality check to pass
check_boilerplate: true  # Reject boilerplate or generic commit bodies

# paths
logs_dir: "logs"  # Directory for log output (relative to project root)
temp_dir: "tmp"   # Directory for temporary files (relative to project root)
```

Note: The `git.push_set_upstream` key proposed in the companion
auto-push-upstream proposal would also get a comment when it is added.

### What does NOT change

- No key names, values, or structural changes.
- No YAML indentation or formatting changes beyond adding comments.
- No modifications to `autocommit/config.py`, `core.py`, `cli.py`, or
  any test file.
- No changes to any baseline spec (comments have no architectural
  significance).

## Scope

In scope:

- Inline YAML comments on every leaf-level key in `autocommit/params.yaml`.

Out of scope:

- Any behavior, structure, or value changes.
- Comments on non-leaf keys (`llm:`, `git:`, `paths:`, `primary:`,
  `fallback:`, `quality:`).
- README or external documentation updates (the file is self-documenting).
- Adding a comment block header for sections.

## API, CLI, And Config Changes

- **Public API:** none.
- **CLI:** none.
- **Config:** inline comments added to `autocommit/params.yaml`; no key,
  value, or structure change.
- **Prompt/provider behavior:** none.

## Files Expected To Change

| File | Change |
|---|---|
| `autocommit/params.yaml` | Inline YAML comments added to every leaf-level key. |

No other files change.

## Test Plan

No new tests needed. Comments are invisible to the YAML parser. Run
existing tests to confirm no regression:

```bash
pytest
```

Additionally, validate the file parses correctly:

```bash
python -c "import yaml; yaml.safe_load(open('autocommit/params.yaml'))"
```

## Risks And Mitigations

- **Risk: Long inline comments could cause horizontal scrolling in some editors.**
  **Mitigation:** Comments are kept concise (one line per key). The longest
  comment is ~75 characters which fits within a standard 80–120 character line
  width with the key-value prefix.

- **Risk: Comments may drift out of sync if a key's behavior changes later.**
  **Mitigation:** This is a general documentation-maintenance concern, not
  specific to this change. The architecture spec requires that feature work
  adding config keys updates `params.yaml`; the same discipline should apply
  to comments.

## Baseline Spec Updates

- **Product spec:** unchanged.
- **Architecture spec:** unchanged — the configuration contract does not change.
- **Quality spec:** unchanged.

## Approval Request

Approve this proposal before implementation begins.
