"""
Tests for AIGenerator in ai_generator.py.

Covers: direct responses, tool-use dispatch, correct tool name/params forwarded
to ToolManager, loop call structure (tools included), synthesis call structure
(no tools), multi-round scenarios, exhausted rounds, and error handling.
"""
import pytest
from unittest.mock import MagicMock, patch, call

from ai_generator import AIGenerator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_generator():
    """Return an AIGenerator with a mocked Anthropic client."""
    with patch("ai_generator.anthropic.Anthropic") as MockAnthropic:
        mock_client = MagicMock()
        MockAnthropic.return_value = mock_client
        gen = AIGenerator(api_key="test-key", model="test-model")
        gen._client = mock_client  # keep direct reference for assertions
        return gen, mock_client


def _text_response(text="answer text"):
    resp = MagicMock()
    resp.stop_reason = "end_turn"
    resp.content = [MagicMock(type="text", text=text)]
    return resp


def _tool_use_response(tool_name, tool_id, tool_input):
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.id = tool_id
    block.input = tool_input

    resp = MagicMock()
    resp.stop_reason = "tool_use"
    resp.content = [block]
    return resp


def _setup_single_round(tool_name="search_course_content", tool_input=None, final_text="Final answer."):
    """
    Wire a generator for exactly one tool-calling round.
    Sequence: initial(tool_use) -> loop_call(end_turn).
    Returns (gen, mock_client, mock_tool_manager).
    """
    if tool_input is None:
        tool_input = {"query": "Python"}

    with patch("ai_generator.anthropic.Anthropic") as MockAnthropic:
        mock_client = MagicMock()
        MockAnthropic.return_value = mock_client
        mock_client.messages.create.side_effect = [
            _tool_use_response(tool_name, "tid_1", tool_input),
            _text_response(final_text),
        ]
        gen = AIGenerator(api_key="k", model="m")

    mock_tm = MagicMock()
    mock_tm.execute_tool.return_value = "search results"
    return gen, mock_client, mock_tm


def _setup_two_rounds_natural_stop(final_text="Two-round answer."):
    """
    Wire a generator for two tool-calling rounds that end naturally.
    Sequence: initial(tool_use) -> loop_call_1(tool_use) -> loop_call_2(end_turn).
    Returns (gen, mock_client, mock_tool_manager).
    """
    with patch("ai_generator.anthropic.Anthropic") as MockAnthropic:
        mock_client = MagicMock()
        MockAnthropic.return_value = mock_client
        mock_client.messages.create.side_effect = [
            _tool_use_response("search_course_content", "tid_1", {"query": "first"}),
            _tool_use_response("search_course_content", "tid_2", {"query": "second"}),
            _text_response(final_text),
        ]
        gen = AIGenerator(api_key="k", model="m")

    mock_tm = MagicMock()
    mock_tm.execute_tool.return_value = "results"
    return gen, mock_client, mock_tm


def _setup_exhausted_rounds(final_text="Exhausted synthesis."):
    """
    Wire a generator where Claude wants tools three times (exceeds MAX_TOOL_ROUNDS=2).
    Sequence: initial(tool_use) -> loop_1(tool_use) -> loop_2(tool_use) -> synthesis(end_turn).
    Returns (gen, mock_client, mock_tool_manager).
    """
    with patch("ai_generator.anthropic.Anthropic") as MockAnthropic:
        mock_client = MagicMock()
        MockAnthropic.return_value = mock_client
        mock_client.messages.create.side_effect = [
            _tool_use_response("search_course_content", "tid_1", {"query": "q1"}),
            _tool_use_response("search_course_content", "tid_2", {"query": "q2"}),
            _tool_use_response("search_course_content", "tid_3", {"query": "q3"}),
            _text_response(final_text),
        ]
        gen = AIGenerator(api_key="k", model="m")

    mock_tm = MagicMock()
    mock_tm.execute_tool.return_value = "results"
    return gen, mock_client, mock_tm


# ---------------------------------------------------------------------------
# Direct (no-tool-use) response
# ---------------------------------------------------------------------------

