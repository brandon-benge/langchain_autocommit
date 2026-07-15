import argparse
import json
import sys
from unittest.mock import MagicMock, patch

import pytest
import yaml

from autocommit.cli import _build_llm_overrides, _build_quality_overrides, _merge_config_overrides
from autocommit.core import CommitMessage, _bool


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


class TestBuildLlmOverrides:
    def _args(self, **kwargs):
        defaults = dict(
            keychain=None,
            env_var=None,
            keychain_service=None,
            keychain_key=None,
            env_var_name=None,
            base_url=None,
            model=None,
            temperature=None,
            max_tokens=None,
            timeout=None,
        )
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    def test_keychain_enables_keychain_and_disables_env_var(self):
        overrides = _build_llm_overrides(self._args(keychain=True))
        primary = overrides["llm"]["primary"]
        assert primary["keychain"] == {"service": "langchain_autocommit", "key": "opencode_api_key"}
        assert primary["env_var"] is None

    def test_keychain_with_custom_service_key(self):
        overrides = _build_llm_overrides(self._args(
            keychain=True,
            keychain_service="my_service",
            keychain_key="my_key",
        ))
        primary = overrides["llm"]["primary"]
        assert primary["keychain"] == {"service": "my_service", "key": "my_key"}
        assert primary["env_var"] is None

    def test_no_keychain_disables_keychain(self):
        overrides = _build_llm_overrides(self._args(keychain=False))
        assert overrides["llm"]["primary"]["keychain"] is None

    def test_env_var_enables_env_var_and_disables_keychain(self):
        overrides = _build_llm_overrides(self._args(env_var=True))
        primary = overrides["llm"]["primary"]
        assert primary["env_var"] == "OPENCODE_API_KEY"
        assert primary["keychain"] is None

    def test_env_var_with_custom_name(self):
        overrides = _build_llm_overrides(self._args(
            env_var=True,
            env_var_name="MY_CUSTOM_KEY",
        ))
        primary = overrides["llm"]["primary"]
        assert primary["env_var"] == "MY_CUSTOM_KEY"
        assert primary["keychain"] is None

    def test_no_env_var_disables_env_var(self):
        overrides = _build_llm_overrides(self._args(env_var=False))
        assert overrides["llm"]["primary"]["env_var"] is None

    def test_keychain_and_env_var_both_true_errors(self):
        with pytest.raises(SystemExit):
            _build_llm_overrides(self._args(keychain=True, env_var=True))

    def test_base_url_override(self):
        overrides = _build_llm_overrides(self._args(base_url="https://custom.url/v1"))
        assert overrides["llm"]["primary"]["base_url"] == "https://custom.url/v1"

    def test_model_override(self):
        overrides = _build_llm_overrides(self._args(model="gpt-4"))
        assert overrides["llm"]["primary"]["model"] == "gpt-4"

    def test_temperature_override(self):
        overrides = _build_llm_overrides(self._args(temperature=0.7))
        assert overrides["llm"]["primary"]["temperature"] == 0.7

    def test_max_tokens_override(self):
        overrides = _build_llm_overrides(self._args(max_tokens=2048))
        assert overrides["llm"]["primary"]["max_tokens"] == 2048

    def test_timeout_override(self):
        overrides = _build_llm_overrides(self._args(timeout=120))
        assert overrides["llm"]["primary"]["timeout"] == 120

    def test_multiple_scalar_overrides(self):
        overrides = _build_llm_overrides(self._args(
            base_url="https://custom.url",
            model="gpt-4",
            temperature=0.5,
            max_tokens=1024,
            timeout=30,
        ))
        primary = overrides["llm"]["primary"]
        assert primary["base_url"] == "https://custom.url"
        assert primary["model"] == "gpt-4"
        assert primary["temperature"] == 0.5
        assert primary["max_tokens"] == 1024
        assert primary["timeout"] == 30

    def test_mixed_keychain_and_scalar_overrides(self):
        overrides = _build_llm_overrides(self._args(
            keychain=True,
            keychain_service="svc",
            keychain_key="k",
            model="deepseek-v4-pro",
        ))
        primary = overrides["llm"]["primary"]
        assert primary["keychain"] == {"service": "svc", "key": "k"}
        assert primary["model"] == "deepseek-v4-pro"
        assert primary["env_var"] is None

    def test_no_flags_returns_empty_dict(self):
        overrides = _build_llm_overrides(self._args())
        assert overrides == {}


