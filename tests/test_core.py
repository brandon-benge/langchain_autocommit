import os
from unittest.mock import MagicMock, patch

import pytest

from autocommit.core import (
    CommitMessage,
    _build_fallback_body,
    _bool,
    apply_commit,
    generate_and_commit,
    generate_commit_message,
)


class TestBoolHelper:
    def test_true_values(self):
        assert _bool(True) is True
        assert _bool("true") is True
        assert _bool("yes") is True
        assert _bool("1") is True

    def test_false_values(self):
        assert _bool(False) is False
        assert _bool("false") is False
        assert _bool("no") is False
        assert _bool("0") is False

    def test_none_uses_default(self):
        assert _bool(None) is False
        assert _bool(None, default=True) is True


class TestBuildFallbackBody:
    def test_single_file(self):
        subject, body = _build_fallback_body(["src/main.py"], "feat", "app")
        assert subject == "feat(app): update"
        assert "1 file" in body

    def test_multiple_files(self):
        subject, body = _build_fallback_body(["a.py", "b.py", "c.py"], "chore", "")
        assert subject == "chore: update"
        assert "3 file" in body

    def test_more_than_ten_files(self):
        files = [f"file_{i}.py" for i in range(15)]
        subject, body = _build_fallback_body(files, "feat", "core")
        assert subject == "feat(core): update"
        assert "...and 5 more" in body

    def test_no_files(self):
        subject, body = _build_fallback_body([], "feat", "")
        assert "0 file" in body


class TestGenerateCommitMessageConfigPath:
    def test_config_path_passed_to_load_config(self, mocker):
        """When config is None and config_path is given, it's passed to load_config."""
        mock_load = mocker.patch("autocommit.core.load_config", return_value={"llm": {}, "git": {}})
        mocker.patch("autocommit.core.changed_files", return_value=[])
        mocker.patch("autocommit.core.staged_diff_summary")
        mocker.patch("autocommit.core.ensure_git_repo")

        generate_commit_message(config=None, config_path="/tmp/custom.yaml", cwd="/tmp")

        # load_config should have been called with the config_path as first positional arg
        assert mock_load.call_args[0][0] == "/tmp/custom.yaml"

    def test_config_path_ignored_when_config_provided(self, mocker):
        """When config dict is provided, config_path is ignored."""
        mock_load = mocker.patch("autocommit.core.load_config", return_value={"llm": {}, "git": {}})
        mocker.patch("autocommit.core.changed_files", return_value=[])
        mocker.patch("autocommit.core.staged_diff_summary")
        mocker.patch("autocommit.core.ensure_git_repo")

        config_dict = {"custom": "value"}
        generate_commit_message(config=config_dict, config_path="/tmp/custom.yaml", cwd="/tmp")

        # load_config should NOT have been called (config was provided)
        mock_load.assert_not_called()


class TestGenerateCommitMessageEarlyExit:
    def test_empty_files(self, mocker):
        mocker.patch("autocommit.core.changed_files", return_value=[])
        mocker.patch("autocommit.core.staged_diff_summary", return_value="some diff")
        mocker.patch("autocommit.core.load_config", return_value={"llm": {}, "git": {}})
        mocker.patch("autocommit.core.ensure_git_repo")
        msg = generate_commit_message(cwd="/tmp")
        assert msg.subject == ""
        assert msg.body == ""

    def test_empty_diff(self, mocker):
        mocker.patch("autocommit.core.changed_files", return_value=["a.py"])
        mocker.patch("autocommit.core.staged_diff_summary", return_value="")
        mocker.patch("autocommit.core.load_config", return_value={"llm": {}, "git": {}})
        mocker.patch("autocommit.core.ensure_git_repo")
        msg = generate_commit_message(cwd="/tmp")
        assert msg.subject == ""
        assert msg.body == ""

    def test_boilerplate_only_diff(self, mocker):
        mocker.patch("autocommit.core.changed_files", return_value=["a.py"])
        mocker.patch("autocommit.core.staged_diff_summary",
                     return_value="---\n@@ -1 +1 @@\ndiff --git a/a.py b/a.py\nindex abc..def 100644")
        mocker.patch("autocommit.core.load_config", return_value={"llm": {}, "git": {}})
        mocker.patch("autocommit.core.ensure_git_repo")
        msg = generate_commit_message(cwd="/tmp")
        assert msg.subject == ""
        assert msg.body == ""


