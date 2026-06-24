#!/Users/brandonbenge/Desktop/GitProjects/venv/bin/python3
"""
CLI entrypoint for LangChain AutoCommit (full implementation)
- Loads config via master.load_config()
- Collects Git context (changed files, staged diff, branch)
- Invokes LangChain chain to generate a conventional commit
- Applies git commit (and optional push)
"""
import os, sys, json, argparse, getpass
from master import load_config

# LangChain commit generator
from chains.commit_chain import build_chain
from scripts.llm_provider import resolve_llm, build_fallback_llm
from scripts.keychain import set_api_key

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
    ap.add_argument("--setup-key", action="store_true", help="Store API key in macOS Keychain and exit")
    args = ap.parse_args(argv)

    cfg = load_config()
    if args.show_config:
        print(json.dumps(cfg, indent=2))
        return 0

    if args.setup_key:
        kc = cfg.get("llm", {}).get("primary", {}).get("keychain", {})
        service = kc.get("service", "langchain_autocommit")
        key = kc.get("key", "opencode_api_key")
        api_key = getpass.getpass(f"Enter API key (stored as {service}/{key}): ")
        if not api_key:
            print("No key entered. Aborting.")
            return 1
        set_api_key(service, key, api_key)
        print(f"  API key stored in macOS Keychain ({service}/{key}).")
        return 0

    llm_cfg = cfg.get("llm", {})
    git_cfg = cfg.get("git", {})
    max_subject = int(git_cfg.get("max_subject_length", 72))

    # Working directory is the repo root we run from
    cwd = os.getcwd()

    # --- Git context ---
    ensure_git_repo(cwd)

    # Stage changes if requested
    if args.autostage or _bool(git_cfg.get("autostage_all", False)):
        autostage_all(cwd)

    files = changed_files(cwd)
    diff = staged_diff_summary(cwd)
    
    # Check for no changes at all
    if not files:
        print("📍 No changes detected in the repository.")
        print("   All files are up-to-date with the last commit.")
        return 0
    
    # Check for no staged changes
    if not diff.strip():
        if args.autostage or _bool(git_cfg.get("autostage_all", False)):
            print("📍 No changes to commit after staging.")
            print("   All modified files appear to have no actual differences.")
        else:
            print("📍 No staged changes found.")
            print("   Use 'git add <files>' to stage changes, or run with --autostage")
            print(f"   Modified files: {', '.join(files) if files else 'none'}")
        return 0
    
    # Check for empty diff (only metadata, no real content changes)
    diff_lines = [line for line in diff.split('\n') if line.strip() and not line.startswith('---')]
    content_lines = [line for line in diff_lines if not line.startswith('@@') and not line.startswith('diff --git') and not line.startswith('index ')]
    if len(content_lines) <= 1:  # Only separator or no meaningful content
        print("📍 No meaningful changes detected.")
        print("   Staged files contain only metadata or whitespace changes.")
        return 0

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
    llm_model, provider_used = resolve_llm(llm_cfg)
    print(f"  Using provider: {provider_used}")
    chain = build_chain(llm_model)

    inputs = dict(
        type=ctype,
        scope=scope,
        ticket=ticket,
        changed_files=files,
        diff_summary=diff,
        max_subject_length=max_subject,
    )

    raw = None
    try:
        raw = chain.invoke(inputs)
    except Exception as e:
        if provider_used == "opencode":
            print(f"  Primary provider failed during generation ({e}). Falling back to Ollama.")
            fb_llm = build_fallback_llm(llm_cfg)
            chain = build_chain(fb_llm)
            raw = chain.invoke(inputs)
        else:
            raise

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

    # Smart truncation: avoid cutting words in half
    if len(subject) > max_subject:
        truncated = subject[:max_subject]
        # Find the last space to avoid cutting a word
        last_space = truncated.rfind(' ')
        if last_space > max_subject * 0.8:  # Only truncate at word boundary if we don't lose too much
            subject = truncated[:last_space]
        else:
            subject = truncated  # Fall back to hard truncation if no good break point

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
