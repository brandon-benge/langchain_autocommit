import os
from typing import NamedTuple

from autocommit.config import load_config
from autocommit.chains.commit_chain import build_graph
from autocommit.utils.llm_provider import build_fallback_llm, resolve_llm
from autocommit.utils.git_utils import (
    autostage_all,
    changed_files,
    commit,
    current_branch,
    ensure_git_repo,
    find_ticket,
    infer_scope_from_cwd,
    infer_type_from_paths,
    push,
    staged_diff_summary,
)


class CommitMessage(NamedTuple):
    subject: str
    body: str


def _bool(v, default=False):
    if isinstance(v, bool):
        return v
    if v is None:
        return default
    s = str(v).strip().lower()
    return s in {"1", "true", "t", "yes", "y"}


def _build_fallback_body(files: list, type: str, scope: str) -> tuple:
    subject = f"{type}{f'({scope})' if scope else ''}: update"
    lines = [f"Changes made to {len(files)} file(s):"]
    for f in files[:10]:
        lines.append(f"- {f}")
    if len(files) > 10:
        lines.append(f"- ...and {len(files) - 10} more")
    return subject, "\n".join(lines)


def generate_commit_message(
    *,
    config: dict | None = None,
    config_overrides: dict | None = None,
    type: str | None = None,
    scope: str | None = None,
    ticket: str | None = None,
    context: str = "",
    committer: str = "",
    max_subject_length: int | None = None,
    cwd: str | None = None,
    autostage: bool | None = None,
    conventional: bool | None = None,
    dry_run: bool = False,
) -> CommitMessage:
    if cwd is None:
        cwd = os.getcwd()

    if config is None:
        cfg = load_config(config_overrides)
    else:
        cfg = config
        if config_overrides:
            from autocommit.config import deep_merge
            cfg = deep_merge(cfg, config_overrides)

    llm_cfg = cfg.get("llm", {})
    git_cfg = cfg.get("git", {})

    if max_subject_length is None:
        max_subject_length = int(git_cfg.get("max_subject_length", 72))

    max_diff_chars = int(git_cfg.get("max_diff_chars", 8000))
    max_changed_files = int(git_cfg.get("max_changed_files", 20))
    include_diff_patch = _bool(git_cfg.get("include_diff_patch", True))

    ensure_git_repo(cwd)

    if autostage is None:
        autostage = _bool(git_cfg.get("autostage_all", False))
    if autostage:
        autostage_all(cwd)

    files = changed_files(cwd)
    diff = staged_diff_summary(cwd, include_patch=include_diff_patch)

    if not files:
        return CommitMessage("", "")

    if not diff.strip():
        return CommitMessage("", "")

    diff_lines = [line for line in diff.split("\n") if line.strip() and not line.startswith("---")]
    content_lines = [line for line in diff_lines if not line.startswith("@@") and not line.startswith("diff --git") and not line.startswith("index ")]
    if len(content_lines) <= 1:
        return CommitMessage("", "")

    if conventional is None:
        conventional = _bool(git_cfg.get("conventional", True))

    if type is None:
        type = git_cfg.get("default_type", "chore")
        if conventional:
            inferred = infer_type_from_paths(files)
            type = inferred or type

    if scope is None:
        if _bool(git_cfg.get("scope_from_folder", True)):
            scope = infer_scope_from_cwd(cwd)
        else:
            scope = ""

    branch = current_branch(cwd)
    if ticket is None:
        ticket = ""
        pattern = git_cfg.get("ticket_regex")
        if pattern:
            ticket = find_ticket(branch, pattern) or ""

    _diff_truncated = max_diff_chars > 0 and len(diff) > max_diff_chars

    if _diff_truncated:
        diff = diff[:max_diff_chars]

    llm_model, provider_used = resolve_llm(llm_cfg)
    fallback_llm = build_fallback_llm(llm_cfg)
    graph = build_graph(llm_model, fallback_llm, cfg)

    initial_state: dict = dict(
        raw_diff=diff,
        changed_files=files,
        user_context=context or "",
        max_subject_length=max_subject_length,
        max_diff_chars=max_diff_chars,
        max_changed_files=max_changed_files,
        diff_truncated=_diff_truncated,
        heuristic_type=type,
        heuristic_scope=scope,
        ticket=ticket,
        conventional=conventional,
        primary_llm=llm_model,
        fallback_llm=fallback_llm,
        retry_count=0,
        critique_history=[],
        errors=[],
        diff_analysis=None,
        draft_subject="",
        draft_body="",
        quality_passed=False,
    )

    result = graph.invoke(initial_state)

    if not result or not isinstance(result, dict):
        subject, body = _build_fallback_body(files, type, scope)
        return CommitMessage(subject=subject, body=body)

    subject = (result.get("draft_subject") or "").strip()
    body = (result.get("draft_body") or "").strip()

    if not subject and not body:
        subject, body = _build_fallback_body(files, type, scope)
        return CommitMessage(subject=subject, body=body)

    if len(subject) > max_subject_length:
        truncated = subject[:max_subject_length]
        last_space = truncated.rfind(" ")
        if last_space > max_subject_length * 0.8:
            subject = truncated[:last_space]
        else:
            subject = truncated

    if committer:
        body += f"\n\nCommitter: {committer}"

    return CommitMessage(subject=subject, body=body)


def apply_commit(
    message: CommitMessage,
    *,
    cwd: str | None = None,
    signoff: bool = False,
    amend: bool = False,
    push_after: bool = False,
) -> None:
    if cwd is None:
        cwd = os.getcwd()
    if not message.subject:
        raise ValueError("No subject in commit message — nothing to commit")
    commit(cwd, message.subject, message.body, signoff=signoff, amend=amend)
    if push_after:
        push(cwd)


def generate_and_commit(
    *,
    config: dict | None = None,
    config_overrides: dict | None = None,
    type: str | None = None,
    scope: str | None = None,
    ticket: str | None = None,
    context: str = "",
    committer: str = "",
    max_subject_length: int | None = None,
    cwd: str | None = None,
    autostage: bool | None = None,
    conventional: bool | None = None,
    signoff: bool | None = None,
    amend: bool | None = None,
    push_after: bool | None = None,
) -> CommitMessage:
    if cwd is None:
        cwd = os.getcwd()

    if config is None:
        cfg = load_config(config_overrides)
    else:
        cfg = config
        if config_overrides:
            from autocommit.config import deep_merge
            cfg = deep_merge(cfg, config_overrides)

    git_cfg = cfg.get("git", {})

    if signoff is None:
        signoff = _bool(git_cfg.get("signoff", False))
    if amend is None:
        amend = _bool(git_cfg.get("allow_amend", False))
    if push_after is None:
        push_after = _bool(git_cfg.get("push_after_commit", False))

    message = generate_commit_message(
        config=cfg,
        config_overrides=None,
        type=type,
        scope=scope,
        ticket=ticket,
        context=context,
        committer=committer,
        max_subject_length=max_subject_length,
        cwd=cwd,
        autostage=autostage,
        conventional=conventional,
    )
    if message.subject:
        apply_commit(message, cwd=cwd, signoff=signoff, amend=amend, push_after=push_after)
    return message