class _MockGraph:
    """Minimal mock for CompiledStateGraph that returns a fixed result."""

    def __init__(self, result=None, side_effect=None):
        self._result = result or {"draft_subject": "", "draft_body": ""}
        self._side_effect = side_effect

    def invoke(self, state, config=None, **kwargs):
        if self._side_effect:
            raise self._side_effect
        return self._result


class TestGenerateCommitMessageLlmFallback:
    def _setup_mocks(self, mocker, graph_result=None, graph_side_effect=None):
        mocker.patch("autocommit.core.changed_files", return_value=["src/main.py"])
        mocker.patch("autocommit.core.staged_diff_summary", return_value="A---\nA src/main.py\n---\n 1 file changed")
        mocker.patch("autocommit.core.load_config",
                     return_value={"llm": {}, "git": {"conventional": False, "scope_from_folder": False}})
        mocker.patch("autocommit.core.ensure_git_repo")
        mocker.patch("autocommit.core.current_branch", return_value="main")
        mock_graph = _MockGraph(result=graph_result, side_effect=graph_side_effect)
        mocker.patch("autocommit.core.resolve_llm", return_value=(MagicMock(), "opencode"))
        mocker.patch("autocommit.core.build_fallback_llm")
        mocker.patch("autocommit.core.build_graph", return_value=mock_graph)
        return mock_graph

    def test_fallback_body_on_llm_failure(self, mocker):
        self._setup_mocks(mocker, graph_result={"draft_subject": "", "draft_body": ""})

        msg = generate_commit_message(cwd="/tmp")
        assert "update" in msg.subject
        assert "1 file" in msg.body

    def test_fallback_body_on_parse_failure(self, mocker):
        # Simulate graph returning None (should not happen in practice, but defensive)
        self._setup_mocks(mocker, graph_result=None)

        msg = generate_commit_message(cwd="/tmp")
        assert "update" in msg.subject
        assert "1 file" in msg.body

    def test_committer_appended_to_body(self, mocker):
        self._setup_mocks(mocker, graph_result={"draft_subject": "feat: add thing", "draft_body": "Added the thing"})

        msg = generate_commit_message(cwd="/tmp", committer="Jane Doe")
        assert "Jane Doe" in msg.body
        assert "Committer: Jane Doe" in msg.body


class TestGenerateCommitMessageSubjectTruncation:
    def _setup_mocks(self, mocker, graph_result=None):
        mocker.patch("autocommit.core.changed_files", return_value=["src/main.py"])
        mocker.patch("autocommit.core.staged_diff_summary", return_value="A---\nA src/main.py\n---\n 1 file changed")
        mocker.patch("autocommit.core.load_config",
                     return_value={"llm": {}, "git": {"conventional": False, "scope_from_folder": False}})
        mocker.patch("autocommit.core.ensure_git_repo")
        mocker.patch("autocommit.core.current_branch", return_value="main")
        mock_graph = _MockGraph(result=graph_result)
        mocker.patch("autocommit.core.resolve_llm", return_value=(MagicMock(), "opencode"))
        mocker.patch("autocommit.core.build_graph", return_value=mock_graph)

    def test_no_truncation_needed(self, mocker):
        self._setup_mocks(mocker, graph_result={"draft_subject": "short", "draft_body": "body"})
        msg = generate_commit_message(cwd="/tmp", max_subject_length=100)
        assert msg.subject == "short"

    def test_subject_truncated(self, mocker):
        long_subject = "a" * 50 + " " + "b" * 50
        self._setup_mocks(mocker, graph_result={"draft_subject": long_subject, "draft_body": "body"})
        msg = generate_commit_message(cwd="/tmp", max_subject_length=30)
        assert len(msg.subject) <= 30


