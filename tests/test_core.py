import os
from unittest.mock import MagicMock, patch

import pytest

from autocommit.core import CommitMessage, _build_fallback_body, _bool, generate_commit_message


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
