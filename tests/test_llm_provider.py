import pytest

from autocommit.utils.llm_provider import build_fallback_llm, resolve_llm


class TestResolveLLM:
    def test_primary_provider_with_env_var(self, mocker):
        mocker.patch.dict("os.environ", {"MY_API_KEY": "sk-test"})
        mock_chatopenai = mocker.patch("autocommit.utils.llm_provider.ChatOpenAI")
        mock_instance = mocker.MagicMock()
        mock_chatopenai.return_value = mock_instance

        cfg = {
            "primary": {
                "base_url": "https://api.example.com",
                "model": "test-model",
                "temperature": 0.1,
                "max_tokens": 200,
                "timeout": 30,
                "env_var": "MY_API_KEY",
            },
            "fallback": {"model": "fallback", "base_url": "http://localhost:11434"},
        }

        llm, name = resolve_llm(cfg)
        assert name == "opencode"
        assert llm is mock_instance

    def test_primary_provider_with_keychain(self, mocker):
        mocker.patch(
            "autocommit.utils.llm_provider.get_api_key", return_value="sk-keychain"
        )
        mock_chatopenai = mocker.patch("autocommit.utils.llm_provider.ChatOpenAI")
        mock_instance = mocker.MagicMock()
        mock_chatopenai.return_value = mock_instance

        cfg = {
            "primary": {
                "keychain": {"service": "s", "key": "k"},
            },
            "fallback": {"model": "fallback", "base_url": "http://localhost:11434"},
        }

        llm, name = resolve_llm(cfg)
        assert name == "opencode"
        assert llm is mock_instance

    def test_fallback_when_no_api_key(self, mocker):
        mock_chatollama = mocker.patch("autocommit.utils.llm_provider.ChatOllama")
        mock_instance = mocker.MagicMock()
        mock_chatollama.return_value = mock_instance

        cfg = {
            "primary": {},
            "fallback": {"model": "qwen3:8b", "base_url": "http://localhost:11434"},
        }

        llm, name = resolve_llm(cfg)
        assert name == "ollama"
        assert llm is mock_instance

    def test_fallback_when_env_var_missing(self, mocker):
        mock_chatollama = mocker.patch("autocommit.utils.llm_provider.ChatOllama")
        mock_instance = mocker.MagicMock()
        mock_chatollama.return_value = mock_instance

        cfg = {
            "primary": {"env_var": "MISSING_VAR"},
            "fallback": {"model": "qwen3:8b", "base_url": "http://localhost:11434"},
        }

        llm, name = resolve_llm(cfg)
        assert name == "ollama"
        assert llm is mock_instance

    def test_error_when_both_keychain_and_env_var(self):
        cfg = {
            "primary": {
                "keychain": {"service": "s", "key": "k"},
                "env_var": "SOME_VAR",
            },
            "fallback": {},
        }

        with pytest.raises(ValueError, match="Cannot configure both"):
            resolve_llm(cfg)

    def test_primary_uses_defaults_when_fields_missing(self, mocker):
        mocker.patch.dict("os.environ", {"MY_API_KEY": "sk-test"})
        mock_chatopenai = mocker.patch("autocommit.utils.llm_provider.ChatOpenAI")
        mock_instance = mocker.MagicMock()
        mock_chatopenai.return_value = mock_instance

        cfg = {
            "primary": {"env_var": "MY_API_KEY"},
            "fallback": {},
        }

        llm, name = resolve_llm(cfg)
        assert name == "opencode"
        call_kwargs = mock_chatopenai.call_args.kwargs
        assert call_kwargs["model"] == "deepseek-v4-flash"
        assert call_kwargs["base_url"] == "https://opencode.ai/zen/go/v1"

    # --- Fallback ChatOpenAI tests ---------------------------------------------

    def test_fallback_with_env_var(self, mocker):
        """Fallback uses ChatOpenAI when env_var is configured and set."""
        mocker.patch.dict("os.environ", {"FALLBACK_KEY": "sk-fallback"})
        mocker.patch("autocommit.utils.llm_provider.ChatOpenAI")
        mock_chatollama = mocker.patch("autocommit.utils.llm_provider.ChatOllama")

        cfg = {
            "primary": {"env_var": "MISSING_VAR"},
            "fallback": {
                "base_url": "https://fallback.example.com",
                "model": "fb-model",
                "env_var": "FALLBACK_KEY",
            },
        }

        llm, name = resolve_llm(cfg)
        assert name == "opencode-fallback"
        assert mock_chatollama.call_count == 0

    def test_fallback_with_keychain(self, mocker):
        """Fallback uses ChatOpenAI when keychain is configured."""
        mocker.patch(
            "autocommit.utils.llm_provider.get_api_key", return_value="sk-fallback"
        )
        mocker.patch("autocommit.utils.llm_provider.ChatOpenAI")
        mock_chatollama = mocker.patch("autocommit.utils.llm_provider.ChatOllama")

        cfg = {
            "primary": {"env_var": "MISSING_VAR"},
            "fallback": {
                "base_url": "https://fallback.example.com",
                "model": "fb-model",
                "keychain": {"service": "s", "key": "k"},
            },
        }

        llm, name = resolve_llm(cfg)
        assert name == "opencode-fallback"
        assert mock_chatollama.call_count == 0

    def test_fallback_with_env_var_missing(self, mocker):
        """Fallback env_var configured but missing -> Ollama."""
        mock_chatopenai = mocker.patch("autocommit.utils.llm_provider.ChatOpenAI")
        mock_chatollama = mocker.patch("autocommit.utils.llm_provider.ChatOllama")
        mock_instance = mocker.MagicMock()
        mock_chatollama.return_value = mock_instance

        cfg = {
            "primary": {"env_var": "MISSING_VAR"},
            "fallback": {
                "env_var": "ALSO_MISSING",
            },
        }

        llm, name = resolve_llm(cfg)
        assert name == "ollama"
        assert llm is mock_instance
        assert mock_chatopenai.call_count == 0

    def test_fallback_with_both_env_var_and_keychain(self, mocker):
        """Fallback mutual exclusivity caught -> Ollama."""
        mock_chatopenai = mocker.patch("autocommit.utils.llm_provider.ChatOpenAI")
        mock_chatollama = mocker.patch("autocommit.utils.llm_provider.ChatOllama")
        mock_instance = mocker.MagicMock()
        mock_chatollama.return_value = mock_instance

        cfg = {
            "primary": {"env_var": "MISSING_VAR"},
            "fallback": {
                "env_var": "SOME_VAR",
                "keychain": {"service": "s", "key": "k"},
            },
        }

        llm, name = resolve_llm(cfg)
        assert name == "ollama"
        assert llm is mock_instance
        assert mock_chatopenai.call_count == 0

    def test_primary_use_and_fallback_with_env_var(self, mocker):
        """Primary succeeds; fallback should not be called."""
        mocker.patch.dict("os.environ", {"PRIMARY_KEY": "sk-primary"})
        mock_chatopenai = mocker.patch("autocommit.utils.llm_provider.ChatOpenAI")
        mock_chatollama = mocker.patch("autocommit.utils.llm_provider.ChatOllama")
        mock_instance = mocker.MagicMock()
        mock_chatopenai.return_value = mock_instance

        cfg = {
            "primary": {"env_var": "PRIMARY_KEY"},
            "fallback": {
                "env_var": "FALLBACK_KEY",
            },
        }

        llm, name = resolve_llm(cfg)
        assert name == "opencode"
        assert llm is mock_instance
        assert mock_chatollama.call_count == 0


