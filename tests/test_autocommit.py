import sys
from unittest.mock import MagicMock, patch

import pytest

from autocommit import _bool, _merge_flag


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

    def test_yes_flag_skips_confirmation(self, mocker):
        mocker.patch("autocommit.load_config", return_value={
            "llm": {"primary": {"keychain": {"service": "s", "key": "k"}},
                    "fallback": {"model": "x", "base_url": "http://localhost:11434"}},
            "git": {"default_type": "feat", "conventional": False, "scope_from_folder": False},
        })
        mocker.patch("autocommit.changed_files", return_value=["a.py", "b.py"])
        mocker.patch("autocommit.staged_diff_summary", return_value="M a.py\nM b.py\n---\n 2 files changed")
        mocker.patch("autocommit.current_branch", return_value="main")
        mock_llm = mocker.MagicMock()
        mock_llm.return_value = mocker.MagicMock(
            content='{"subject": "test", "body": "test body"}'
        )
        mocker.patch("autocommit.resolve_llm", return_value=(mock_llm, "opencode"))
        mocker.patch("autocommit.commit")
        mocker.patch("autocommit.push")

        with patch.object(sys, "argv", ["autocommit.py", "-y"]):
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
        mocker.patch("autocommit.changed_files", return_value=["a.py", "b.py"])
        mocker.patch("autocommit.staged_diff_summary", return_value="M a.py\nM b.py\n---\n 2 files changed")
        mocker.patch("autocommit.current_branch", return_value="main")

        mock_llm = mocker.MagicMock()
        mock_llm.side_effect = [
            Exception("Primary timeout"),
            mocker.MagicMock(content='{"subject": "fallback", "body": "used ollama"}'),
        ]
        mocker.patch("autocommit.resolve_llm", return_value=(mock_llm, "opencode"))
        mock_fb = mocker.MagicMock()
        mock_fb.return_value = mocker.MagicMock(content='{"subject": "retry", "body": "ok"}')
        mocker.patch("autocommit.build_fallback_llm", return_value=mock_fb)
        mocker.patch("autocommit.commit")
        mocker.patch("autocommit.push")
        mock_fb.return_value = mocker.MagicMock(content='{"subject": "retry", "body": "ok"}')

        with patch.object(sys, "argv", ["autocommit.py", "-y"]):
            from autocommit import main
            result = main()
            assert result == 0

    def test_context_passed_to_inputs(self, mocker):
        mocker.patch("autocommit.load_config", return_value={
            "llm": {"primary": {"keychain": {"service": "s", "key": "k"}},
                    "fallback": {"model": "x", "base_url": "http://localhost:11434"}},
            "git": {"default_type": "feat", "conventional": False, "scope_from_folder": False},
        })
        mocker.patch("autocommit.changed_files", return_value=["a.py", "b.py"])
        mocker.patch("autocommit.staged_diff_summary", return_value="M a.py\nM b.py\n---\n 2 files changed")
        mocker.patch("autocommit.current_branch", return_value="main")
        mock_llm = mocker.MagicMock()
        mock_llm.return_value = mocker.MagicMock(
            content='{"subject": "test", "body": "test body"}'
        )
        mocker.patch("autocommit.resolve_llm", return_value=(mock_llm, "opencode"))
        mocker.patch("autocommit.commit")
        mocker.patch("autocommit.push")

        with patch.object(sys, "argv", ["autocommit.py", "-y", "-c", "refactored the auth module"]):
            from autocommit import main
            result = main()
            assert result == 0
            prompt = str(mock_llm.call_args[0][0])
            assert "refactored the auth module" in prompt

    def test_type_override(self, mocker):
        mocker.patch("autocommit.load_config", return_value={
            "llm": {"primary": {"keychain": {"service": "s", "key": "k"}},
                    "fallback": {"model": "x", "base_url": "http://localhost:11434"}},
            "git": {"default_type": "chore", "conventional": True, "scope_from_folder": False},
        })
        mocker.patch("autocommit.changed_files", return_value=["docs/guide.md", "src/util.py"])
        mocker.patch("autocommit.staged_diff_summary", return_value="M docs/guide.md\nM src/util.py\n---\n 2 files changed")
        mocker.patch("autocommit.current_branch", return_value="main")
        mock_llm = mocker.MagicMock()
        mock_llm.return_value = mocker.MagicMock(
            content='{"subject": "test", "body": "test body"}'
        )
        mocker.patch("autocommit.resolve_llm", return_value=(mock_llm, "opencode"))
        mocker.patch("autocommit.commit")
        mocker.patch("autocommit.push")

        with patch.object(sys, "argv", ["autocommit.py", "-y", "-t", "docs"]):
            from autocommit import main
            result = main()
            assert result == 0
            prompt = str(mock_llm.call_args[0][0])
            assert "docs" in prompt

    def test_scope_override(self, mocker):
        mocker.patch("autocommit.load_config", return_value={
            "llm": {"primary": {"keychain": {"service": "s", "key": "k"}},
                    "fallback": {"model": "x", "base_url": "http://localhost:11434"}},
            "git": {"default_type": "feat", "conventional": False, "scope_from_folder": True},
        })
        mocker.patch("autocommit.changed_files", return_value=["a.py", "b.py"])
        mocker.patch("autocommit.staged_diff_summary", return_value="M a.py\nM b.py\n---\n 2 files changed")
        mocker.patch("autocommit.current_branch", return_value="main")
        mock_llm = mocker.MagicMock()
        mock_llm.return_value = mocker.MagicMock(
            content='{"subject": "test", "body": "test body"}'
        )
        mocker.patch("autocommit.resolve_llm", return_value=(mock_llm, "opencode"))
        mocker.patch("autocommit.commit")
        mocker.patch("autocommit.push")

        with patch.object(sys, "argv", ["autocommit.py", "-y", "-s", "auth"]):
            from autocommit import main
            result = main()
            assert result == 0
            prompt = str(mock_llm.call_args[0][0])
            assert "auth" in prompt

    def test_ticket_override(self, mocker):
        mocker.patch("autocommit.load_config", return_value={
            "llm": {"primary": {"keychain": {"service": "s", "key": "k"}},
                    "fallback": {"model": "x", "base_url": "http://localhost:11434"}},
            "git": {"default_type": "feat", "conventional": False, "scope_from_folder": False},
        })
        mocker.patch("autocommit.changed_files", return_value=["a.py", "b.py"])
        mocker.patch("autocommit.staged_diff_summary", return_value="M a.py\nM b.py\n---\n 2 files changed")
        mocker.patch("autocommit.current_branch", return_value="main")
        mock_llm = mocker.MagicMock()
        mock_llm.return_value = mocker.MagicMock(
            content='{"subject": "test", "body": "test body"}'
        )
        mocker.patch("autocommit.resolve_llm", return_value=(mock_llm, "opencode"))
        mocker.patch("autocommit.commit")
        mocker.patch("autocommit.push")

        with patch.object(sys, "argv", ["autocommit.py", "-y", "--ticket", "PROJ-42"]):
            from autocommit import main
            result = main()
            assert result == 0
            prompt = str(mock_llm.call_args[0][0])
            assert "PROJ-42" in prompt

    def test_committer_appended_to_body(self, mocker):
        mocker.patch("autocommit.load_config", return_value={
            "llm": {"primary": {"keychain": {"service": "s", "key": "k"}},
                    "fallback": {"model": "x", "base_url": "http://localhost:11434"}},
            "git": {"default_type": "feat", "conventional": False, "scope_from_folder": False},
        })
        mocker.patch("autocommit.changed_files", return_value=["a.py", "b.py"])
        mocker.patch("autocommit.staged_diff_summary", return_value="M a.py\nM b.py\n---\n 2 files changed")
        mocker.patch("autocommit.current_branch", return_value="main")
        mock_llm = mocker.MagicMock()
        mock_llm.return_value = mocker.MagicMock(
            content='{"subject": "test", "body": "did some work"}'
        )
        mocker.patch("autocommit.resolve_llm", return_value=(mock_llm, "opencode"))
        mock_commit = mocker.patch("autocommit.commit")

        with patch.object(sys, "argv", ["autocommit.py", "-y", "-n", "Brandon"]):
            from autocommit import main
            result = main()
            assert result == 0
            call_args, _ = mock_commit.call_args
            _, _, body = call_args[0], call_args[1], call_args[2]
            assert body == "did some work\n\nCommitter: Brandon"

    def test_max_subject_length_override(self, mocker):
        mocker.patch("autocommit.load_config", return_value={
            "llm": {"primary": {"keychain": {"service": "s", "key": "k"}},
                    "fallback": {"model": "x", "base_url": "http://localhost:11434"}},
            "git": {"default_type": "feat", "conventional": False, "scope_from_folder": False,
                    "max_subject_length": 72},
        })
        mocker.patch("autocommit.changed_files", return_value=["a.py", "b.py"])
        mocker.patch("autocommit.staged_diff_summary", return_value="M a.py\nM b.py\n---\n 2 files changed")
        mocker.patch("autocommit.current_branch", return_value="main")
        mock_llm = mocker.MagicMock()
        mock_llm.return_value = mocker.MagicMock(
            content='{"subject": "' + "a" * 50 + '", "body": "test body"}'
        )
        mocker.patch("autocommit.resolve_llm", return_value=(mock_llm, "opencode"))
        mocker.patch("autocommit.commit")
        mocker.patch("autocommit.push")

        with patch.object(sys, "argv", ["autocommit.py", "-y", "--max-subject-length", "10"]):
            from autocommit import main
            result = main()
            assert result == 0
