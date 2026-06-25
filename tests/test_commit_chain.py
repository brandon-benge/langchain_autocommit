import pytest

pytest.importorskip("langchain_core.runnables", reason="LangChain not available")

from langchain_core.runnables import RunnableSequence
from autocommit.chains.commit_chain import _prepare_diff, build_chain


class TestBuildChain:
    def test_returns_runnable_sequence(self, mocker):
        mock_llm = mocker.MagicMock()
        chain = build_chain(mock_llm)
        assert isinstance(chain, RunnableSequence)

    def test_truncated_warning_in_prompt_when_truncated(self, mocker):
        mock_llm = mocker.MagicMock()
        chain = build_chain(mock_llm)
        inputs = {
            "type": "feat",
            "scope": "app",
            "ticket": "",
            "changed_files": ["a.py"],
            "diff_summary": "change",
            "max_subject_length": 72,
            "max_diff_chars": 8000,
            "max_changed_files": 20,
            "_diff_truncated": True,
            "user_context": "",
        }
        prompt = chain.steps[0] | chain.steps[1]
        rendered = prompt.invoke(inputs)
        assert "truncated" in rendered.text.lower()

    def test_no_truncation_warning_when_not_truncated(self, mocker):
        mock_llm = mocker.MagicMock()
        chain = build_chain(mock_llm)
        inputs = {
            "type": "feat",
            "scope": "app",
            "ticket": "",
            "changed_files": ["a.py"],
            "diff_summary": "change",
            "max_subject_length": 72,
            "max_diff_chars": 8000,
            "max_changed_files": 20,
            "_diff_truncated": False,
            "user_context": "",
        }
        prompt = chain.steps[0] | chain.steps[1]
        rendered = prompt.invoke(inputs)
        assert "truncated" not in rendered.text.lower()


class TestPrepareDiff:
    def test_no_truncation(self):
        result = _prepare_diff({"diff_summary": "short", "max_diff_chars": 8000})
        assert result == "short"

    def test_truncation(self):
        result = _prepare_diff({"diff_summary": "x" * 100, "max_diff_chars": 10})
        assert len(result) == 10
        assert result == "x" * 10

    def test_zero_max_disables_truncation(self):
        result = _prepare_diff({"diff_summary": "x" * 100, "max_diff_chars": 0})
        assert len(result) == 100

    def test_exact_fit(self):
        result = _prepare_diff({"diff_summary": "x" * 50, "max_diff_chars": 50})
        assert len(result) == 50

    def test_missing_max_diff_chars_defaults(self):
        result = _prepare_diff({"diff_summary": "x" * 9000})
        assert len(result) == 8000