class TestDirectResponse:

    def test_returns_text_from_content(self):
        with patch("ai_generator.anthropic.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            MockAnthropic.return_value = mock_client
            mock_client.messages.create.return_value = _text_response("Hello!")
            gen = AIGenerator(api_key="k", model="m")
            result = gen.generate_response("Hi?")
        assert result == "Hello!"

    def test_no_tool_manager_call_on_end_turn(self):
        with patch("ai_generator.anthropic.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            MockAnthropic.return_value = mock_client
            mock_client.messages.create.return_value = _text_response("direct")
            mock_tm = MagicMock()
            gen = AIGenerator(api_key="k", model="m")
            gen.generate_response("Q?", tool_manager=mock_tm)
        mock_tm.execute_tool.assert_not_called()

    def test_api_called_with_user_query(self):
        with patch("ai_generator.anthropic.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            MockAnthropic.return_value = mock_client
            mock_client.messages.create.return_value = _text_response()
            gen = AIGenerator(api_key="k", model="m")
            gen.generate_response("What is Python?")
        call_kwargs = mock_client.messages.create.call_args[1]
        messages = call_kwargs["messages"]
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "What is Python?"

    def test_tools_included_in_api_call_when_provided(self):
        with patch("ai_generator.anthropic.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            MockAnthropic.return_value = mock_client
            mock_client.messages.create.return_value = _text_response()
            gen = AIGenerator(api_key="k", model="m")
            tools = [{"name": "search_course_content", "input_schema": {}}]
            gen.generate_response("Q?", tools=tools)
        call_kwargs = mock_client.messages.create.call_args[1]
        assert "tools" in call_kwargs
        assert call_kwargs["tools"] == tools

    def test_tools_not_in_api_call_when_not_provided(self):
        with patch("ai_generator.anthropic.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            MockAnthropic.return_value = mock_client
            mock_client.messages.create.return_value = _text_response()
            gen = AIGenerator(api_key="k", model="m")
            gen.generate_response("Q?")
        call_kwargs = mock_client.messages.create.call_args[1]
        assert "tools" not in call_kwargs


# ---------------------------------------------------------------------------
# Conversation history
# ---------------------------------------------------------------------------

class TestConversationHistory:

    def test_history_appended_to_system_prompt(self):
        with patch("ai_generator.anthropic.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            MockAnthropic.return_value = mock_client
            mock_client.messages.create.return_value = _text_response()
            gen = AIGenerator(api_key="k", model="m")
            gen.generate_response("Q?", conversation_history="User: hi\nAssistant: hello")
        call_kwargs = mock_client.messages.create.call_args[1]
        assert "User: hi\nAssistant: hello" in call_kwargs["system"]
        assert "Previous conversation" in call_kwargs["system"]

    def test_no_history_prefix_when_none(self):
        with patch("ai_generator.anthropic.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            MockAnthropic.return_value = mock_client
            mock_client.messages.create.return_value = _text_response()
            gen = AIGenerator(api_key="k", model="m")
            gen.generate_response("Q?", conversation_history=None)
        call_kwargs = mock_client.messages.create.call_args[1]
        assert "Previous conversation" not in call_kwargs["system"]


# ---------------------------------------------------------------------------
# Single-round tool use
# ---------------------------------------------------------------------------

class TestSingleRoundToolUse:

    def test_execute_tool_called_on_tool_use(self):
        gen, mock_client, mock_tm = _setup_single_round(
            tool_name="search_course_content",
            tool_input={"query": "Python"},
        )
        with patch("ai_generator.anthropic.Anthropic"):
            gen.generate_response(
                "Python?",
                tools=[{"name": "search_course_content"}],
                tool_manager=mock_tm,
            )
        mock_tm.execute_tool.assert_called_once()

    def test_execute_tool_called_with_correct_tool_name(self):
        gen, mock_client, mock_tm = _setup_single_round(
            tool_name="search_course_content",
            tool_input={"query": "Python"},
        )
        with patch("ai_generator.anthropic.Anthropic"):
            gen.generate_response(
                "Python?",
                tools=[{"name": "search_course_content"}],
                tool_manager=mock_tm,
            )
        assert mock_tm.execute_tool.call_args[0][0] == "search_course_content"

    def test_execute_tool_called_with_correct_input_params(self):
        gen, mock_client, mock_tm = _setup_single_round(
            tool_name="search_course_content",
            tool_input={"query": "Python", "course_name": "Intro"},
        )
        with patch("ai_generator.anthropic.Anthropic"):
            gen.generate_response(
                "Python?",
                tools=[{"name": "search_course_content"}],
                tool_manager=mock_tm,
            )
        call_kwargs = mock_tm.execute_tool.call_args[1]
        assert call_kwargs.get("query") == "Python"
        assert call_kwargs.get("course_name") == "Intro"

    def test_final_text_returned_after_tool(self):
        gen, mock_client, mock_tm = _setup_single_round(final_text="Final answer.")
        with patch("ai_generator.anthropic.Anthropic"):
            result = gen.generate_response(
                "Q?",
                tools=[{"name": "search_course_content"}],
                tool_manager=mock_tm,
            )
        assert result == "Final answer."

    def test_two_api_calls_made_on_tool_use(self):
        """One tool round (natural stop) → 2 API calls: initial + loop call."""
        gen, mock_client, mock_tm = _setup_single_round()
        with patch("ai_generator.anthropic.Anthropic"):
            gen.generate_response(
                "Q?",
                tools=[{"name": "search_course_content"}],
                tool_manager=mock_tm,
            )
        assert mock_client.messages.create.call_count == 2

    def test_loop_api_call_includes_tools(self):
        """
        The API call made inside the tool loop must include tools so Claude
        can decide to search again in a follow-up round.
        """
        gen, mock_client, mock_tm = _setup_single_round()
        tools = [{"name": "search_course_content"}]
        with patch("ai_generator.anthropic.Anthropic"):
            gen.generate_response("Q?", tools=tools, tool_manager=mock_tm)
        loop_call_kwargs = mock_client.messages.create.call_args_list[1][1]
        assert "tools" in loop_call_kwargs
        assert loop_call_kwargs["tools"] == tools

    def test_tool_result_appended_as_user_message(self):
        """
        The Anthropic API requires tool results to be submitted as a 'user'
        role message containing tool_result blocks.
        """
        gen, mock_client, mock_tm = _setup_single_round(tool_input={"query": "Python"})
        mock_tm.execute_tool.return_value = "result text"

        with patch("ai_generator.anthropic.Anthropic"):
            gen.generate_response(
                "Q?",
                tools=[{"name": "search_course_content"}],
                tool_manager=mock_tm,
            )

        loop_call_kwargs = mock_client.messages.create.call_args_list[1][1]
        messages = loop_call_kwargs["messages"]
        tool_result_message = messages[-1]
        assert tool_result_message["role"] == "user"
        content = tool_result_message["content"]
        assert isinstance(content, list)
        assert content[0]["type"] == "tool_result"
        assert content[0]["content"] == "result text"

    def test_tool_result_id_matches_tool_use_id(self):
        gen, mock_client, mock_tm = _setup_single_round()
        with patch("ai_generator.anthropic.Anthropic"):
            gen.generate_response(
                "Q?",
                tools=[{"name": "search_course_content"}],
                tool_manager=mock_tm,
            )
        loop_call_kwargs = mock_client.messages.create.call_args_list[1][1]
        messages = loop_call_kwargs["messages"]
        tool_result_msg = messages[-1]
        assert tool_result_msg["content"][0]["tool_use_id"] == "tid_1"

    def test_no_tool_use_when_stop_reason_end_turn(self):
        with patch("ai_generator.anthropic.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            MockAnthropic.return_value = mock_client
            mock_client.messages.create.return_value = _text_response("direct")
            mock_tm = MagicMock()
            gen = AIGenerator(api_key="k", model="m")
            gen.generate_response(
                "Q?",
                tools=[{"name": "search_course_content"}],
                tool_manager=mock_tm,
            )
        assert mock_client.messages.create.call_count == 1
        mock_tm.execute_tool.assert_not_called()

    def test_tool_error_does_not_crash(self):
        """An error string returned by execute_tool is passed as tool_result content;
        the loop continues and a valid text response is returned."""
        gen, mock_client, mock_tm = _setup_single_round(final_text="Sorry, nothing found.")
        mock_tm.execute_tool.return_value = "No course found matching 'XYZ'"
        with patch("ai_generator.anthropic.Anthropic"):
            result = gen.generate_response(
                "Q?",
                tools=[{"name": "search_course_content"}],
                tool_manager=mock_tm,
            )
        assert isinstance(result, str)
        assert result == "Sorry, nothing found."


# ---------------------------------------------------------------------------
# Multi-round tool use
# ---------------------------------------------------------------------------

class TestMultiRoundToolUse:

    def test_two_rounds_three_api_calls(self):
        """Two tool rounds that end naturally → 3 API calls total."""
        gen, mock_client, mock_tm = _setup_two_rounds_natural_stop()
        with patch("ai_generator.anthropic.Anthropic"):
            gen.generate_response(
                "Q?",
                tools=[{"name": "search_course_content"}],
                tool_manager=mock_tm,
            )
        assert mock_client.messages.create.call_count == 3

    def test_two_rounds_execute_tool_twice(self):
        """Two tool rounds → execute_tool is called exactly twice."""
        gen, mock_client, mock_tm = _setup_two_rounds_natural_stop()
        with patch("ai_generator.anthropic.Anthropic"):
            gen.generate_response(
                "Q?",
                tools=[{"name": "search_course_content"}],
                tool_manager=mock_tm,
            )
        assert mock_tm.execute_tool.call_count == 2

    def test_two_rounds_returns_final_text(self):
        gen, mock_client, mock_tm = _setup_two_rounds_natural_stop(final_text="Multi-round answer.")
        with patch("ai_generator.anthropic.Anthropic"):
            result = gen.generate_response(
                "Q?",
                tools=[{"name": "search_course_content"}],
                tool_manager=mock_tm,
            )
        assert result == "Multi-round answer."

    def test_exhausted_rounds_four_api_calls(self):
        """Rounds exhausted (Claude wants 3 tool calls, MAX=2) → 4 API calls total."""
        gen, mock_client, mock_tm = _setup_exhausted_rounds()
        with patch("ai_generator.anthropic.Anthropic"):
            gen.generate_response(
                "Q?",
                tools=[{"name": "search_course_content"}],
                tool_manager=mock_tm,
            )
        assert mock_client.messages.create.call_count == 4

    def test_exhausted_rounds_execute_tool_three_times(self):
        """Rounds exhausted → execute_tool called for all 3 tool-use blocks."""
        gen, mock_client, mock_tm = _setup_exhausted_rounds()
        with patch("ai_generator.anthropic.Anthropic"):
            gen.generate_response(
                "Q?",
                tools=[{"name": "search_course_content"}],
                tool_manager=mock_tm,
            )
        assert mock_tm.execute_tool.call_count == 3

    def test_synthesis_call_excludes_tools(self):
        """When rounds are exhausted, the final synthesis call must not include tools."""
        gen, mock_client, mock_tm = _setup_exhausted_rounds()
        with patch("ai_generator.anthropic.Anthropic"):
            gen.generate_response(
                "Q?",
                tools=[{"name": "search_course_content"}],
                tool_manager=mock_tm,
            )
        synthesis_call_kwargs = mock_client.messages.create.call_args_list[3][1]
        assert "tools" not in synthesis_call_kwargs

    def test_exhausted_rounds_returns_synthesis_text(self):
        gen, mock_client, mock_tm = _setup_exhausted_rounds(final_text="Synthesized answer.")
        with patch("ai_generator.anthropic.Anthropic"):
            result = gen.generate_response(
                "Q?",
                tools=[{"name": "search_course_content"}],
                tool_manager=mock_tm,
            )
        assert result == "Synthesized answer."
