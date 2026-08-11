"""LangGraph commit-message pipeline with specialized agents and quality loop."""

from __future__ import annotations

import concurrent.futures
import warnings
from typing import Callable, NamedTuple, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

TRUNCATION_WARNING = "\n\n**Note:** The diff below was truncated. Your view may be incomplete."
FULL_DIFF_INSTRUCTIONS = (
    "The git diff above (including the actual patch content under ---PATCH---) "
    "is the primary source of truth for what changed."
)

# ---------------------------------------------------------------------------
# Agent prompts
# ---------------------------------------------------------------------------

ANALYZE_TYPE_PROMPT = PromptTemplate.from_template(
    """You are a senior engineer reviewing a git diff. Based on the diff content,
determine the conventional commit type.

Consider what the changes actually DO:
- **feat**: A new feature or enhancement for the user
- **fix**: A bug fix
- **docs**: Documentation only changes
- **style**: Changes that do not affect the meaning of the code
- **refactor**: A code change that neither fixes a bug nor adds a feature
- **perf**: A code change that improves performance
- **test**: Adding missing tests or correcting existing tests
- **chore**: Changes to the build process or auxiliary tools

Changed files: {changed_files}
Diff:
{diff_summary}
{truncated_warning}

Return exactly this JSON:
{{
  "type": "<conventional-commit-type>",
  "reasoning": "<one-sentence explanation>",
  "confidence": <0.0-1.0>
}}"""
)

ANALYZE_SCOPE_PROMPT = PromptTemplate.from_template(
    """You are a senior engineer reviewing a git diff. Based on the diff content,
determine the most appropriate scope for the commit.

Scope is the area of the codebase affected (e.g. "auth", "api", "ui", "core",
"docs", "config"). Look at file paths and diff content to identify what
component or module is primarily affected.

Changed files: {changed_files}
Diff:
{diff_summary}
{truncated_warning}

Return exactly this JSON:
{{
  "scope": "<short-scope-string-or-empty>",
  "reasoning": "<one-sentence explanation>"
}}"""
)

WRITE_MESSAGE_PROMPT = PromptTemplate.from_template(
    """You are a senior engineer generating a detailed, comprehensive conventional
commit message.

Changed files: {changed_files}
Diff:
{diff_summary}
{truncated_warning}

Analysis:
- Heuristic type (from file paths): {heuristic_type}
- Heuristic scope (from folder): {heuristic_scope}
- Ticket: {ticket}
- Content-based type analysis: {content_type_analysis}
- Content-based scope analysis: {content_scope_analysis}

User context: {user_context}
{diff_instructions}
{critique_section}

Now produce a commit message.
- Subject <= {max_subject_length} chars.
- Format: <type>(<scope>): <subject>
- Imperative mood, no trailing period.
- If ticket present, prefix subject with "[{ticket}] ".
- Body: 3-15 lines explaining WHY, WHAT, HOW.
- Wrap body at ~80 chars.

Return exactly this JSON:
{{
  "subject": "<subject>",
  "body": "<body>"
}}"""
)

# ---------------------------------------------------------------------------
# Graph state
# ---------------------------------------------------------------------------


class GraphState(TypedDict):
    """State carried through the LangGraph commit-message pipeline."""

    # Immutable inputs set before invocation
    raw_diff: str
    changed_files: list[str]
    user_context: str
    max_subject_length: int
    max_diff_chars: int
    max_changed_files: int
    diff_truncated: bool
    heuristic_type: str
    heuristic_scope: str
    ticket: str
    conventional: bool
    primary_llm: BaseChatModel
    fallback_llm: BaseChatModel | None

    # Populated by analyze_diff
    diff_analysis: dict | None

    # Populated by write_message
    draft_subject: str
    draft_body: str

    # Quality-loop bookkeeping
    retry_count: int
    critique_history: list[str]
    errors: list[str]
    quality_passed: bool




# ---------------------------------------------------------------------------
# LLM helper
# ---------------------------------------------------------------------------


class _LLMCall(NamedTuple):
    """Result of a single LLM chain call: parsed dict or a failure reason."""

    result: dict | None   # parsed dict when the call succeeded
    error: str | None     # human-readable reason when result is None


_MAX_ERROR_TEXT = 300

# Reason used when an LLM call returns without raising but produces output
# that cannot be parsed into the expected dict shape.
_NON_DICT_REASON = "returned non-dict output (unparseable)"


