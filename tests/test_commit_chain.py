"""Tests for the LangGraph commit-message pipeline."""

from unittest.mock import MagicMock

import pytest

from autocommit.chains.commit_chain import _check_quality, build_graph

pytest.importorskip("langgraph.graph.state")


# ---------------------------------------------------------------------------
# build_graph
# ---------------------------------------------------------------------------


class TestBuildGraph:
    def test_returns_compiled_state_graph(self, mocker):
        mock_llm = mocker.MagicMock()
        graph = build_graph(mock_llm, None, {"git": {"quality": {}}})
        # CompiledStateGraph has a .invoke method
        assert hasattr(graph, "invoke")
        assert callable(graph.invoke)

    def test_compiles_without_error(self, mocker):
        mock_llm = mocker.MagicMock()
        # Should not raise
        graph = build_graph(
            mock_llm,
            None,
            {
                "git": {
                    "quality": {"max_retries": 3, "min_body_lines": 5, "check_boilerplate": False},
                    "conventional": False,
                }
            },
        )
        assert hasattr(graph, "invoke")

    def test_invoke_returns_subject_and_body(self, mocker):
        mock_llm = mocker.MagicMock()
        graph = build_graph(mock_llm, None, {"git": {"quality": {}}})

        # Mock the LLM call chain at the _call_with_fallback level
        mock_call = mocker.patch(
            "autocommit.chains.commit_chain._call_with_fallback",
            side_effect=[
                {"type": "feat", "reasoning": "adds feature", "confidence": 0.9},
                {"scope": "auth", "reasoning": "auth module"},
                {"subject": "feat(auth): add login", "body": "Added login endpoint.\nOAuth2 flow.\nTests included."},
            ],
        )

        state = {
            "raw_diff": "--- a/src/auth.py\n+++ b/src/auth.py\n@@ -1 +1 @@\n-base\n+new",
            "changed_files": ["src/auth.py"],
            "user_context": "",
            "max_subject_length": 72,
            "max_diff_chars": 8000,
            "max_changed_files": 20,
            "diff_truncated": False,
            "heuristic_type": "feat",
            "heuristic_scope": "",
            "ticket": "",
            "conventional": True,
            "primary_llm": mocker.MagicMock(),
            "fallback_llm": None,
            "diff_analysis": None,
            "draft_subject": "",
            "draft_body": "",
            "retry_count": 0,
            "critique_history": [],
            "errors": [],
            "quality_passed": False,
        }

        result = graph.invoke(state)
        assert isinstance(result, dict)
        assert result.get("draft_subject") == "feat(auth): add login"
        assert result.get("draft_body")
        assert mock_call.call_count >= 2  # at least type + scope


# ---------------------------------------------------------------------------
# _check_quality
# ---------------------------------------------------------------------------


class TestCheckQuality:
    def test_passes_valid_conventional_message(self):
        passed, critique = _check_quality(
            subject="feat(auth): add login endpoint",
            body="Added a login endpoint.\nImplements OAuth2.\nIncludes tests.",
            max_subject_length=72,
            conventional=True,
            min_body_lines=3,
            check_boilerplate=True,
        )
        assert passed is True
        assert critique == ""

    def test_passes_valid_message_no_scope(self):
        passed, critique = _check_quality(
            subject="fix: resolve null pointer",
            body="Fixed a null pointer exception.\nAdded null check.\nUpdated tests.",
            max_subject_length=72,
            conventional=True,
            min_body_lines=3,
            check_boilerplate=True,
        )
        assert passed is True
        assert critique == ""

    def test_fails_empty_subject(self):
        passed, critique = _check_quality(
            subject="",
            body="Some body content here.",
            max_subject_length=72,
            conventional=True,
            min_body_lines=1,
            check_boilerplate=False,
        )
        assert passed is False
        assert "Subject is empty" in critique

    def test_fails_subject_too_long(self):
        long_subject = "x" * 80
        passed, critique = _check_quality(
            subject=long_subject,
            body="Body content.\nMore body.\nEven more.",
            max_subject_length=50,
            conventional=False,
            min_body_lines=1,
            check_boilerplate=False,
        )
        assert passed is False
        assert "80 chars" in critique
        assert "50" in critique

    def test_fails_missing_conventional_format(self):
        passed, critique = _check_quality(
            subject="fixed the thing",
            body="Fixed the bug.\nAdded tests.\nAll green.",
            max_subject_length=72,
            conventional=True,
            min_body_lines=3,
            check_boilerplate=False,
        )
        assert passed is False
        assert "conventional format" in critique

    def test_passes_non_conventional_when_conventional_off(self):
        passed, critique = _check_quality(
            subject="fixed the thing",
            body="Fixed the bug.\nAdded tests.\nAll green.",
            max_subject_length=72,
            conventional=False,
            min_body_lines=3,
            check_boilerplate=False,
        )
        assert passed is True

    def test_fails_empty_body(self):
        passed, critique = _check_quality(
            subject="feat: add feature",
            body="",
            max_subject_length=72,
            conventional=True,
            min_body_lines=1,
            check_boilerplate=False,
        )
        assert passed is False
        assert "Body is empty" in critique

    def test_fails_too_few_body_lines(self):
        passed, critique = _check_quality(
            subject="feat: add feature",
            body="Just one line.",
            max_subject_length=72,
            conventional=True,
            min_body_lines=3,
            check_boilerplate=False,
        )
        assert passed is False
        assert "1 non-empty line" in critique

    def test_fails_boilerplate_detection(self):
        passed, critique = _check_quality(
            subject="fix: fix bug",
            body="Fixed a bug.\nMade some changes.\nUpdated tests.",
            max_subject_length=72,
            conventional=True,
            min_body_lines=3,
            check_boilerplate=True,
        )
        assert passed is False
        assert "Boilerplate" in critique

    def test_passes_less_than_min_body_lines_when_check_off(self):
        passed, critique = _check_quality(
            subject="feat: add feature",
            body="Short body.",
            max_subject_length=72,
            conventional=True,
            min_body_lines=5,
            check_boilerplate=False,
        )
        assert passed is False  # still fails because min_body_lines=5 but only 1
        # Actually this should still check min_body_lines regardless of check_boilerplate
        assert "1 non-empty line" in critique

    def test_boilerplate_not_detected_when_check_off(self):
        passed, critique = _check_quality(
            subject="fix: fix bug",
            body="Fixed a null pointer.\nAdded null guard.\nUpdated tests.",
            max_subject_length=72,
            conventional=True,
            min_body_lines=3,
            check_boilerplate=False,
        )
        assert passed is True  # boilerplate check is off, conventional passes, subject ok

    def test_accepts_exclamation_mark_conventional(self):
        passed, critique = _check_quality(
            subject="feat(auth)!: breaking change",
            body="Breaking change to auth.\nUpdated API.\nMigrated tokens.",
            max_subject_length=72,
            conventional=True,
            min_body_lines=3,
            check_boilerplate=False,
        )
        assert passed is True
