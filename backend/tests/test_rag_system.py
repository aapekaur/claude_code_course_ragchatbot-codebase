"""
Tests for RAGSystem.query() in rag_system.py.

Covers: prompt wrapping, tool/tool_manager handoff to AIGenerator, source
retrieval and reset, session history persistence, and tool registration.
"""
import pytest
from unittest.mock import MagicMock, patch, call

from rag_system import RAGSystem


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_config():
    cfg = MagicMock()
    cfg.ANTHROPIC_API_KEY = "test-key"
    cfg.ANTHROPIC_MODEL = "test-model"
    cfg.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    cfg.CHROMA_PATH = "/tmp/test_chroma"
    cfg.MAX_RESULTS = 5
    cfg.MAX_HISTORY = 2
    cfg.CHUNK_SIZE = 800
    cfg.CHUNK_OVERLAP = 100
    return cfg


def _make_rag(ai_response="AI response", sources=None):
    """
    Return a RAGSystem with VectorStore, AIGenerator, DocumentProcessor,
    and SessionManager all mocked out. Tools are real but backed by the
    mocked VectorStore.
    """
    if sources is None:
        sources = []

    with (
        patch("rag_system.VectorStore") as MockVS,
        patch("rag_system.AIGenerator") as MockAI,
        patch("rag_system.DocumentProcessor"),
        patch("rag_system.SessionManager") as MockSM,
    ):
        mock_vs_instance = MagicMock()
        MockVS.return_value = mock_vs_instance

        mock_ai_instance = MagicMock()
        mock_ai_instance.generate_response.return_value = ai_response
        MockAI.return_value = mock_ai_instance

        mock_sm_instance = MagicMock()
        mock_sm_instance.get_conversation_history.return_value = None
        MockSM.return_value = mock_sm_instance

        rag = RAGSystem(_make_config())
        # Inject desired sources into search_tool so tool_manager returns them
        rag.search_tool.last_sources = sources

    return rag, mock_ai_instance, mock_sm_instance


# ---------------------------------------------------------------------------
# Return value shape
# ---------------------------------------------------------------------------

class TestQueryReturnValue:

    def test_returns_tuple_of_two(self):
        rag, _, _ = _make_rag()
        result = rag.query("What is Python?")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_first_element_is_ai_response(self):
        rag, _, _ = _make_rag(ai_response="AI says hello")
        response, _ = rag.query("Hello?")
        assert response == "AI says hello"

    def test_second_element_is_sources_list(self):
        sources = [{"label": "Course A - Lesson 1", "url": "https://example.com"}]
        rag, _, _ = _make_rag(sources=sources)
        _, returned_sources = rag.query("What is X?")
        assert returned_sources == sources


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

class TestQueryPromptWrapping:

    def test_query_wrapped_in_course_materials_prompt(self):
        rag, mock_ai, _ = _make_rag()
        rag.query("What is machine learning?")
        call_kwargs = mock_ai.generate_response.call_args[1]
        assert "What is machine learning?" in call_kwargs["query"]
        assert "course materials" in call_kwargs["query"].lower()

    def test_raw_query_not_passed_verbatim_as_prompt(self):
        """query() wraps the user question — it must not be the bare question."""
        rag, mock_ai, _ = _make_rag()
        rag.query("bare question")
        call_kwargs = mock_ai.generate_response.call_args[1]
        assert call_kwargs["query"] != "bare question"


# ---------------------------------------------------------------------------
# Tool handoff
# ---------------------------------------------------------------------------

class TestQueryToolHandoff:

    def test_passes_tool_definitions_to_ai_generator(self):
        rag, mock_ai, _ = _make_rag()
        rag.query("Q?")
        call_kwargs = mock_ai.generate_response.call_args[1]
        tools = call_kwargs.get("tools")
        assert tools is not None
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_passes_tool_manager_to_ai_generator(self):
        rag, mock_ai, _ = _make_rag()
        rag.query("Q?")
        call_kwargs = mock_ai.generate_response.call_args[1]
        assert call_kwargs.get("tool_manager") is rag.tool_manager

    def test_both_tools_registered_in_tool_manager(self):
        rag, _, _ = _make_rag()
        tool_names = list(rag.tool_manager.tools.keys())
        assert "search_course_content" in tool_names
        assert "get_course_outline" in tool_names

    def test_tool_definitions_include_search_and_outline(self):
        rag, mock_ai, _ = _make_rag()
        rag.query("Q?")
        call_kwargs = mock_ai.generate_response.call_args[1]
        tool_names = [t["name"] for t in call_kwargs["tools"]]
        assert "search_course_content" in tool_names
        assert "get_course_outline" in tool_names


# ---------------------------------------------------------------------------
# Source retrieval and reset
# ---------------------------------------------------------------------------

class TestSourceHandling:

    def test_sources_returned_from_tool_manager(self):
        sources = [{"label": "Lesson 1", "url": "https://example.com"}]
        rag, _, _ = _make_rag(sources=sources)
        _, returned = rag.query("Q?")
        assert returned == sources

    def test_sources_reset_after_query(self):
        sources = [{"label": "Lesson 1", "url": "https://example.com"}]
        rag, _, _ = _make_rag(sources=sources)
        rag.query("Q?")
        # After query, last_sources should be cleared
        assert rag.search_tool.last_sources == []

    def test_sources_empty_when_no_tool_called(self):
        rag, _, _ = _make_rag(sources=[])
        _, returned = rag.query("General question?")
        assert returned == []


# ---------------------------------------------------------------------------
# Session / conversation history
# ---------------------------------------------------------------------------

class TestSessionHandling:

    def test_exchange_saved_when_session_id_provided(self):
        rag, _, mock_sm = _make_rag(ai_response="The answer")
        rag.query("What is X?", session_id="session_1")
        mock_sm.add_exchange.assert_called_once_with("session_1", "What is X?", "The answer")

    def test_exchange_not_saved_when_no_session_id(self):
        rag, _, mock_sm = _make_rag()
        rag.query("What is X?", session_id=None)
        mock_sm.add_exchange.assert_not_called()

    def test_history_fetched_when_session_id_provided(self):
        rag, _, mock_sm = _make_rag()
        rag.query("Q?", session_id="session_1")
        mock_sm.get_conversation_history.assert_called_once_with("session_1")

    def test_history_not_fetched_when_no_session_id(self):
        rag, _, mock_sm = _make_rag()
        rag.query("Q?", session_id=None)
        mock_sm.get_conversation_history.assert_not_called()

    def test_history_passed_to_ai_generator(self):
        rag, mock_ai, mock_sm = _make_rag()
        mock_sm.get_conversation_history.return_value = "User: hi\nAssistant: hello"
        rag.query("Q?", session_id="session_1")
        call_kwargs = mock_ai.generate_response.call_args[1]
        assert call_kwargs.get("conversation_history") == "User: hi\nAssistant: hello"

    def test_none_history_passed_when_no_session(self):
        rag, mock_ai, _ = _make_rag()
        rag.query("Q?", session_id=None)
        call_kwargs = mock_ai.generate_response.call_args[1]
        assert call_kwargs.get("conversation_history") is None

    def test_original_query_stored_in_history_not_wrapped_prompt(self):
        """
        RAGSystem wraps the query for the AI, but stores the raw user query
        in session history so that conversation context is human-readable.
        """
        rag, _, mock_sm = _make_rag(ai_response="resp")
        rag.query("What is Python?", session_id="s1")
        stored_query = mock_sm.add_exchange.call_args[0][1]
        assert stored_query == "What is Python?"
        assert "Answer this question" not in stored_query