class TestBuildQualityOverrides:
    def _args(self, **kwargs):
        defaults = dict(
            quality_max_retries=None,
            min_body_lines=None,
            check_boilerplate=None,
        )
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    def test_no_flags_returns_empty_dict(self):
        overrides = _build_quality_overrides(self._args())
        assert overrides == {}

    def test_quality_max_retries(self):
        overrides = _build_quality_overrides(self._args(quality_max_retries=5))
        assert overrides == {"git": {"quality": {"max_retries": 5}}}

    def test_min_body_lines(self):
        overrides = _build_quality_overrides(self._args(min_body_lines=10))
        assert overrides == {"git": {"quality": {"min_body_lines": 10}}}

    def test_check_boilerplate_true(self):
        overrides = _build_quality_overrides(self._args(check_boilerplate=True))
        assert overrides == {"git": {"quality": {"check_boilerplate": True}}}

    def test_check_boilerplate_false(self):
        overrides = _build_quality_overrides(self._args(check_boilerplate=False))
        assert overrides == {"git": {"quality": {"check_boilerplate": False}}}

    def test_multiple_flags(self):
        overrides = _build_quality_overrides(self._args(
            quality_max_retries=3,
            min_body_lines=5,
            check_boilerplate=True,
        ))
        quality = overrides["git"]["quality"]
        assert quality["max_retries"] == 3
        assert quality["min_body_lines"] == 5
        assert quality["check_boilerplate"] is True


