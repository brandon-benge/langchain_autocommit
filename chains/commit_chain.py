# Uses LangChain primitives only to generate a conventional commit message from git diff and context.
from typing import Dict
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableMap
try:
    from langchain_community.chat_models import ChatOllama
except Exception:
    from langchain_community.llms import Ollama as ChatOllama  # type: ignore

DEFAULT_PROMPT = PromptTemplate.from_template(
    """You are a senior engineer generating a **conventional commit**.
Follow the rules strictly:
- Subject line <= {max_subject_length} chars.
- Format: <type>(<scope>): <subject>
- Use imperative mood; no trailing period.
- If ticket is present, prefix subject with "[{ticket}] " (without quotes).
- Provide a short body explaining WHY, not just WHAT. Wrap at ~72 chars.
- If multiple files changed, reference them concisely (by module or folder).

Inputs:
- type: {type}
- scope: {scope}
- ticket: {ticket}
- changed_files: {changed_files}
- diff_summary:
{diff_summary}

Now produce:
1) subject (one line)
2) body (2-6 lines)

Return exactly this JSON:
{{
  "subject": "<subject>",
  "body": "<body>"
}}
"""
)

def build_chain(base_url: str, model: str, temperature: float, max_tokens: int):
    llm = ChatOllama(
        base_url=base_url,
        model=model,
        temperature=temperature,
        num_predict=max_tokens,
    )
    chain = (
        RunnableMap({
            "type": lambda x: x.get("type"),
            "scope": lambda x: x.get("scope"),
            "ticket": lambda x: x.get("ticket") or "",
            "changed_files": lambda x: ", ".join(x.get("changed_files", [])[:20]),
            "diff_summary": lambda x: x.get("diff_summary")[:4000],
            "max_subject_length": lambda x: x.get("max_subject_length", 72),
        })
        | DEFAULT_PROMPT
        | llm
    )
    return chain
