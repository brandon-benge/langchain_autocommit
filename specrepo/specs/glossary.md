# Glossary

| Term | Meaning |
| --- | --- |
| Request | A feature or change request placed in `specrepo/requests/`. |
| Proposal | A draft architecture response to a request, placed in `specrepo/proposals/`. |
| Approval record | Human approval for a proposal, placed in `specrepo/approved/`. |
| Implementation review | Coding-agent review of the approved architecture before code edits. |
| Baseline spec | Current approved product, architecture, and quality documentation in `specrepo/specs/`. |
| Public API | Names exported from `autocommit/__init__.py`. |
| Primary provider | OpenAI-compatible chat model configured under `llm.primary`. |
| Fallback provider | Local Ollama chat model configured under `llm.fallback`. |
