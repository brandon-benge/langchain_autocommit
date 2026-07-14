"""CLI entrypoint for LangChain AutoCommit."""
import argparse
import getpass
import json
import os
import sys

from autocommit.config import load_config
from autocommit.core import CommitMessage, generate_commit_message, apply_commit
from autocommit.utils.keychain import set_api_key


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


def _build_llm_overrides(args) -> dict:
    """Build config_overrides dict from CLI flags for LLM params."""
    primary_overrides = {}

    if args.keychain is True and args.env_var is True:
        print("error: --keychain and --env-var are mutually exclusive", file=sys.stderr)
        sys.exit(1)

    if args.keychain is True:
        primary_overrides["keychain"] = {
            "service": args.keychain_service or "langchain_autocommit",
            "key": args.keychain_key or "opencode_api_key",
        }
        primary_overrides["env_var"] = None
    elif args.keychain is False:
        primary_overrides["keychain"] = None

    if args.env_var is True:
        primary_overrides["env_var"] = args.env_var_name or "OPENCODE_API_KEY"
        primary_overrides["keychain"] = None
    elif args.env_var is False:
        primary_overrides["env_var"] = None

    if args.base_url is not None:
        primary_overrides["base_url"] = args.base_url
    if args.model is not None:
        primary_overrides["model"] = args.model
    if args.temperature is not None:
        primary_overrides["temperature"] = args.temperature
    if args.max_tokens is not None:
        primary_overrides["max_tokens"] = args.max_tokens
    if args.timeout is not None:
        primary_overrides["timeout"] = args.timeout

    if primary_overrides:
        return {"llm": {"primary": primary_overrides}}
    return {}


def _build_quality_overrides(args) -> dict:
    """Build config_overrides dict from CLI flags for git.quality.* params."""
    overrides = {}
    if args.quality_max_retries is not None:
        overrides["max_retries"] = args.quality_max_retries
    if args.min_body_lines is not None:
        overrides["min_body_lines"] = args.min_body_lines
    if args.check_boilerplate is not None:
        overrides["check_boilerplate"] = args.check_boilerplate
    if overrides:
        return {"git": {"quality": overrides}}
    return {}


def _merge_config_overrides(*dicts: dict) -> dict:
    """Deep-merge multiple config override dicts, later wins."""
    result: dict = {}
    for d in dicts:
        if d:
            from autocommit.config import deep_merge
            result = deep_merge(result, d)
    return result


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
    ap.add_argument("--push-set-upstream", action="store_true", dest="push_set_upstream", default=None,
                    help="Automatically set upstream tracking branch on first push")
    ap.add_argument("--no-push-set-upstream", action="store_false", dest="push_set_upstream", default=None,
                    help="Do not automatically set upstream tracking branch")
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

    ap.add_argument("--quality-max-retries", type=int, default=None,
                    help="Override max quality-loop retries (git.quality.max_retries)")
    ap.add_argument("--min-body-lines", type=int, default=None,
                    help="Override min body lines for quality check (git.quality.min_body_lines)")
    ap.add_argument("--check-boilerplate", action="store_true", dest="check_boilerplate", default=None,
                    help="Enable boilerplate detection in quality check")
    ap.add_argument("--no-check-boilerplate", action="store_false", dest="check_boilerplate", default=None,
                    help="Disable boilerplate detection in quality check")

    ap.add_argument("--keychain", action="store_true", dest="keychain", default=None,
                    help="Enable API key lookup from macOS Keychain")
    ap.add_argument("--no-keychain", action="store_false", dest="keychain", default=None,
                    help="Disable API key lookup from macOS Keychain")
    ap.add_argument("--keychain-service", type=str, default=None,
                    help="Keychain service name (default: langchain_autocommit)")
    ap.add_argument("--keychain-key", type=str, default=None,
                    help="Keychain key name (default: opencode_api_key)")

    ap.add_argument("--env-var", action="store_true", dest="env_var", default=None,
                    help="Enable API key lookup from environment variable")
    ap.add_argument("--no-env-var", action="store_false", dest="env_var", default=None,
                    help="Disable API key lookup from environment variable")
    ap.add_argument("--env-var-name", type=str, default=None,
                    help="Environment variable name (default: OPENCODE_API_KEY)")

    ap.add_argument("--base-url", type=str, default=None,
                    help="Override LLM base URL")
    ap.add_argument("--model", type=str, default=None,
                    help="Override LLM model name")
    ap.add_argument("--temperature", type=float, default=None,
                    help="Override LLM temperature")
    ap.add_argument("--max-tokens", type=int, default=None,
                    help="Override LLM max tokens")
    ap.add_argument("--timeout", type=int, default=None,
                    help="Override LLM timeout in seconds")
    ap.add_argument("--config-file", type=str, default=None,
                    help="Path to a custom YAML config file (absolute or relative to cwd)")
    args = ap.parse_args(argv)

    config_overrides = _merge_config_overrides(
        _build_llm_overrides(args),
        _build_quality_overrides(args),
    )
    cfg = load_config(config_path=args.config_file, overrides=config_overrides)
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
    push_after = _merge_flag(args.push, git_cfg.get("push_after_commit", False))
    push_set_upstream = _merge_flag(args.push_set_upstream, git_cfg.get("push_set_upstream", True))

    try:
        apply_commit(message, cwd=cwd, signoff=signoff, amend=amend,
                     push_after=push_after, push_set_upstream=push_set_upstream)
        print("Committed." if not push_after else "Committed.\n  Pushed.")
    except RuntimeError as e:
        print(f"  Push failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
