# Quality Spec

## Test Strategy

The default verification command is:

```bash
pytest
```

The existing test suite uses pytest with mocks for LLM, keychain, and selected
Git behavior. New tests should avoid real network calls and should not require a
running Ollama server.

## Required Coverage Areas

Feature changes must include focused tests for the affected layer:

- Public API behavior in `tests/test_core.py`.
- CLI flag parsing and delegation in `tests/test_autocommit.py`.
- Git wrapper behavior in `tests/test_git_utils.py`.
- LLM provider selection in `tests/test_llm_provider.py`.
- Config loading and deep-merge behavior in config-focused tests.
- Prompt, parser, or graph topology behavior in `tests/test_commit_chain.py`
  when model input, output, or graph structure changes.

## Compatibility Rules

- Python 3.10+ support must be preserved.
- Public exports from `autocommit/__init__.py` are stable by default.
- Existing config keys should keep their behavior unless a breaking change is
  explicitly approved.
- Tests should be deterministic and local.

## Security And Safety Rules

- Do not log API key values.
- Do not require secrets in tests.
- Avoid expanding Git side effects beyond the approved scope.
- Push behavior must remain opt-in through config or explicit caller choice.
- Any change involving shell command construction or external subprocesses
  requires tests for argument handling and failure behavior.

## Documentation Rules

User-visible behavior changes require README updates. Architecture or workflow
changes require corresponding updates under `specrepo/specs/`.