class TestMergeConfigOverrides:
    def test_empty_dicts(self):
        result = _merge_config_overrides({}, {})
        assert result == {}

    def test_single_dict(self):
        result = _merge_config_overrides({"a": 1})
        assert result == {"a": 1}

    def test_merge_two_dicts(self):
        result = _merge_config_overrides({"llm": {"primary": {"model": "gpt-4"}}},
                                         {"git": {"quality": {"max_retries": 2}}})
        assert result["llm"]["primary"]["model"] == "gpt-4"
        assert result["git"]["quality"]["max_retries"] == 2

    def test_later_overrides_win(self):
        result = _merge_config_overrides({"git": {"quality": {"max_retries": 1}}},
                                         {"git": {"quality": {"max_retries": 5}}})
        assert result["git"]["quality"]["max_retries"] == 5


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
        mocker.patch("autocommit.utils.git_utils.push")

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
        mocker.patch("autocommit.utils.git_utils.push")

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
        mocker.patch("autocommit.utils.git_utils.push")

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
        mocker.patch("autocommit.utils.git_utils.push")

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
        mocker.patch("autocommit.utils.git_utils.push")

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
        mocker.patch("autocommit.utils.git_utils.push")

        with patch.object(sys, "argv", ["autocommit", "-y", "--max-subject-length", "10"]):
            from autocommit.cli import main
            result = main()
            assert result == 0
            assert mock_gen.call_args.kwargs["max_subject_length"] == 10

    def test_no_changes_exits_with_message(self, mocker):
        mocker.patch("autocommit.cli.load_config", return_value={"llm": {}, "git": {}})
        mocker.patch("autocommit.cli.generate_commit_message",
                     return_value=MagicMock(subject="", body=""))

        with patch.object(sys, "argv", ["autocommit"]):
            from autocommit.cli import main
            result = main()
            assert result == 0

    def test_config_file_flag_passed_to_load_config(self, mocker):
        """--config-file <path> is passed as config_path to load_config."""
        mock_load = mocker.patch("autocommit.cli.load_config", return_value={"llm": {}, "git": {}})
        mocker.patch("autocommit.cli.generate_commit_message",
                     return_value=MagicMock(subject="test", body="body"))
        mocker.patch("autocommit.cli.apply_commit")
        mocker.patch("autocommit.utils.git_utils.push")

        config_path = "/tmp/custom-config.yaml"
        with patch.object(sys, "argv", ["autocommit", "-y", "--config-file", config_path]):
            from autocommit.cli import main
            result = main()
            assert result == 0
            # load_config should have been called with config_path set
            assert mock_load.call_args.kwargs.get("config_path") == config_path

    def test_config_file_flag_with_overrides(self, mocker):
        """--config-file combined with override flags: overrides still applied."""
        mock_load = mocker.patch("autocommit.cli.load_config", return_value={"llm": {}, "git": {}})
        mocker.patch("autocommit.cli.generate_commit_message",
                     return_value=MagicMock(subject="test", body="body"))
        mocker.patch("autocommit.cli.apply_commit")
        mocker.patch("autocommit.utils.git_utils.push")

        with patch.object(sys, "argv", ["autocommit", "-y", "--config-file", "/tmp/cfg.yaml",
                                         "--model", "custom-model"]):
            from autocommit.cli import main
            result = main()
            assert result == 0
            # config_path should be set
            assert mock_load.call_args.kwargs.get("config_path") == "/tmp/cfg.yaml"
            # overrides should also be populated (llm.primary.model)
            overrides = mock_load.call_args.kwargs.get("overrides", {})
            assert overrides.get("llm", {}).get("primary", {}).get("model") == "custom-model"

    def test_config_file_no_flag_uses_default(self, mocker):
        """When --config-file is absent, config_path should be None in load_config call."""
        mock_load = mocker.patch("autocommit.cli.load_config", return_value={"llm": {}, "git": {}})
        mocker.patch("autocommit.cli.generate_commit_message",
                     return_value=MagicMock(subject="test", body="body"))
        mocker.patch("autocommit.cli.apply_commit")
        mocker.patch("autocommit.utils.git_utils.push")

        with patch.object(sys, "argv", ["autocommit", "-y"]):
            from autocommit.cli import main
            result = main()
            assert result == 0
            assert mock_load.call_args.kwargs.get("config_path") is None

    def test_config_file_overrides_autocommit_params(
        self, tmp_path, monkeypatch, capsys
    ):
        """--config-file wins over AUTOCOMMIT_PARAMS in the real config loader."""
        env_file = tmp_path / "environment.yaml"
        explicit_file = tmp_path / "explicit.yaml"
        env_file.write_text(yaml.safe_dump({"source": "environment"}))
        explicit_file.write_text(yaml.safe_dump({"source": "explicit"}))
        monkeypatch.setenv("AUTOCOMMIT_PARAMS", str(env_file))

        from autocommit.cli import main
        result = main(["--show-config", "--config-file", str(explicit_file)])

        assert result == 0
        assert json.loads(capsys.readouterr().out) == {"source": "explicit"}


