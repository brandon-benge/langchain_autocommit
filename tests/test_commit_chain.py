"""Tests for the LangGraph commit-message pipeline."""

import subprocess
import sys
import warnings
from unittest.mock import MagicMock

import pytest

from autocommit.chains.commit_chain import (
    _call_with_fallback,
    _check_quality,
    _safe_error_text,
    build_graph,
)

pytest.importorskip("langgraph.graph.state")


# ---------------------------------------------------------------------------
# Import behavior
# ---------------------------------------------------------------------------


def test_import_does_not_emit_allowed_objects_warning():
    script = """
import warnings
from langchain_core._api.deprecation import LangChainPendingDeprecationWarning

warnings.simplefilter("always", LangChainPendingDeprecationWarning)

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always", LangChainPendingDeprecationWarning)
    import autocommit.chains.commit_chain  # noqa: F401

messages = [str(item.message) for item in caught]
if any("allowed_objects" in message for message in messages):
    raise SystemExit("\\n".join(messages))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout


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
# _call_with_fallback / warning emission
# ---------------------------------------------------------------------------


class TestCallWithFallbackWarning:
    """Warning emission when the primary LLM fails and fallback is used."""

    @staticmethod
    def _prompt():
        from langchain_core.prompts import PromptTemplate

        return PromptTemplate.from_template("Respond: {changed_files}")

    def _make_chain(self, primary, fallback=None, **kwargs):
        return _call_with_fallback(
            self._prompt(),
            primary,
            fallback,
            task_label="analyze_type",
            changed_files="src/auth.py",
            **kwargs,
        )

    def test_warns_and_uses_fallback_on_exception(self):
        def primary(_inp):
            raise RuntimeError("boom")

        def fallback(_inp):
            return '{"type": "feat"}'

        with pytest.warns(UserWarning) as record:
            result = self._make_chain(primary, fallback)

        assert result == {"type": "feat"}
        assert len(record) == 1
        message = str(record[0].message)
        assert "analyze_type" in message
        assert "boom" in message
        assert "falling back" in message

    def test_warns_on_unparseable_primary_result(self):
        def primary(_inp):
            return "[1, 2, 3]"

        def fallback(_inp):
            return '{"type": "feat"}'

        with pytest.warns(UserWarning) as record:
            result = self._make_chain(primary, fallback)

        assert result == {"type": "feat"}
        assert len(record) == 1
        message = str(record[0].message)
        assert "analyze_type" in message
        assert "no usable result" in message
        assert "falling back" in message

    def test_no_warning_on_primary_success(self):
        def primary(_inp):
            return '{"type": "feat"}'

        def fallback(_inp):
            raise AssertionError("fallback must not be called")

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = self._make_chain(primary, fallback)

        assert result == {"type": "feat"}
        assert caught == []

    def test_no_warning_when_fallback_none(self):
        def primary(_inp):
            raise RuntimeError("boom")

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = self._make_chain(primary, None)

        assert result is None
        assert caught == []

    def test_warns_even_when_fallback_also_fails(self):
        def primary(_inp):
            raise RuntimeError("boom")

        def fallback(_inp):
            raise ConnectionError("fallback down")

        with pytest.warns(UserWarning) as record:
            result = self._make_chain(primary, fallback)

        assert result is None
        assert len(record) == 1
        message = str(record[0].message)
        assert "analyze_type" in message
        assert "boom" in message
        assert "falling back" in message

    def test_error_text_truncated(self):
        long_text = "x" * 5000

        def primary(_inp):
            raise RuntimeError(long_text)

        def fallback(_inp):
            return '{"type": "feat"}'

        with pytest.warns(UserWarning) as record:
            self._make_chain(primary, fallback)

        message = str(record[0].message)
        # Bound guards against dumping request bodies/credentials.
        assert len(message) < 400
        assert "..." in message

    def test_safe_error_text_truncates_and_strips(self):
        error = RuntimeError("   " + "x" * 5000)
        text = _safe_error_text(error)
        assert text.endswith("...")
        assert len(text) <= 304  # 300 chars + "..."
        assert text.startswith("RuntimeError: ")

    def test_on_error_callback_receives_enriched_reason(self):
        received: list[str] = []

        def primary(_inp):
            raise RuntimeError("boom")

        def fallback(_inp):
            return '{"type": "feat"}'

        with pytest.warns(UserWarning):
            result = _call_with_fallback(
                self._prompt(),
                primary,
                fallback,
                task_label="analyze_type",
                on_error=received.append,
                changed_files="src/auth.py",
            )

        assert result == {"type": "feat"}
        assert received == ["analyze_type: primary failed (RuntimeError: boom)"]


class TestGraphFallbackWarning:
    """Graph-level warning and state.errors enrichment on fallback."""

    @staticmethod
    def _make_primary():
        def primary_raises(_inp):
            raise RuntimeError("boom")

        return primary_raises

    @staticmethod
    def _make_fallback():
        def fallback_responds(inp):
            text = inp.to_string() if hasattr(inp, "to_string") else str(inp)
            if "determine the conventional commit type" in text:
                return '{"type": "feat", "reasoning": "adds feature", "confidence": 0.9}'
            if "most appropriate scope" in text:
                return '{"scope": "auth", "reasoning": "auth module"}'
            return (
                '{"subject": "feat(auth): add login", '
                '"body": "Added login.\\nOAuth2 flow.\\nTests included."}'
            )

        return fallback_responds

    def _state(self):
        return {
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
            "primary_llm": self._make_primary(),
            "fallback_llm": self._make_fallback(),
            "diff_analysis": None,
            "draft_subject": "",
            "draft_body": "",
            "retry_count": 0,
            "critique_history": [],
            "errors": [],
            "quality_passed": False,
        }

    def test_analyze_fallback_warning_identifies_subtask(self):
        graph = build_graph(
            self._make_primary(),
            self._make_fallback(),
            {"git": {"quality": {}}},
        )

        with pytest.warns(UserWarning) as record:
            result = graph.invoke(self._state())

        messages = [str(w.message) for w in record]
        # Concurrent sub-tasks: assert presence, never inter-thread order.
        assert any("analyze_type" in m and "falling back" in m for m in messages)
        assert any("analyze_scope" in m and "falling back" in m for m in messages)
        assert any("write_message" in m and "falling back" in m for m in messages)

    def test_state_errors_enriched_with_primary_failure(self):
        graph = build_graph(
            self._make_primary(),
            self._make_fallback(),
            {"git": {"quality": {}}},
        )

        with pytest.warns(UserWarning):
            result = graph.invoke(self._state())

        errors = result.get("errors", [])
        assert "analyze_type: primary failed (RuntimeError: boom)" in errors
        assert "analyze_scope: primary failed (RuntimeError: boom)" in errors
        assert "write_message: primary failed (RuntimeError: boom)" in errors


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
