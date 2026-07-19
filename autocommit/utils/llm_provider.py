import os
from typing import Tuple

from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from autocommit.utils.keychain import get_api_key


def _resolve_api_key(provider_cfg: dict) -> str | None:
    """Resolve API key from env_var or keychain.

    Returns the key string if a source is configured and resolves.
    Returns None  if no key source is configured.
    Raises ValueError if both env_var and keychain are set, or a
    configured source fails to produce a key.
    """
    has_env_var = bool(provider_cfg.get("env_var"))
    has_keychain = bool(provider_cfg.get("keychain"))

    if has_env_var and has_keychain:
        raise ValueError(
            "Cannot configure both 'keychain' and 'env_var'. "
            "Choose one method for providing the API key."
        )

    if has_env_var:
        env_var_name = provider_cfg["env_var"]
        api_key = os.environ.get(env_var_name)
        if not api_key:
            raise ValueError(f"Environment variable {env_var_name} is not set")
        return api_key

    if has_keychain:
        kc = provider_cfg["keychain"]
        api_key = get_api_key(
            kc.get("service", "langchain_autocommit"),
            kc.get("key", "opencode_api_key"),
        )
        if not api_key:
            raise ValueError("No API key found in macOS Keychain")
        return api_key

    return None


def _build_chat_openai(cfg: dict, defaults: dict) -> ChatOpenAI:
    """Build ChatOpenAI from provider config merged with defaults."""
    return ChatOpenAI(
        model=cfg.get("model", defaults["model"]),
        api_key=cfg["_api_key"],
        base_url=cfg.get("base_url", defaults["base_url"]),
        temperature=float(cfg.get("temperature", defaults["temperature"])),
        max_tokens=int(cfg.get("max_tokens", defaults["max_tokens"])),
        timeout=int(cfg.get("timeout", defaults.get("timeout", 60))),
    )


def resolve_llm(llm_cfg: dict) -> Tuple[BaseChatModel, str]:
    """Build primary LLM or fall back. Returns (llm, provider_name).

    Resolution order:
      1. Primary     → ChatOpenAI (env_var / keychain)  → "opencode"
      2. Fallback    → ChatOpenAI (env_var / keychain)  → "opencode-fallback"
      3. Ultimate    → ChatOllama (local)               → "ollama"
    """
    primary = llm_cfg.get("primary", {})
    fallback = llm_cfg.get("fallback", {})

    # --- Tier 1 : Primary ChatOpenAI --------------------------------------------
    # Mutual exclusivity for primary is a config error — don't swallow it
    if bool(primary.get("env_var")) and bool(primary.get("keychain")):
        raise ValueError(
            "Cannot configure both 'keychain' and 'env_var' under llm.primary. "
            "Choose one method for providing the API key."
        )

    try:
        api_key = _resolve_api_key(primary)
        if api_key is None:
            raise ValueError("No API key source configured (keychain or env_var)")
        primary["_api_key"] = api_key
        llm = _build_chat_openai(primary, {
            "model": "deepseek-v4-flash",
            "base_url": "https://opencode.ai/zen/go/v1",
            "temperature": 0.2,
            "max_tokens": 512,
            "timeout": 60,
        })
        return llm, "opencode"
    except ValueError as e:
        print(f"  Primary provider setup failed ({e}).")

    # --- Tier 2 : Fallback ChatOpenAI (if key source configured) -----------------
    try:
        api_key = _resolve_api_key(fallback)
        if api_key is not None:
            fallback["_api_key"] = api_key
            llm = _build_chat_openai(fallback, {
                "model": "qwen3:8b",
                "base_url": "http://localhost:11434",
                "temperature": 0.2,
                "max_tokens": 4096,
            })
            return llm, "opencode-fallback"
    except ValueError as e:
        print(f"  Fallback provider setup failed ({e}).")

    # --- Tier 3 : Local Ollama ---------------------------------------------------
    print("  Falling back to Ollama (local).")
    llm = ChatOllama(
        base_url=fallback.get("base_url", "http://localhost:11434"),
        model=fallback.get("model", "qwen3:8b"),
        temperature=float(fallback.get("temperature", 0.2)),
        num_predict=int(fallback.get("max_tokens", 4096)),
    )
    return llm, "ollama"


def build_fallback_llm(llm_cfg: dict) -> BaseChatModel:
    """Build the fallback LLM for retry after primary fails mid-generation.

    Tries ChatOpenAI first if fallback config includes env_var / keychain,
    otherwise defaults to local ChatOllama.
    """
    fallback = llm_cfg.get("fallback", {})

    try:
        api_key = _resolve_api_key(fallback)
        if api_key is not None:
            fallback["_api_key"] = api_key
            return _build_chat_openai(fallback, {
                "model": "qwen3:8b",
                "base_url": "http://localhost:11434",
                "temperature": 0.2,
                "max_tokens": 4096,
            })
    except ValueError as e:
        print(f"  Fallback ChatOpenAI setup failed ({e}). Using Ollama.")

    return ChatOllama(
        base_url=fallback.get("base_url", "http://localhost:11434"),
        model=fallback.get("model", "qwen3:8b"),
        temperature=float(fallback.get("temperature", 0.2)),
        num_predict=int(fallback.get("max_tokens", 4096)),
    )