class TestApplyCommitAutoPR:
    def _make_msg(self, subject="feat: add feature", body="Some body"):
        return CommitMessage(subject=subject, body=body)

    @patch("autocommit.core.commit")
    @patch("autocommit.core.push")
    @patch("autocommit.core.current_branch")
    def test_auto_pr_creates_pr(self, mock_branch, mock_push, mock_commit):
        """apply_commit calls create_pr when auto_pr_enabled=True."""
        mock_branch.return_value = "feature-xyz"
        events = []
        mock_push.side_effect = lambda *args, **kwargs: events.append("push")
        # Patch at the actual module paths since imports are lazy (inside function)
        with patch("autocommit.utils.pr_token.resolve_pr_token", return_value="ghp_token"):
            with patch("autocommit.utils.pr_utils.create_pr",
                       side_effect=lambda **kwargs: (
                           events.append("create_pr")
                           or "https://github.com/o/r/pull/1"
                       )) as mock_create:
                url = apply_commit(
                    self._make_msg(),
                    cwd="/tmp",
                    push_after=True,
                    auto_pr_enabled=True,
                    auto_pr_target_branch="main",
                    _config={"git": {"auto_pr": {"enabled": True}}},
                )
        assert url == "https://github.com/o/r/pull/1"
        assert events == ["push", "create_pr"]
        mock_create.assert_called_once_with(
            repo_path="/tmp",
            token="ghp_token",
            head_branch="feature-xyz",
            base_branch="main",
            title="feat: add feature",
            body="Some body",
        )

    @patch("autocommit.core.commit")
    @patch("autocommit.core.push")
    @patch("autocommit.core.current_branch")
    def test_auto_pr_same_branch_skips(
        self, mock_branch, mock_push, mock_commit, caplog
    ):
        """No PR when current branch equals target branch."""
        mock_branch.return_value = "main"
        with caplog.at_level("INFO", logger="autocommit.core"):
            with patch("autocommit.utils.pr_utils.create_pr") as mock_create:
                url = apply_commit(
                    self._make_msg(),
                    cwd="/tmp",
                    push_after=True,
                    auto_pr_enabled=True,
                    auto_pr_target_branch="main",
                )
        assert url is None
        mock_create.assert_not_called()
        assert "matches target branch" in caplog.text

    @patch("autocommit.core.commit")
    @patch("autocommit.core.push")
    def test_auto_pr_disabled(self, mock_push, mock_commit):
        """No PR when auto_pr_enabled is False."""
        with patch("autocommit.utils.pr_utils.create_pr") as mock_create:
            url = apply_commit(
                self._make_msg(),
                cwd="/tmp",
                auto_pr_enabled=False,
            )
        assert url is None
        mock_create.assert_not_called()

    @patch("autocommit.core.commit")
    @patch("autocommit.core.push")
    @patch("autocommit.core.current_branch")
    def test_auto_pr_returns_none_when_disabled(self, mock_branch, mock_push, mock_commit):
        """Returns None when auto_pr_enabled is True but same branch."""
        mock_branch.return_value = "main"
        url = apply_commit(
            self._make_msg(),
            cwd="/tmp",
            push_after=True,
            auto_pr_enabled=True,
            auto_pr_target_branch="main",
        )
        assert url is None

    @patch("autocommit.core.commit")
    @patch("autocommit.core.push")
    @patch("autocommit.core.current_branch")
    def test_auto_pr_defaults_not_enabled(self, mock_branch, mock_push, mock_commit):
        """Default behavior (no kwargs) does not create PRs."""
        mock_branch.return_value = "feature-xyz"
        with patch("autocommit.utils.pr_utils.create_pr") as mock_create:
            url = apply_commit(self._make_msg(), cwd="/tmp")
        assert url is None
        mock_create.assert_not_called()

    @patch("autocommit.core.commit")
    @patch("autocommit.core.push")
    @patch("autocommit.core.current_branch")
    def test_auto_pr_custom_title_body(self, mock_branch, mock_push, mock_commit):
        """auto_pr_title and auto_pr_body override commit message."""
        mock_branch.return_value = "feature-xyz"
        with patch("autocommit.utils.pr_token.resolve_pr_token", return_value="token"):
            with patch("autocommit.utils.pr_utils.create_pr", return_value="url") as mock_create:
                apply_commit(
                    self._make_msg(subject="ignored", body="ignored"),
                    cwd="/tmp",
                    push_after=True,
                    auto_pr_enabled=True,
                    auto_pr_target_branch="main",
                    auto_pr_title="Custom Title",
                    auto_pr_body="Custom Body",
                    _config={"git": {"auto_pr": {"enabled": True}}},
                )
        mock_create.assert_called_once()
        assert mock_create.call_args[1]["title"] == "Custom Title"
        assert mock_create.call_args[1]["body"] == "Custom Body"

    @patch("autocommit.core.commit")
    @patch("autocommit.core.push")
    @patch("autocommit.core.current_branch")
    def test_auto_pr_requires_push(self, mock_branch, mock_push, mock_commit):
        """Enabling auto-PR without a push never attempts PR creation."""
        mock_branch.return_value = "feature-xyz"
        with patch("autocommit.utils.pr_token.resolve_pr_token") as mock_token:
            with patch("autocommit.utils.pr_utils.create_pr") as mock_create:
                url = apply_commit(
                    self._make_msg(),
                    cwd="/tmp",
                    push_after=False,
                    auto_pr_enabled=True,
                )

        assert url is None
        mock_push.assert_not_called()
        mock_token.assert_not_called()
        mock_create.assert_not_called()

    @patch("autocommit.core.commit")
    @patch("autocommit.core.push", side_effect=RuntimeError("push failed"))
    def test_auto_pr_not_attempted_after_failed_push(self, mock_push, mock_commit):
        """A failed push aborts before token resolution or PR creation."""
        with patch("autocommit.utils.pr_token.resolve_pr_token") as mock_token:
            with patch("autocommit.utils.pr_utils.create_pr") as mock_create:
                with pytest.raises(RuntimeError, match="push failed"):
                    apply_commit(
                        self._make_msg(),
                        cwd="/tmp",
                        push_after=True,
                        auto_pr_enabled=True,
                    )

        mock_token.assert_not_called()
        mock_create.assert_not_called()

    @patch("autocommit.core.commit")
    @patch("autocommit.core.push")
    @patch("autocommit.core.current_branch", return_value="feature-xyz")
    def test_public_api_resolves_default_github_token(
        self, mock_branch, mock_push, mock_commit, monkeypatch
    ):
        """Direct apply_commit use resolves GITHUB_TOKEN via bundled config."""
        monkeypatch.setenv("GITHUB_TOKEN", "public-api-token")
        # Pass explicit _config to isolate from any AUTOCOMMIT_PARAMS env var
        # that might override bundled defaults.
        _test_cfg = {
            "git": {
                "auto_pr": {
                    "enabled": True,
                    "target_branch": "main",
                    "token_env_var": "GITHUB_TOKEN",
                },
            },
        }
        with patch(
            "autocommit.utils.pr_utils.create_pr",
            return_value="https://github.com/o/r/pull/7",
        ) as mock_create:
            url = apply_commit(
                self._make_msg(),
                cwd="/tmp",
                push_after=True,
                auto_pr_enabled=True,
                _config=_test_cfg,
            )

        assert url == "https://github.com/o/r/pull/7"
        assert mock_create.call_args.kwargs["token"] == "public-api-token"


