import os
from typing import Tuple
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from autocommit.utils.keychain import get_api_key


def resolve_llm(llm_cfg: dict) -> Tuple[BaseChatModel, str]:
    """Build primary LLM or fall back to Ollama. Returns (llm, provider_name)."""
    primary = llm_cfg.get("primary", {})
    fallback = llm_cfg.get("fallback", {})
    has_keychain = bool(primary.get("keychain"))
    has_env_var = bool(primary.get("env_var"))

    if has_keychain and has_env_var:
        raise ValueError(
            "Cannot configure both 'keychain' and 'env_var' in params.yaml "
            "under llm.primary. Choose one method for providing the API key."
        )

    try:
        if has_env_var:
            env_var_name = primary["env_var"]
            api_key = os.environ.get(env_var_name)
            if not api_key:
                raise ValueError(f"Environment variable {env_var_name} is not set")
        elif has_keychain:
            kc = primary["keychain"]
            api_key = get_api_key(
                kc.get("service", "langchain_autocommit"),
                kc.get("key", "opencode_api_key"),
            )
            if not api_key:
                raise ValueError("No API key found in macOS Keychain")
        else:
            raise ValueError("No API key source configured (keychain or env_var)")

        llm = ChatOpenAI(
            model=primary.get("model", "deepseek-v4-flash"),
            api_key=api_key,
            base_url=primary.get("base_url", "https://opencode.ai/zen/go/v1"),
            temperature=float(primary.get("temperature", 0.2)),
            max_tokens=int(primary.get("max_tokens", 512)),
            timeout=int(primary.get("timeout", 60)),
        )
        return llm, "opencode"

    except Exception as e:
        print(f"  Primary provider setup failed ({e}). Falling back to Ollama.")

        llm = ChatOllama(
            base_url=fallback.get("base_url", "http://localhost:11434"),
            model=fallback.get("model", "qwen3:8b"),
            temperature=float(fallback.get("temperature", 0.2)),
            num_predict=int(fallback.get("max_tokens", 4096)),
        )
        return llm, "ollama"


def build_fallback_llm(llm_cfg: dict) -> BaseChatModel:
    """Build the fallback Ollama LLM for retry after primary fails mid-generation."""
    fallback = llm_cfg.get("fallback", {})
    return ChatOllama(
        base_url=fallback.get("base_url", "http://localhost:11434"),
        model=fallback.get("model", "qwen3:8b"),
        temperature=float(fallback.get("temperature", 0.2)),
        num_predict=int(fallback.get("max_tokens", 4096)),
    )
