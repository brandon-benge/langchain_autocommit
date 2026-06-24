import sys
from unittest.mock import MagicMock, patch

import pytest

from autocommit import _bool


class TestBoolHelper:
    def test_true_values(self):
        assert _bool(True) is True
        assert _bool("true") is True
        assert _bool("True") is True
        assert _bool("yes") is True
        assert _bool("1") is True
        assert _bool("t") is True
        assert _bool("y") is True

    def test_false_values(self):
        assert _bool(False) is False
        assert _bool("false") is False
        assert _bool("no") is False
        assert _bool("0") is False
        assert _bool("f") is False

    def test_none_uses_default(self):
        assert _bool(None) is False
        assert _bool(None, default=True) is True

    def test_non_bool_string(self):
        assert _bool("random") is False


class TestCliArgs:
    def test_dry_run_flag(self):
        with patch.object(sys, "argv", ["autocommit.py", "--dry-run"]):
            with patch("autocommit.load_config") as mock_cfg:
                mock_cfg.return_value = {}
                with patch("autocommit.changed_files", return_value=[]):
                    from autocommit import main
                    result = main()
                    assert result == 0

    def test_show_config_flag(self):
        with patch.object(sys, "argv", ["autocommit.py", "--show-config"]):
            with patch("autocommit.load_config") as mock_cfg:
                mock_cfg.return_value = {"test": "value"}
                from autocommit import main
                result = main()
                assert result == 0

    def test_setup_key_flag(self, mocker):
        mocker.patch("autocommit.load_config", return_value={
            "llm": {
                "primary": {
                    "keychain": {
                        "service": "test_svc",
                        "key": "test_key",
                    }
                }
            }
        })
        mocker.patch("autocommit.getpass.getpass", return_value="sk-new-key")
        mock_set = mocker.patch("autocommit.set_api_key")

        with patch.object(sys, "argv", ["autocommit.py", "--setup-key"]):
            from autocommit import main
            result = main()
            assert result == 0
            mock_set.assert_called_once_with("test_svc", "test_key", "sk-new-key")

    def test_setup_key_aborts_on_empty(self, mocker):
        mocker.patch("autocommit.load_config", return_value={
            "llm": {
                "primary": {
                    "keychain": {"service": "s", "key": "k"}
                }
            }
        })
        mocker.patch("autocommit.getpass.getpass", return_value="")

        with patch.object(sys, "argv", ["autocommit.py", "--setup-key"]):
            from autocommit import main
            result = main()
            assert result == 1

    def test_no_changes_exits_early(self):
        with patch.object(sys, "argv", ["autocommit.py"]):
            with patch("autocommit.load_config") as mock_cfg:
                mock_cfg.return_value = {"llm": {}, "git": {}}
                with patch("autocommit.changed_files", return_value=[]):
                    from autocommit import main
                    result = main()
                    assert result == 0

    def test_fallback_during_generation(self, mocker):
        mocker.patch("autocommit.load_config", return_value={
            "llm": {
                "primary": {"model": "test", "keychain": {"service": "s", "key": "k"}},
                "fallback": {"model": "test", "base_url": "http://localhost:11434"},
            },
            "git": {"default_type": "feat", "conventional": False, "scope_from_folder": False},
        })
        mocker.patch("autocommit.changed_files", return_value=["a.py"])
        mocker.patch("autocommit.staged_diff_summary", return_value="M a.py")
        mocker.patch("autocommit.current_branch", return_value="main")

        mock_llm = mocker.MagicMock()
        mock_llm.invoke.side_effect = [
            Exception("Primary timeout"),
            mocker.MagicMock(content='{"subject": "fallback", "body": "used ollama"}'),
        ]
        mocker.patch("autocommit.resolve_llm", return_value=(mock_llm, "opencode"))
        mock_fb = mocker.MagicMock()
        mocker.patch("autocommit.build_fallback_llm", return_value=mock_fb)
        mock_fb.invoke.return_value = mocker.MagicMock(content='{"subject": "retry", "body": "ok"}')

        with patch.object(sys, "argv", ["autocommit.py", "-y"]):
            from autocommit import main
            result = main()
            assert result == 0