class TestGenerateAndCommitAutoPR:
    @patch("autocommit.core.commit")
    @patch("autocommit.core.push")
    @patch("autocommit.core.current_branch", return_value="feature-xyz")
    @patch(
        "autocommit.core.generate_commit_message",
        return_value=CommitMessage("feat: integrated PR", "body"),
    )
    def test_configured_auto_pr_runs_through_public_workflow(
        self, mock_generate, mock_branch, mock_push, mock_commit, monkeypatch
    ):
        """generate_and_commit preserves config through token and PR creation."""
        cfg = {
            "llm": {},
            "git": {
                "push_after_commit": True,
                "push_set_upstream": True,
                "auto_pr": {
                    "enabled": True,
                    "target_branch": "develop",
                    "token_env_var": "CUSTOM_PR_TOKEN",
                },
            },
        }
        monkeypatch.setenv("CUSTOM_PR_TOKEN", "configured-token")
        with patch(
            "autocommit.utils.pr_utils.create_pr",
            return_value="https://github.com/o/r/pull/8",
        ) as mock_create:
            message = generate_and_commit(config=cfg, cwd="/tmp")

        assert message == CommitMessage("feat: integrated PR", "body")
        mock_push.assert_called_once_with("/tmp", set_upstream=True)
        mock_create.assert_called_once_with(
            repo_path="/tmp",
            token="configured-token",
            head_branch="feature-xyz",
            base_branch="develop",
            title="feat: integrated PR",
            body="body",
        )