def _safe_error_text(error: Exception) -> str:
    """Format an exception for warnings, bounded to avoid dumping request
    bodies or credentials into output."""
    text = f"{type(error).__name__}: {error}".strip()
    if len(text) > _MAX_ERROR_TEXT:
        text = text[:_MAX_ERROR_TEXT] + "..."
    return text


def _call_llm(chain, **kwargs) -> _LLMCall:
    """Call an LLM chain and return parsed JSON plus a failure reason.

    Returns a ``_LLMCall(result, error)``: ``result`` is the parsed dict on
    success (``error`` is ``None``), or ``result`` is ``None`` with ``error``
    set to a human-readable reason on failure (exception text or an
    unparseable-output note).
    """
    try:
        result = chain.invoke(kwargs)
        if isinstance(result, dict):
            return _LLMCall(result=result, error=None)
        return _LLMCall(result=None, error=_NON_DICT_REASON)
    except Exception as e:
        return _LLMCall(result=None, error=_safe_error_text(e))


def _warn_fallback(task_label: str, reason: str, call_failed: bool = True) -> None:
    """Emit a UserWarning that the fallback LLM branch is being entered.

    ``call_failed`` selects phrasing: exception text uses "call failed",
    while an unparseable (non-exception) result reads as "produced no usable
    result".
    """
    if call_failed:
        failure = "primary LLM call failed"
    else:
        failure = "primary LLM call produced no usable result"
    warnings.warn(
        f"{task_label}: {failure} ({reason}); "
        "falling back to the fallback LLM.",
        UserWarning,
        stacklevel=2,
    )


def _call_with_fallback(
    prompt: PromptTemplate,
    llm: BaseChatModel,
    fallback_llm: BaseChatModel | None,
    *,
    task_label: str,
    on_error: Callable[[str], None] | None = None,
    **kwargs,
) -> dict | None:
    """Try primary LLM, then fallback. Returns parsed dict or None.

    Emits a ``UserWarning`` (naming the failed sub-task and including the
    primary error) when the fallback branch is entered — the primary attempt
    failed and ``fallback_llm`` is configured — regardless of whether the
    fallback attempt itself succeeds. No warning fires on primary success or
    when ``fallback_llm is None``.

    ``task_label`` identifies which agent fell back (e.g. ``"analyze_type"``).
    The optional ``on_error`` callback receives the enriched primary failure
    reason (e.g. ``"analyze_type: primary failed (ConnectionError: ...)"``)
    for ``state.errors`` bookkeeping.
    """
    parser = JsonOutputParser()
    primary = _call_llm(prompt | llm | parser, **kwargs)
    if primary.result is not None:
        return primary.result
    if fallback_llm is not None:
        reason = primary.error or "no usable parsed result"
        _warn_fallback(task_label, reason, call_failed=reason != _NON_DICT_REASON)
        if on_error is not None:
            on_error(f"{task_label}: primary failed ({reason})")
        fallback = _call_llm(prompt | fallback_llm | parser, **kwargs)
        return fallback.result
    return None


# ---------------------------------------------------------------------------
# Quality checker (deterministic, no LLM)
# ---------------------------------------------------------------------------

_BOILERPLATE_PATTERNS = [
    "update file",
    "update files",
    "fix bug",
    "fix issue",
    "fix problem",
    "minor fix",
    "minor change",
    "small fix",
    "small change",
    "various fixes",
    "various changes",
    "code cleanup",
    "clean up",
    "refactor code",
    "refactoring",
]


