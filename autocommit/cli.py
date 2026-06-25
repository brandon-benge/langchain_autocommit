"""CLI entrypoint for LangChain AutoCommit."""
import argparse
import getpass
import json
import os
import sys

from autocommit.config import load_config
from autocommit.core import CommitMessage, generate_commit_message, apply_commit
from autocommit.utils.keychain import set_api_key
from autocommit.utils.git_utils import push


def _bool(v, default=False):
    if isinstance(v, bool):
        return v
    if v is None:
        return default
    s = str(v).strip().lower()
    return s in {"1", "true", "t", "yes", "y"}


def _merge_flag(flag_val, config_val, default=False):
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

    ap.add_argument("-c", "--context", type=str, default="",
                    help="Optional context describing what you changed and why")
    ap.add_argument("-n", "--committer", type=str, default="",
                    help="Committer name to include in the commit body")

    ap.add_argument("-t", "--type", type=str, default="",
                    help="Override commit type (feat, fix, chore, docs, test, etc.)")
    ap.add_argument("-s", "--scope", type=str, default="",
                    help="Override commit scope (ignores git.scope_from_folder)")
    ap.add_argument("--ticket", type=str, default="",
                    help="Override ticket ID extracted from branch name")

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

    git_cfg = cfg.get("git", {})
    max_subject = args.max_subject_length if args.max_subject_length > 0 else int(git_cfg.get("max_subject_length", 72))
    cwd = os.getcwd()

    message = generate_commit_message(
        config=cfg,
        config_overrides=None,
        type=args.type or None,
        scope=args.scope or None,
        ticket=args.ticket or None,
        context=args.context,
        committer=args.committer,
        max_subject_length=max_subject,
        cwd=cwd,
        autostage=_merge_flag(args.autostage, git_cfg.get("autostage_all", False)),
        conventional=_merge_flag(args.conventional, git_cfg.get("conventional", True)),
    )

    if not message.subject:
        print("  No changes detected in the repository.")
        print("  All files are up-to-date with the last commit.")
        return 0

    print("\n--- Proposed Commit ---")
    print(message.subject)
    print()
    print(message.body)
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
    apply_commit(message, cwd=cwd, signoff=signoff, amend=amend)
    print("Committed.")

    if _merge_flag(args.push, git_cfg.get("push_after_commit", False)):
        push(cwd)
        print("Pushed.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