class TestApplyCommitAutoMerge:
    """Tests for apply_commit with auto-merge enabled."""

    def _make_msg(self, subject="feat: add feature", body="Some body"):
        return CommitMessage(subject=subject, body=body)

    @patch("autocommit.core.commit")
    @patch("autocommit.core.push")
    @patch("autocommit.core.current_branch")
    def test_auto_merge_calls_create_pr_and_auto_merge(
        self, mock_branch, mock_push, mock_commit
    ):
        """apply_commit calls create_pr_and_auto_merge when auto_merge=True."""
        mock_branch.return_value = "feature-xyz"
        events = []
        mock_push.side_effect = lambda *args, **kwargs: events.append("push")

        with patch("autocommit.utils.pr_token.resolve_pr_token", return_value="ghp_token"):
            with patch(
                "autocommit.utils.pr_utils.create_pr_and_auto_merge",
                side_effect=lambda **kwargs: (
                    events.append("create_pr_and_auto_merge")
                    or "https://github.com/o/r/pull/1"
                ),
            ) as mock_auto_merge:
                with patch(
                    "autocommit.utils.pr_utils.create_pr",
                    side_effect=lambda **kwargs: (
                        events.append("create_pr")
                        or "https://github.com/o/r/pull/99"
                    ),
                ) as mock_create:
                    url = apply_commit(
                        self._make_msg(),
                        cwd="/tmp",
                        push_after=True,
                        auto_pr_enabled=True,
                        auto_pr_target_branch="main",
                        auto_pr_auto_merge=True,
                        _config={"git": {"auto_pr": {"enabled": True, "auto_merge": True}}},
                    )

        assert url == "https://github.com/o/r/pull/1"
        assert events == ["push", "create_pr_and_auto_merge"]
        mock_auto_merge.assert_called_once_with(
            repo_path="/tmp",
            token="ghp_token",
            head_branch="feature-xyz",
            base_branch="main",
            title="feat: add feature",
            body="Some body",
            auto_merge=True,
            merge_method="merge",
        )
        mock_create.assert_not_called()

    @patch("autocommit.core.commit")
    @patch("autocommit.core.push")
    @patch("autocommit.core.current_branch")
    def test_auto_merge_disabled_calls_plain_create_pr(
        self, mock_branch, mock_push, mock_commit
    ):
        """auto_merge=False calls create_pr (backward compat)."""
        mock_branch.return_value = "feature-xyz"
        events = []
        mock_push.side_effect = lambda *args, **kwargs: events.append("push")

        with patch("autocommit.utils.pr_token.resolve_pr_token", return_value="ghp_token"):
            with patch(
                "autocommit.utils.pr_utils.create_pr_and_auto_merge",
            ) as mock_auto_merge:
                with patch(
                    "autocommit.utils.pr_utils.create_pr",
                    side_effect=lambda **kwargs: (
                        events.append("create_pr")
                        or "https://github.com/o/r/pull/1"
                    ),
                ) as mock_create:
                    url = apply_commit(
                        self._make_msg(),
                        cwd="/tmp",
                        push_after=True,
                        auto_pr_enabled=True,
                        auto_pr_target_branch="main",
                        auto_pr_auto_merge=False,
                        _config={"git": {"auto_pr": {"enabled": True}}},
                    )

        assert url == "https://github.com/o/r/pull/1"
        assert events == ["push", "create_pr"]
        mock_create.assert_called_once()
        mock_auto_merge.assert_not_called()

    @patch("autocommit.core.commit")
    @patch("autocommit.core.push")
    @patch("autocommit.core.current_branch")
    def test_auto_merge_defaults_not_enabled(
        self, mock_branch, mock_push, mock_commit, monkeypatch
    ):
        """Default (no auto_merge kwarg) calls create_pr (not auto-merge)."""
        mock_branch.return_value = "feature-xyz"
        monkeypatch.setenv("GITHUB_TOKEN", "test-token")
        with patch("autocommit.utils.pr_utils.create_pr_and_auto_merge") as mock_auto_merge:
            with patch("autocommit.utils.pr_utils.create_pr", return_value="url") as mock_create:
                url = apply_commit(
                    self._make_msg(),
                    cwd="/tmp",
                    push_after=True,
                    auto_pr_enabled=True,
                    auto_pr_target_branch="main",
                    _config={"git": {"auto_pr": {"enabled": True}}},
                )

        assert url == "url"
        mock_create.assert_called_once()
        mock_auto_merge.assert_not_called()

    @patch("autocommit.core.commit")
    @patch("autocommit.core.push")
    @patch("autocommit.core.current_branch")
    def test_auto_merge_skipped_when_same_branch(
        self, mock_branch, mock_push, mock_commit, caplog
    ):
        """Same-branch skip takes priority over auto-merge."""
        mock_branch.return_value = "main"
        with patch("autocommit.utils.pr_utils.create_pr") as mock_create:
            with patch("autocommit.utils.pr_utils.create_pr_and_auto_merge") as mock_auto_merge:
                with caplog.at_level("INFO", logger="autocommit.core"):
                    url = apply_commit(
                        self._make_msg(),
                        cwd="/tmp",
                        push_after=True,
                        auto_pr_enabled=True,
                        auto_pr_target_branch="main",
                        auto_pr_auto_merge=True,
                        _config={"git": {"auto_pr": {"enabled": True}}},
                    )

        assert url is None
        mock_create.assert_not_called()
        mock_auto_merge.assert_not_called()
        assert "matches target branch" in caplog.text


