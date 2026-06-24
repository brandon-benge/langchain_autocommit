#!/usr/bin/env python3
"""
CLI entrypoint for LangChain AutoCommit (full implementation)
- Loads config via master.load_config()
- Collects Git context (changed files, staged diff, branch)
- Invokes LangChain chain to generate a conventional commit
- Applies git commit (and optional push)
"""
import os, sys, json, argparse, getpass

try:
    from master import load_config
    from chains.commit_chain import build_chain
    from scripts.llm_provider import resolve_llm, build_fallback_llm
    from scripts.keychain import set_api_key
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
except ModuleNotFoundError as e:
    print(f"Error: Missing required module '{e.name}'.")
    print("Install dependencies by running:")
    print("  ./run_venv.sh")
    print("Then activate the virtual environment:")
    print("  source ../venv/bin/activate")
    sys.exit(1)


def _bool(v, default=False):
    if isinstance(v, bool):
        return v
    if v is None:
        return default
    s = str(v).strip().lower()
    return s in {"1", "true", "t", "yes", "y"}


def _merge_flag(flag_val, config_val, default=False):
    """CLI flag → config value → fallback default."""
    if flag_val is not None:
        return flag_val
    return _bool(config_val, default)


def main(argv=None):
    argv = argv or sys.argv[1:]
    ap = argparse.ArgumentParser(description="LangChain auto-commit using local LLM")
    ap.add_argument("--dry-run", action="store_true", help="Show proposed commit without applying it")
    ap.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")
    ap.add_argument("--show-config", action="store_true", help="Print parsed YAML config and exit")
    ap.add_argument("--setup-key", action="store_true", help="Store API key in macOS Keychain and exit")

    # User input flags
    ap.add_argument("-c", "--context", type=str, default="",
        help="Optional context describing what you changed and why")
    ap.add_argument("-n", "--committer", type=str, default="",
        help="Committer name to include in the commit body")

    # Override flags
    ap.add_argument("-t", "--type", type=str, default="",
        help="Override commit type (feat, fix, chore, docs, test, etc.)")
    ap.add_argument("-s", "--scope", type=str, default="",
        help="Override commit scope (ignores git.scope_from_folder)")
    ap.add_argument("--ticket", type=str, default="",
        help="Override ticket ID extracted from branch name")

    # Boolean three-state flags (None = use config)
    ap.add_argument("--autostage", action="store_true", dest="autostage", default=None,
        help="Enable auto-staging all files")
    ap.add_argument("--no-autostage", action="store_false", dest="autostage", default=None,
        help="Disable auto-staging all files")
    ap.add_argument("--amend", action="store_true", dest="amend", default=None,
        help="Amend previous commit instead of creating a new one")
    ap.add_argument("--no-amend", action="store_false", dest="amend", default=None,
        help="Do not amend previous commit")
    ap.add_argument("--push", action="store_true", dest="push", default=None,
        help="Push after commit")
    ap.add_argument("--no-push", action="store_false", dest="push", default=None,
        help="Do not push after commit")
    ap.add_argument("--signoff", action="store_true", dest="signoff", default=None,
        help="Add Signed-off-by trailer")
    ap.add_argument("--no-signoff", action="store_false", dest="signoff", default=None,
        help="Omit Signed-off-by trailer")
    ap.add_argument("--conventional", action="store_true", dest="conventional", default=None,
        help="Enforce conventional commit format")
    ap.add_argument("--no-conventional", action="store_false", dest="conventional", default=None,
        help="Disable conventional commit enforcement")

    # Numeric overrides
    ap.add_argument("--max-subject-length", type=int, default=0,
        help="Override max subject line length")
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
    max_subject = args.max_subject_length if args.max_subject_length > 0 else int(git_cfg.get("max_subject_length", 72))

    cwd = os.getcwd()

    # --- Git context ---
    ensure_git_repo(cwd)

    if _merge_flag(args.autostage, git_cfg.get("autostage_all", False)):
        autostage_all(cwd)

    files = changed_files(cwd)
    diff = staged_diff_summary(cwd)

    if not files:
        print("  No changes detected in the repository.")
        print("  All files are up-to-date with the last commit.")
        return 0

    if not diff.strip():
        if _merge_flag(args.autostage, git_cfg.get("autostage_all", False)):
            print("  No changes to commit after staging.")
            print("  All modified files appear to have no actual differences.")
        else:
            print("  No staged changes found.")
            print("  Use 'git add <files>' to stage changes, or run with --autostage")
            print(f"  Modified files: {', '.join(files) if files else 'none'}")
        return 0

    diff_lines = [line for line in diff.split('\n') if line.strip() and not line.startswith('---')]
    content_lines = [line for line in diff_lines if not line.startswith('@@') and not line.startswith('diff --git') and not line.startswith('index ')]
    if len(content_lines) <= 1:
        print("  No meaningful changes detected.")
        print("  Staged files contain only metadata or whitespace changes.")
        return 0

    # --- Resolve type, scope, ticket (CLI flag wins, then inference, then config default) ---
    if args.type:
        ctype = args.type
    else:
        ctype = git_cfg.get("default_type", "chore")
        if _merge_flag(args.conventional, git_cfg.get("conventional", True)):
            inferred = infer_type_from_paths(files)
            ctype = inferred or ctype

    if args.scope:
        scope = args.scope
    else:
        scope = infer_scope_from_cwd(cwd) if _bool(git_cfg.get("scope_from_folder", True)) else ""

    branch = current_branch(cwd)
    if args.ticket:
        ticket = args.ticket
    else:
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
        user_context=args.context or "",
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
        truncated = subject[:max_subject]
        last_space = truncated.rfind(' ')
        if last_space > max_subject * 0.8:
            subject = truncated[:last_space]
        else:
            subject = truncated

    # Append committer if provided
    if args.committer:
        body += f"\n\nCommitter: {args.committer}"

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

    signoff = _merge_flag(args.signoff, git_cfg.get("signoff", False))
    amend = _merge_flag(args.amend, git_cfg.get("allow_amend", False))
    commit(cwd, subject, body, signoff=signoff, amend=amend)
    print("Committed.")

    if _merge_flag(args.push, git_cfg.get("push_after_commit", False)):
        push(cwd)
        print("Pushed.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