class TestBuildFallbackLLM:
    def test_builds_ollama_with_fallback_config(self, mocker):
        mock_chatollama = mocker.patch("autocommit.utils.llm_provider.ChatOllama")
        mock_instance = mocker.MagicMock()
        mock_chatollama.return_value = mock_instance

        cfg = {
            "fallback": {
                "base_url": "http://custom:11434",
                "model": "custom-model",
                "temperature": 0.5,
                "max_tokens": 1000,
            }
        }

        llm = build_fallback_llm(cfg)
        assert llm is mock_instance
        mock_chatollama.assert_called_once_with(
            base_url="http://custom:11434",
            model="custom-model",
            temperature=0.5,
            num_predict=1000,
        )

    def test_builds_openai_when_env_var_set(self, mocker):
        mocker.patch.dict("os.environ", {"FB_KEY": "sk-fb"})
        mock_chatopenai = mocker.patch("autocommit.utils.llm_provider.ChatOpenAI")
        mock_instance = mocker.MagicMock()
        mock_chatopenai.return_value = mock_instance
        mock_chatollama = mocker.patch("autocommit.utils.llm_provider.ChatOllama")

        cfg = {
            "fallback": {
                "base_url": "https://fb.example.com",
                "model": "fb-model",
                "temperature": 0.5,
                "env_var": "FB_KEY",
            },
        }

        llm = build_fallback_llm(cfg)
        assert llm is mock_instance
        assert mock_chatollama.call_count == 0

    def test_builds_openai_when_keychain_set(self, mocker):
        mocker.patch(
            "autocommit.utils.llm_provider.get_api_key", return_value="sk-fb"
        )
        mock_chatopenai = mocker.patch("autocommit.utils.llm_provider.ChatOpenAI")
        mock_instance = mocker.MagicMock()
        mock_chatopenai.return_value = mock_instance
        mock_chatollama = mocker.patch("autocommit.utils.llm_provider.ChatOllama")

        cfg = {
            "fallback": {
                "base_url": "https://fb.example.com",
                "model": "fb-model",
                "temperature": 0.5,
                "keychain": {"service": "s", "key": "k"},
            },
        }

        llm = build_fallback_llm(cfg)
        assert llm is mock_instance
        assert mock_chatollama.call_count == 0

    def test_builds_ollama_when_env_var_missing(self, mocker):
        mock_chatopenai = mocker.patch("autocommit.utils.llm_provider.ChatOpenAI")
        mock_chatollama = mocker.patch("autocommit.utils.llm_provider.ChatOllama")
        mock_instance = mocker.MagicMock()
        mock_chatollama.return_value = mock_instance

        cfg = {
            "fallback": {
                "env_var": "MISSING_VAR",
            },
        }

        llm = build_fallback_llm(cfg)
        assert llm is mock_instance
        assert mock_chatopenai.call_count == 0

    def test_builds_ollama_when_both_env_var_and_keychain(self, mocker):
        mock_chatopenai = mocker.patch("autocommit.utils.llm_provider.ChatOpenAI")
        mock_chatollama = mocker.patch("autocommit.utils.llm_provider.ChatOllama")
        mock_instance = mocker.MagicMock()
        mock_chatollama.return_value = mock_instance

        cfg = {
            "fallback": {
                "env_var": "SOME_VAR",
                "keychain": {"service": "s", "key": "k"},
            },
        }

        llm = build_fallback_llm(cfg)
        assert llm is mock_instance
        assert mock_chatopenai.call_count == 0