class TestGenerateAndCommitAutoMerge:
    """Tests for generate_and_commit with auto-merge config."""

    @patch("autocommit.core.commit")
    @patch("autocommit.core.push")
    @patch("autocommit.core.current_branch", return_value="feature-xyz")
    @patch(
        "autocommit.core.generate_commit_message",
        return_value=CommitMessage("feat: auto-merge", "body"),
    )
    def test_configured_auto_merge_runs_through_workflow(
        self, mock_generate, mock_branch, mock_push, mock_commit, monkeypatch
    ):
        """generate_and_commit reads auto_merge config and passes to apply_commit."""
        cfg = {
            "llm": {},
            "git": {
                "push_after_commit": True,
                "push_set_upstream": True,
                "auto_pr": {
                    "enabled": True,
                    "target_branch": "main",
                    "token_env_var": "GITHUB_TOKEN",
                    "auto_merge": True,
                    "merge_method": "squash",
                    "merge_timeout": 300,
                },
            },
        }
        monkeypatch.setenv("GITHUB_TOKEN", "auto-merge-token")
        with patch(
            "autocommit.utils.pr_utils.create_pr_and_auto_merge",
            return_value="https://github.com/o/r/pull/42",
        ) as mock_auto_merge:
            message = generate_and_commit(config=cfg, cwd="/tmp")

        assert message == CommitMessage("feat: auto-merge", "body")
        mock_auto_merge.assert_called_once_with(
            repo_path="/tmp",
            token="auto-merge-token",
            head_branch="feature-xyz",
            base_branch="main",
            title="feat: auto-merge",
            body="body",
            auto_merge=True,
            merge_method="squash",
        )
