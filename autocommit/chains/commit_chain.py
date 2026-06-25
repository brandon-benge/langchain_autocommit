from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableMap

DEFAULT_PROMPT = PromptTemplate.from_template(
    """You are a senior engineer generating a **detailed, comprehensive conventional commit message**.
Follow the rules strictly:
- Subject line <= {max_subject_length} chars.
- Format: <type>(<scope>): <subject>
- Use imperative mood; no trailing period.
- If ticket is present, prefix subject with "[{ticket}] " (without quotes).
- Provide a DETAILED body explaining:
  * WHY these changes were made (motivation, context, problem being solved)
  * WHAT specifically changed (key modifications, new features, fixes)
  * HOW the changes work (implementation details, approach taken)
  * Any important side effects, dependencies, or breaking changes
- Body should be comprehensive: 3-15 lines minimum
- Wrap body lines at ~80 chars for readability
- If multiple files changed, explain changes by module/component
- Include technical details that would help reviewers understand the changes
- Reference specific functions, classes, or modules that were modified

Inputs (primary — from git diff):
- type: {type}
- scope: {scope}
- ticket: {ticket}
- changed_files: {changed_files}
- diff_summary:
{diff_summary}

User-provided context (secondary — describes intent):
{user_context}

Instructions:
- The git diff above is the primary source of truth for what changed.
- If user context is provided, use it to understand motivation and intent,
  but verify it against the actual diff.
- If no user context is provided, ignore this section.

Now produce:
1) subject (one concise line that summarizes the key change)
2) body (comprehensive explanation, 5-15 lines with rich technical detail)

Return exactly this JSON:
{{
  "subject": "<subject>",
  "body": "<body>"
}}
"""
)


def build_chain(llm):
    chain = (
        RunnableMap({
            "type": lambda x: x.get("type"),
            "scope": lambda x: x.get("scope"),
            "ticket": lambda x: x.get("ticket") or "",
            "changed_files": lambda x: ", ".join(x.get("changed_files", [])[:20]),
            "diff_summary": lambda x: x.get("diff_summary")[:8000],
            "max_subject_length": lambda x: x.get("max_subject_length", 72),
            "user_context": lambda x: x.get("user_context", ""),
        })
        | DEFAULT_PROMPT
        | llm
    )
    return chain
