"""Tests for autocommit/utils/pr_token.py."""

import os
from unittest.mock import patch

import pytest

from autocommit.utils.pr_token import resolve_pr_token


class TestResolvePRToken:
    def test_env_var_found(self):
        """Reads token from configured environment variable."""
        cfg = {"git": {"auto_pr": {"token_env_var": "MY_PR_TOKEN"}}}
        with patch.dict(os.environ, {"MY_PR_TOKEN": "ghp_secret"}, clear=True):
            token = resolve_pr_token(cfg)
        assert token == "ghp_secret"

    def test_env_var_default(self):
        """Uses default GITHUB_TOKEN when not specified in config."""
        cfg = {"git": {"auto_pr": {"enabled": True}}}
        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_default"}, clear=True):
            token = resolve_pr_token(cfg)
        assert token == "ghp_default"

    def test_keychain_fallback(self):
        """Falls back to macOS Keychain when env var is not set."""
        cfg = {
            "git": {
                "auto_pr": {
                    "token_env_var": "GITHUB_TOKEN",
                    "keychain": {
                        "service": "my_service",
                        "key": "my_key",
                    },
                }
            }
        }
        with patch.dict(os.environ, {}, clear=True):
            with patch("autocommit.utils.pr_token.get_api_key", return_value="kc_secret"):
                token = resolve_pr_token(cfg)
        assert token == "kc_secret"

    def test_keychain_default_service_key(self):
        """Uses default keychain service/key when not specified."""
        cfg = {
            "git": {
                "auto_pr": {
                    "token_env_var": "GITHUB_TOKEN",
                    "keychain": {},
                }
            }
        }
        with patch.dict(os.environ, {}, clear=True):
            with patch("autocommit.utils.pr_token.get_api_key", return_value="kc_default") as mock_kc:
                token = resolve_pr_token(cfg)
        assert token == "kc_default"
        mock_kc.assert_called_once_with("langchain_autocommit", "github_token")

    def test_missing_token_raises_error(self):
        """Raises RuntimeError when no token source is configured."""
        cfg = {"git": {"auto_pr": {"token_env_var": "GITHUB_TOKEN"}}}
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError, match="No PR API token found"):
                resolve_pr_token(cfg)

    def test_missing_auto_pr_config_raises_error(self):
        """Raises RuntimeError when git.auto_pr is not in config."""
        cfg = {"git": {}}
        with pytest.raises(RuntimeError, match="git.auto_pr is not configured"):
            resolve_pr_token(cfg)
