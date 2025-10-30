#!/usr/bin/env python3
"""
CLI entrypoint for LangChain AutoCommit (full implementation)
- Loads config via master.load_config()
- Collects Git context (changed files, staged diff, branch)
- Invokes LangChain chain to generate a conventional commit
- Applies git commit (and optional push)
"""
import os, sys, json, argparse
from master import load_config

# LangChain commit generator
from chains.commit_chain import build_chain

def safe_int(value, default=0):
    """Convert value to int, handling YAML values with inline comments."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        # Extract value before any comment (space + #)
        value = value.split('#')[0].strip()
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def safe_float(value, default=0.0):
    """Convert value to float, handling YAML values with inline comments."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        # Extract value before any comment (space + #)
        value = value.split('#')[0].strip()
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

# Git helpers (pure subprocess; no external SDKs)
from scripts.git_utils import (
    ensure_git_repo,
    current_branch,
    changed_files,
    staged_diff_summary,
    autostage_all,
    commit,
    push,
    infer_type_from_paths,
    infer_scope_from_cwd,
    find_ticket,
)

def _bool(v, default=False):
    if isinstance(v, bool):
        return v
    if v is None:
        return default
    s = str(v).strip().lower()
    return s in {"1", "true", "t", "yes", "y"}


def main(argv=None):
    argv = argv or sys.argv[1:]
    ap = argparse.ArgumentParser(description="LangChain auto-commit using local Ollama")
    ap.add_argument("--dry-run", action="store_true", help="Show proposed commit but do not run git commit")
    ap.add_argument("--autostage", action="store_true", help="Run git add -A before commit (overrides config.git.autostage_all)")
    ap.add_argument("--amend", action="store_true", help="Amend previous commit (no edit)")
    ap.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt and proceed")
    ap.add_argument("--show-config", action="store_true", help="Print loaded config and exit")
    args = ap.parse_args(argv)

    cfg = load_config()
    if args.show_config:
        print(json.dumps(cfg, indent=2))
        return 0

    llm_cfg = cfg.get("llm", {})
    git_cfg = cfg.get("git", {})
    max_subject = safe_int(git_cfg.get("max_subject_length", 72), 72)

    # Working directory is the repo root we run from
    cwd = os.getcwd()

    # --- Git context ---
    ensure_git_repo(cwd)

    # Stage changes if requested
    if args.autostage or _bool(git_cfg.get("autostage_all", False)):
        autostage_all(cwd)

    files = changed_files(cwd)
    diff = staged_diff_summary(cwd)
    if not diff.strip():
        print("No staged changes. Use --autostage or git add <files>.", file=sys.stderr)
        return 2

    # Infer commit type/scope/ticket
    ctype = git_cfg.get("default_type", "chore")
    if _bool(git_cfg.get("conventional", True)):
        inferred = infer_type_from_paths(files)
        ctype = inferred or ctype

    scope = infer_scope_from_cwd(cwd) if _bool(git_cfg.get("scope_from_folder", True)) else ""

    branch = current_branch(cwd)
    ticket = ""
    pattern = git_cfg.get("ticket_regex")
    if pattern:
        ticket = find_ticket(branch, pattern) or ""

    # --- Build and run the LangChain commit generator ---
    chain = build_chain(
        base_url=llm_cfg.get("base_url", "http://localhost:11434"),
        model=llm_cfg.get("model", "granite4"),
        temperature=safe_float(llm_cfg.get("temperature", 0.2), 0.2),
        max_tokens=safe_int(llm_cfg.get("max_tokens", 512), 512),
    )

    inputs = dict(
        type=ctype,
        scope=scope,
        ticket=ticket,
        changed_files=files,
        diff_summary=diff,
        max_subject_length=max_subject,
    )

    raw = chain.invoke(inputs)
    content = getattr(raw, "content", raw)

    # Parse JSON strictly, with a best-effort fallback
    try:
        payload = json.loads(content)
    except Exception:
        start, end = content.find("{"), content.rfind("}")
        if start != -1 and end != -1 and end > start:
            payload = json.loads(content[start:end+1])
        else:
            payload = {"subject": f"{ctype}{f'({scope})' if scope else ''}: update", "body": "LLM parsing failed; using fallback."}

    subject = (payload.get("subject") or "").strip()
    body = (payload.get("body") or "").strip()

    if len(subject) > max_subject:
        subject = subject[:max_subject]

    print("\n--- Proposed Commit ---")
    print(subject)
    print()
    print(body)
    print("-----------------------\n")

    if args.dry_run:
        return 0

    if not args.yes:
        try:
            resp = input("Proceed with commit? [y/N]: ").strip().lower()
        except EOFError:
            resp = "n"
        if resp not in ("y", "yes"):
            print("Aborted.")
            return 1

    # Apply commit (and optional push)
    signoff = _bool(git_cfg.get("signoff", False))
    amend = args.amend or _bool(git_cfg.get("allow_amend", False))
    commit(cwd, subject, body, signoff=signoff, amend=amend)
    print("Committed.")

    if _bool(git_cfg.get("push_after_commit", False)):
        push(cwd)
        print("Pushed.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
