import pytest

pytest.importorskip("langchain_core.runnables", reason="LangChain not available")

from langchain_core.runnables import RunnableSequence
from autocommit.chains.commit_chain import build_chain


class TestBuildChain:
    def test_returns_runnable_sequence(self, mocker):
        mock_llm = mocker.MagicMock()
        chain = build_chain(mock_llm)
        assert isinstance(chain, RunnableSequence)
