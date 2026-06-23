from typing import Tuple
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from scripts.keychain import get_api_key


def resolve_llm(llm_cfg: dict) -> Tuple[BaseChatModel, str]:
    """Build primary LLM or fall back to Ollama. Returns (llm, provider_name)."""
    primary = llm_cfg.get("primary", {})
    fallback = llm_cfg.get("fallback", {})

    try:
        kc = primary.get("keychain", {})
        api_key = get_api_key(
            kc.get("service", "langchain_autocommit"),
            kc.get("key", "opencode_api_key"),
        )
        if not api_key:
            raise ValueError("No API key found in macOS Keychain")

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