class TestCliAutoPRFlags:
    @patch("autocommit.cli.apply_commit")
    @patch("autocommit.cli.generate_commit_message")
    @patch("autocommit.cli.load_config")
    def test_auto_pr_flag_enables(self, mock_load, mock_generate, mock_apply):
        """--auto-pr flag enables PR creation."""
        mock_load.return_value = {
            "llm": {},
            "git": {"auto_pr": {"enabled": False, "target_branch": "main"}},
        }
        mock_generate.return_value = MagicMock(subject="feat: test", body="body")
        mock_apply.return_value = "https://github.com/o/r/pull/1"

        with patch.object(sys, "argv", ["autocommit", "-y", "--push", "--auto-pr"]):
            from autocommit.cli import main
            result = main()

        assert result == 0
        call_kwargs = mock_apply.call_args.kwargs
        assert call_kwargs["auto_pr_enabled"] is True

    @patch("autocommit.cli.apply_commit")
    @patch("autocommit.cli.generate_commit_message")
    @patch("autocommit.cli.load_config")
    def test_no_auto_pr_flag_disables(self, mock_load, mock_generate, mock_apply):
        """--no-auto-pr flag disables PR creation even when config says enabled."""
        mock_load.return_value = {
            "llm": {},
            "git": {"auto_pr": {"enabled": True, "target_branch": "main"}},
        }
        mock_generate.return_value = MagicMock(subject="feat: test", body="body")

        with patch.object(sys, "argv", ["autocommit", "-y", "--no-auto-pr"]):
            from autocommit.cli import main
            result = main()

        assert result == 0
        call_kwargs = mock_apply.call_args.kwargs
        assert call_kwargs["auto_pr_enabled"] is False

    @patch("autocommit.cli.apply_commit")
    @patch("autocommit.cli.generate_commit_message")
    @patch("autocommit.cli.load_config")
    def test_auto_pr_target_branch_override(self, mock_load, mock_generate, mock_apply):
        """--auto-pr-target-branch overrides config value."""
        mock_load.return_value = {
            "llm": {},
            "git": {"auto_pr": {"enabled": True, "target_branch": "develop"}},
        }
        mock_generate.return_value = MagicMock(subject="feat: test", body="body")

        with patch.object(sys, "argv", ["autocommit", "-y", "--auto-pr-target-branch", "staging"]):
            from autocommit.cli import main
            result = main()

        assert result == 0
        call_kwargs = mock_apply.call_args.kwargs
        assert call_kwargs["auto_pr_target_branch"] == "staging"

    @patch("autocommit.cli.apply_commit")
    @patch("autocommit.cli.generate_commit_message")
    @patch("autocommit.cli.load_config")
    def test_auto_pr_title_body_flags(self, mock_load, mock_generate, mock_apply):
        """--auto-pr-title and --auto-pr-body flags pass through to apply_commit."""
        mock_load.return_value = {
            "llm": {},
            "git": {"auto_pr": {"enabled": True, "target_branch": "main"}},
        }
        mock_generate.return_value = MagicMock(subject="feat: test", body="body")

        with patch.object(sys, "argv", [
            "autocommit", "-y",
            "--auto-pr-title", "PR Title",
            "--auto-pr-body", "PR Body",
        ]):
            from autocommit.cli import main
            result = main()

        assert result == 0
        call_kwargs = mock_apply.call_args.kwargs
        assert call_kwargs["auto_pr_title"] == "PR Title"
        assert call_kwargs["auto_pr_body"] == "PR Body"

    @patch("autocommit.cli.apply_commit")
    @patch("autocommit.cli.generate_commit_message")
    @patch("autocommit.cli.load_config")
    def test_auto_pr_prints_url(self, mock_load, mock_generate, mock_apply, capsys):
        """PR URL is printed in CLI output when PR is created."""
        mock_load.return_value = {
            "llm": {},
            "git": {"auto_pr": {"enabled": True, "target_branch": "main"}},
        }
        mock_generate.return_value = MagicMock(subject="feat: test", body="body")
        mock_apply.return_value = "https://github.com/o/r/pull/42"

        with patch.object(sys, "argv", ["autocommit", "-y", "--push", "--auto-pr"]):
            from autocommit.cli import main
            result = main()

        assert result == 0
        captured = capsys.readouterr()
        assert "PR created: https://github.com/o/r/pull/42" in captured.out

    def test_cli_config_reaches_real_token_resolution(
        self, mocker, monkeypatch, capsys
    ):
        """CLI passes its effective config through the real apply workflow."""
        cfg = {
            "llm": {},
            "git": {
                "push_after_commit": True,
                "auto_pr": {
                    "enabled": True,
                    "target_branch": "main",
                    "token_env_var": "CLI_PR_TOKEN",
                },
            },
        }
        mocker.patch("autocommit.cli.load_config", return_value=cfg)
        mocker.patch(
            "autocommit.cli.generate_commit_message",
            return_value=CommitMessage("feat: CLI PR", "body"),
        )
        mocker.patch("autocommit.core.commit")
        mocker.patch("autocommit.core.push")
        mocker.patch("autocommit.core.current_branch", return_value="feature-cli")
        mock_create = mocker.patch(
            "autocommit.utils.pr_utils.create_pr",
            return_value="https://github.com/o/r/pull/99",
        )
        monkeypatch.setenv("CLI_PR_TOKEN", "cli-configured-token")

        from autocommit.cli import main
        result = main(["-y"])

        assert result == 0
        assert mock_create.call_args.kwargs["token"] == "cli-configured-token"
        assert "PR created: https://github.com/o/r/pull/99" in capsys.readouterr().out
