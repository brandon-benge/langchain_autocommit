import sys
from unittest.mock import MagicMock, patch

import pytest

from autocommit.core import _bool


def _merge_flag(flag_val, config_val, default=False):
    if flag_val is not None:
        return flag_val
    return _bool(config_val, default)


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


class TestMergeFlag:
    def test_flag_wins_over_config(self):
        assert _merge_flag(True, False) is True
        assert _merge_flag(False, True) is False

    def test_none_flag_uses_config(self):
        assert _merge_flag(None, True) is True
        assert _merge_flag(None, False) is False

    def test_none_flag_and_no_config_uses_default(self):
        assert _merge_flag(None, None, default=True) is True
        assert _merge_flag(None, None, default=False) is False


class TestCliArgs:
    def test_dry_run_flag(self, mocker):
        mocker.patch("autocommit.cli.load_config", return_value={"llm": {}, "git": {}})
        msg = mocker.patch("autocommit.cli.generate_commit_message",
                           return_value=MagicMock(subject="test", body="body"))

        with patch.object(sys, "argv", ["autocommit", "--dry-run"]):
            from autocommit.cli import main
            result = main()
            assert result == 0

    def test_show_config_flag(self, mocker):
        mocker.patch("autocommit.cli.load_config", return_value={"test": "value"})

        with patch.object(sys, "argv", ["autocommit", "--show-config"]):
            from autocommit.cli import main
            result = main()
            assert result == 0

    def test_setup_key_flag(self, mocker):
        mocker.patch("autocommit.cli.load_config", return_value={
            "llm": {"primary": {"keychain": {"service": "test_svc", "key": "test_key"}}}
        })
        mocker.patch("autocommit.cli.getpass.getpass", return_value="sk-new-key")
        mock_set = mocker.patch("autocommit.cli.set_api_key")

        with patch.object(sys, "argv", ["autocommit", "--setup-key"]):
            from autocommit.cli import main
            result = main()
            assert result == 0
            mock_set.assert_called_once_with("test_svc", "test_key", "sk-new-key")

    def test_setup_key_aborts_on_empty(self, mocker):
        mocker.patch("autocommit.cli.load_config", return_value={
            "llm": {"primary": {"keychain": {"service": "s", "key": "k"}}}
        })
        mocker.patch("autocommit.cli.getpass.getpass", return_value="")

        with patch.object(sys, "argv", ["autocommit", "--setup-key"]):
            from autocommit.cli import main
            result = main()
            assert result == 1

    def test_no_changes_exits_early(self, mocker):
        mocker.patch("autocommit.cli.load_config", return_value={"llm": {}, "git": {}})
        mocker.patch("autocommit.cli.generate_commit_message",
                     return_value=MagicMock(subject="", body=""))

        with patch.object(sys, "argv", ["autocommit"]):
            from autocommit.cli import main
            result = main()
            assert result == 0

    def test_yes_flag_skips_confirmation(self, mocker):
        mocker.patch("autocommit.cli.load_config", return_value={
            "llm": {}, "git": {"default_type": "feat", "conventional": False, "scope_from_folder": False}
        })
        mock_msg = MagicMock(subject="test", body="test body")
        mocker.patch("autocommit.cli.generate_commit_message", return_value=mock_msg)
        mock_apply = mocker.patch("autocommit.cli.apply_commit")
        mocker.patch("autocommit.cli.push")

        with patch.object(sys, "argv", ["autocommit", "-y"]):
            from autocommit.cli import main
            result = main()
            assert result == 0
            mock_apply.assert_called_once()

    def test_context_passed_to_generate(self, mocker):
        mocker.patch("autocommit.cli.load_config", return_value={
            "llm": {}, "git": {"default_type": "feat", "conventional": False, "scope_from_folder": False}
        })
        mock_msg = MagicMock(subject="test", body="test body")
        mock_gen = mocker.patch("autocommit.cli.generate_commit_message", return_value=mock_msg)
        mocker.patch("autocommit.cli.apply_commit")
        mocker.patch("autocommit.cli.push")

        with patch.object(sys, "argv", ["autocommit", "-y", "-c", "refactored the auth module"]):
            from autocommit.cli import main
            result = main()
            assert result == 0
            assert mock_gen.call_args.kwargs["context"] == "refactored the auth module"

    def test_type_override(self, mocker):
        mocker.patch("autocommit.cli.load_config", return_value={
            "llm": {}, "git": {"default_type": "chore", "conventional": True, "scope_from_folder": False}
        })
        mock_msg = MagicMock(subject="test", body="test body")
        mock_gen = mocker.patch("autocommit.cli.generate_commit_message", return_value=mock_msg)
        mocker.patch("autocommit.cli.apply_commit")
        mocker.patch("autocommit.cli.push")

        with patch.object(sys, "argv", ["autocommit", "-y", "-t", "docs"]):
            from autocommit.cli import main
            result = main()
            assert result == 0
            assert mock_gen.call_args.kwargs["type"] == "docs"

    def test_scope_override(self, mocker):
        mocker.patch("autocommit.cli.load_config", return_value={
            "llm": {}, "git": {"default_type": "feat", "conventional": False, "scope_from_folder": True}
        })
        mock_msg = MagicMock(subject="test", body="test body")
        mock_gen = mocker.patch("autocommit.cli.generate_commit_message", return_value=mock_msg)
        mocker.patch("autocommit.cli.apply_commit")
        mocker.patch("autocommit.cli.push")

        with patch.object(sys, "argv", ["autocommit", "-y", "-s", "auth"]):
            from autocommit.cli import main
            result = main()
            assert result == 0
            assert mock_gen.call_args.kwargs["scope"] == "auth"

    def test_ticket_override(self, mocker):
        mocker.patch("autocommit.cli.load_config", return_value={
            "llm": {}, "git": {"default_type": "feat", "conventional": False, "scope_from_folder": False}
        })
        mock_msg = MagicMock(subject="test", body="test body")
        mock_gen = mocker.patch("autocommit.cli.generate_commit_message", return_value=mock_msg)
        mocker.patch("autocommit.cli.apply_commit")
        mocker.patch("autocommit.cli.push")

        with patch.object(sys, "argv", ["autocommit", "-y", "--ticket", "PROJ-42"]):
            from autocommit.cli import main
            result = main()
            assert result == 0
            assert mock_gen.call_args.kwargs["ticket"] == "PROJ-42"

    def test_committer_appended_to_body(self, mocker):
        mocker.patch("autocommit.cli.load_config", return_value={
            "llm": {}, "git": {"default_type": "feat", "conventional": False, "scope_from_folder": False}
        })
        mock_msg = MagicMock(subject="test", body="did some work\n\nCommitter: Brandon")
        mock_gen = mocker.patch("autocommit.cli.generate_commit_message", return_value=mock_msg)
        mock_apply = mocker.patch("autocommit.cli.apply_commit")

        with patch.object(sys, "argv", ["autocommit", "-y", "-n", "Brandon"]):
            from autocommit.cli import main
            result = main()
            assert result == 0
            assert mock_apply.call_args[0][0] is mock_msg

    def test_max_subject_length_override(self, mocker):
        mocker.patch("autocommit.cli.load_config", return_value={
            "llm": {}, "git": {"default_type": "feat", "conventional": False, "scope_from_folder": False,
                               "max_subject_length": 72}
        })
        mock_msg = MagicMock(subject="a" * 10, body="test body")
        mock_gen = mocker.patch("autocommit.cli.generate_commit_message", return_value=mock_msg)
        mocker.patch("autocommit.cli.apply_commit")
        mocker.patch("autocommit.cli.push")

        with patch.object(sys, "argv", ["autocommit", "-y", "--max-subject-length", "10"]):
            from autocommit.cli import main
            result = main()
            assert result == 0
            assert mock_gen.call_args.kwargs["max_subject_length"] == 10