def _check_quality(
    subject: str,
    body: str,
    max_subject_length: int,
    conventional: bool,
    min_body_lines: int,
    check_boilerplate: bool,
) -> tuple[bool, str]:
    """Run deterministic quality checks on a draft commit message.

    Returns (passed, critique_string).
    """
    critiques: list[str] = []

    # 1. Subject must not be empty
    if not subject.strip():
        critiques.append("Subject is empty.")

    # 2. Subject length
    if len(subject) > max_subject_length:
        critiques.append(
            f"Subject is {len(subject)} chars (max {max_subject_length})."
        )

    # 3. Conventional format check (when conventional mode is on)
    if conventional and subject.strip():
        # Basic check: looks for type(scope): or type: prefix
        has_conventional_prefix = False
        for sep in (":", "!:"):
            if sep in subject:
                before_sep = subject.split(sep)[0].strip()
                if "(" in before_sep or before_sep.islower():
                    has_conventional_prefix = True
                    break
        if not has_conventional_prefix:
            critiques.append(
                "Subject does not match conventional format "
                "<type>(<scope>): <subject>."
            )

    # 4. Body must not be empty
    body_stripped = body.strip()
    if not body_stripped:
        critiques.append("Body is empty.")

    # 5. Body minimum lines
    body_lines = [l for l in body_stripped.split("\n") if l.strip()]
    if len(body_lines) < min_body_lines:
        critiques.append(
            f"Body has {len(body_lines)} non-empty line(s); "
            f"expected at least {min_body_lines}."
        )

    # 6. Boilerplate detection
    if check_boilerplate:
        body_lower = body_stripped.lower()
        subject_lower = subject.lower()
        for pattern in _BOILERPLATE_PATTERNS:
            if pattern in body_lower or pattern in subject_lower:
                critiques.append(
                    f"Boilerplate detected ('{pattern}'). "
                    "Provide more specific detail."
                )
                break

    if not critiques:
        return True, ""

    return False, "Issues found:\n" + "\n".join(f"- {c}" for c in critiques)


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_graph(
    llm: BaseChatModel,
    fallback_llm: BaseChatModel | None,
    config: dict,
) -> CompiledStateGraph:
    """Build and compile the LangGraph commit-message pipeline.

    Parameters
    ----------
    llm : BaseChatModel
        Primary LLM used by all agent nodes.
    fallback_llm : BaseChatModel or None
        Fallback LLM used when the primary fails.
    config : dict
        Full configuration dict (used to read ``git.quality.*`` and
        ``git.conventional``).

    Returns
    -------
    CompiledStateGraph
        A compiled LangGraph ready for ``graph.invoke(state)``.
    """
    # Read config once, close over values in node functions
    git_cfg = config.get("git", {})
    quality_cfg = git_cfg.get("quality", {})
    max_retries = int(quality_cfg.get("max_retries", 2))
    min_body_lines = int(quality_cfg.get("min_body_lines", 3))
    check_boilerplate_setting = bool(quality_cfg.get("check_boilerplate", True))
    conventional_setting = bool(git_cfg.get("conventional", True))

    # ------------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------------

    def analyze_diff_node(state: GraphState) -> dict:
        """Run parallel diff analysis sub-tasks (type + scope from content)."""
        changed = ", ".join(
            state["changed_files"][: state["max_changed_files"]]
        )
        diff = state["raw_diff"]
        warning = TRUNCATION_WARNING if state["diff_truncated"] else ""

        kwargs = {
            "changed_files": changed,
            "diff_summary": diff,
            "truncated_warning": warning,
        }

        # Errors list lives here so the worker-thread on_error callback can
        # append enriched primary-failure reasons (list.append is atomic).
        errs: list[str] = []

        def record_primary_failure(reason: str) -> None:
            errs.append(reason)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            type_future = pool.submit(
                _call_with_fallback,
                ANALYZE_TYPE_PROMPT,
                state["primary_llm"],
                state.get("fallback_llm"),
                task_label="analyze_type",
                on_error=record_primary_failure,
                **kwargs,
            )
            scope_future = pool.submit(
                _call_with_fallback,
                ANALYZE_SCOPE_PROMPT,
                state["primary_llm"],
                state.get("fallback_llm"),
                task_label="analyze_scope",
                on_error=record_primary_failure,
                **kwargs,
            )
            type_result = type_future.result()
            scope_result = scope_future.result()

        diff_analysis: dict = {}

        if type_result and "type" in type_result:
            diff_analysis["content_type"] = str(type_result["type"])
            diff_analysis["content_type_reasoning"] = str(
                type_result.get("reasoning", "")
            )
            diff_analysis["content_type_confidence"] = float(
                type_result.get("confidence", 0.5)
            )
        else:
            errs.append("analyze_type: no valid result")

        if scope_result and "scope" in scope_result:
            diff_analysis["content_scope"] = str(scope_result["scope"])
            diff_analysis["content_scope_reasoning"] = str(
                scope_result.get("reasoning", "")
            )
        else:
            errs.append("analyze_scope: no valid result")

        return {
            "diff_analysis": diff_analysis,
            "errors": errs,
        }

    def write_message_node(state: GraphState) -> dict:
        """Write a commit message draft based on diff + analysis."""
        analysis = state.get("diff_analysis") or {}
        changed = ", ".join(
            state["changed_files"][: state["max_changed_files"]]
        )
        diff = state["raw_diff"]
        warning = TRUNCATION_WARNING if state["diff_truncated"] else ""

        # Build critique section if this is a retry
        critique_section = ""
        if state["critique_history"]:
            last_critique = state["critique_history"][-1]
            critique_section = (
                "Previous draft had issues. Address them:\n"
                f"{last_critique}"
            )

        kwargs = {
            "changed_files": changed,
            "diff_summary": diff,
            "truncated_warning": warning,
            "heuristic_type": state["heuristic_type"],
            "heuristic_scope": state["heuristic_scope"],
            "ticket": state["ticket"] or "",
            "content_type_analysis": (
                f"Content-based type: {analysis.get('content_type', 'N/A')}\n"
                f"Reasoning: {analysis.get('content_type_reasoning', 'N/A')}"
            ),
            "content_scope_analysis": (
                f"Content-based scope: {analysis.get('content_scope', 'N/A')}\n"
                f"Reasoning: {analysis.get('content_scope_reasoning', 'N/A')}"
            ),
            "user_context": state["user_context"] or "",
            "diff_instructions": FULL_DIFF_INSTRUCTIONS,
            "critique_section": critique_section,
            "max_subject_length": state["max_subject_length"],
        }

        errs: list[str] = list(state.get("errors", []))

        def record_primary_failure(reason: str) -> None:
            errs.append(reason)

        result = _call_with_fallback(
            WRITE_MESSAGE_PROMPT,
            state["primary_llm"],
            state.get("fallback_llm"),
            task_label="write_message",
            on_error=record_primary_failure,
            **kwargs,
        )

        if result and "subject" in result and "body" in result:
            return {
                "draft_subject": (result.get("subject") or "").strip(),
                "draft_body": (result.get("body") or "").strip(),
                "errors": errs,
            }

        # LLM failed entirely — signal downstream to use fallback
        return {
            "draft_subject": "",
            "draft_body": "",
            "errors": errs + ["write_message: no valid result"],
        }

    def check_quality_node(state: GraphState) -> dict:
        """Run deterministic quality checks on the draft."""
        subject = state.get("draft_subject", "")
        body = state.get("draft_body", "")

        passed, critique = _check_quality(
            subject=subject,
            body=body,
            max_subject_length=state["max_subject_length"],
            conventional=state.get("conventional", conventional_setting),
            min_body_lines=min_body_lines,
            check_boilerplate=check_boilerplate_setting,
        )

        if passed:
            return {"quality_passed": True}

        new_retry_count = state["retry_count"] + 1
        if new_retry_count <= max_retries:
            return {
                "quality_passed": False,
                "retry_count": new_retry_count,
                "critique_history": state["critique_history"] + [critique],
            }

        # Exhausted retries — accept best-effort draft
        return {
            "quality_passed": False,
            "retry_count": new_retry_count,
        }

    def output_node(state: GraphState) -> dict:
        """Final output node — passes through draft fields for core.py to read."""
        return {
            "draft_subject": state.get("draft_subject", ""),
            "draft_body": state.get("draft_body", ""),
        }

    # ------------------------------------------------------------------
    # Router
    # ------------------------------------------------------------------

    def decide_after_quality(state: GraphState) -> str:
        """Route: output on pass/exhaustion, write_message on retry."""
        if state.get("quality_passed"):
            return "output"
        if state["retry_count"] < max_retries:
            return "write_message"
        return "output"

    # ------------------------------------------------------------------
    # Build graph
    # ------------------------------------------------------------------

    workflow = StateGraph(GraphState)

    workflow.add_node("analyze_diff", analyze_diff_node)
    workflow.add_node("write_message", write_message_node)
    workflow.add_node("check_quality", check_quality_node)
    workflow.add_node("output", output_node)

    workflow.set_entry_point("analyze_diff")
    workflow.add_edge("analyze_diff", "write_message")
    workflow.add_edge("write_message", "check_quality")

    workflow.add_conditional_edges(
        "check_quality",
        decide_after_quality,
        {
            "write_message": "write_message",
            "output": "output",
        },
    )

    workflow.add_edge("output", END)

    return workflow.compile()
