import pytest

pytest.importorskip("langchain_core.language_models", reason="LangChain not available")

from scripts.llm_provider import resolve_llm, build_fallback_llm


class TestResolveLlm:
    def test_returns_opencode_when_key_present(self, mocker):
        mocker.patch("scripts.llm_provider.get_api_key", return_value="sk-test")
        mock_chat = mocker.patch("scripts.llm_provider.ChatOpenAI")
        mock_chat.return_value = mocker.MagicMock()

        llm, provider = resolve_llm({
            "primary": {
                "base_url": "https://opencode.ai/zen/go/v1",
                "model": "deepseek-v4-flash",
                "keychain": {"service": "s", "key": "k"},
            },
            "fallback": {
                "base_url": "http://localhost:11434",
                "model": "qwen3:8b",
            },
        })

        assert provider == "opencode"

    def test_falls_back_to_ollama_when_key_missing(self, mocker):
        mocker.patch("scripts.llm_provider.get_api_key", return_value=None)
        mock_ollama = mocker.patch("scripts.llm_provider.ChatOllama")
        mock_ollama.return_value = mocker.MagicMock()

        llm, provider = resolve_llm({
            "primary": {
                "base_url": "https://opencode.ai/zen/go/v1",
                "model": "deepseek-v4-flash",
                "keychain": {"service": "s", "key": "k"},
            },
            "fallback": {
                "base_url": "http://localhost:11434",
                "model": "qwen3:8b",
            },
        })

        assert provider == "ollama"

    def test_falls_back_when_chatopenai_raises(self, mocker):
        mocker.patch("scripts.llm_provider.get_api_key", return_value="sk-test")
        mocker.patch("scripts.llm_provider.ChatOpenAI", side_effect=Exception("API error"))
        mock_ollama = mocker.patch("scripts.llm_provider.ChatOllama")
        mock_ollama.return_value = mocker.MagicMock()

        llm, provider = resolve_llm({
            "primary": {
                "base_url": "https://opencode.ai/zen/go/v1",
                "model": "deepseek-v4-flash",
                "keychain": {"service": "s", "key": "k"},
            },
            "fallback": {
                "base_url": "http://localhost:11434",
                "model": "qwen3:8b",
            },
        })

        assert provider == "ollama"

    def test_env_var_provides_key(self, mocker, monkeypatch):
        monkeypatch.setenv("OPENCODE_API_KEY", "sk-test")
        mock_chat = mocker.patch("scripts.llm_provider.ChatOpenAI")
        mock_chat.return_value = mocker.MagicMock()

        llm, provider = resolve_llm({
            "primary": {
                "base_url": "https://opencode.ai/zen/go/v1",
                "model": "deepseek-v4-flash",
                "env_var": "OPENCODE_API_KEY",
            },
            "fallback": {
                "base_url": "http://localhost:11434",
                "model": "qwen3:8b",
            },
        })

        assert provider == "opencode"

    def test_env_var_missing_falls_back(self, mocker, monkeypatch):
        monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
        mock_ollama = mocker.patch("scripts.llm_provider.ChatOllama")
        mock_ollama.return_value = mocker.MagicMock()

        llm, provider = resolve_llm({
            "primary": {
                "base_url": "https://opencode.ai/zen/go/v1",
                "model": "deepseek-v4-flash",
                "env_var": "OPENCODE_API_KEY",
            },
            "fallback": {
                "base_url": "http://localhost:11434",
                "model": "qwen3:8b",
            },
        })

        assert provider == "ollama"

    def test_both_keychain_and_env_var_raises(self, mocker):
        with pytest.raises(ValueError, match="Cannot configure both"):
            resolve_llm({
                "primary": {
                    "keychain": {"service": "s", "key": "k"},
                    "env_var": "OPENCODE_API_KEY",
                },
                "fallback": {
                    "base_url": "http://localhost:11434",
                    "model": "qwen3:8b",
                },
            })

    def test_uses_defaults_when_config_sparse(self, mocker):
        mocker.patch("scripts.llm_provider.get_api_key", return_value=None)
        mock_ollama = mocker.patch("scripts.llm_provider.ChatOllama")
        mock_ollama.return_value = mocker.MagicMock()

        llm, provider = resolve_llm({})

        assert provider == "ollama"


class TestBuildFallbackLlm:
    def test_builds_ollama(self, mocker):
        mock_ollama = mocker.patch("scripts.llm_provider.ChatOllama")
        mock_ollama.return_value = mocker.MagicMock()

        result = build_fallback_llm({
            "fallback": {
                "base_url": "http://localhost:11434",
                "model": "qwen3:8b",
            }
        })

        mock_ollama.assert_called_once()
