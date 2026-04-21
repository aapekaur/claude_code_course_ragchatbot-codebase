"""
Tests for CourseSearchTool.execute() in search_tools.py.

Covers: filter delegation, empty/error result paths, result formatting,
source tracking (label, URL), and stale-source edge cases.
"""
import pytest
from unittest.mock import MagicMock, call

from search_tools import CourseSearchTool, ToolManager
from vector_store import SearchResults


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_results(docs, metas, distances=None):
    if distances is None:
        distances = [0.1] * len(docs)
    return SearchResults(documents=docs, metadata=metas, distances=distances)


def _make_empty():
    return SearchResults(documents=[], metadata=[], distances=[])


def _make_error(msg="Something went wrong"):
    return SearchResults.empty(msg)


def _make_tool(store=None):
    if store is None:
        store = MagicMock()
    return CourseSearchTool(store), store


# ---------------------------------------------------------------------------
# Filter delegation
# ---------------------------------------------------------------------------

class TestFilterDelegation:

    def test_bare_query_passes_none_filters(self):
        tool, store = _make_tool()
        store.search.return_value = _make_empty()
        tool.execute(query="Python")
        store.search.assert_called_once_with(query="Python", course_name=None, lesson_number=None)

    def test_course_name_forwarded(self):
        tool, store = _make_tool()
        store.search.return_value = _make_empty()
        tool.execute(query="loops", course_name="Python Basics")
        store.search.assert_called_once_with(query="loops", course_name="Python Basics", lesson_number=None)

    def test_lesson_number_forwarded(self):
        tool, store = _make_tool()
        store.search.return_value = _make_empty()
        tool.execute(query="loops", lesson_number=3)
        store.search.assert_called_once_with(query="loops", course_name=None, lesson_number=3)

    def test_both_filters_forwarded(self):
        tool, store = _make_tool()
        store.search.return_value = _make_empty()
        tool.execute(query="loops", course_name="Python Basics", lesson_number=3)
        store.search.assert_called_once_with(query="loops", course_name="Python Basics", lesson_number=3)


# ---------------------------------------------------------------------------
# Empty results
# ---------------------------------------------------------------------------

class TestEmptyResults:

    def test_bare_empty_message(self):
        tool, store = _make_tool()
        store.search.return_value = _make_empty()
        result = tool.execute(query="xyz")
        assert result == "No relevant content found."

    def test_empty_with_course_name_in_message(self):
        tool, store = _make_tool()
        store.search.return_value = _make_empty()
        result = tool.execute(query="xyz", course_name="MCP Course")
        assert "No relevant content found" in result
        assert "MCP Course" in result

    def test_empty_with_lesson_number_in_message(self):
        tool, store = _make_tool()
        store.search.return_value = _make_empty()
        result = tool.execute(query="xyz", lesson_number=5)
        assert "No relevant content found" in result
        assert "5" in result

    def test_empty_with_both_filters_in_message(self):
        tool, store = _make_tool()
        store.search.return_value = _make_empty()
        result = tool.execute(query="xyz", course_name="MCP Course", lesson_number=5)
        assert "No relevant content found" in result
        assert "MCP Course" in result


# ---------------------------------------------------------------------------
# Error results
# ---------------------------------------------------------------------------

class TestErrorResults:

    def test_error_string_returned_verbatim(self):
        tool, store = _make_tool()
        store.search.return_value = _make_error("No course found matching 'XYZ'")
        result = tool.execute(query="topic", course_name="XYZ")
        assert result == "No course found matching 'XYZ'"

    def test_search_exception_error_propagated(self):
        tool, store = _make_tool()
        store.search.return_value = _make_error(
            "Search error: number of requested results 5 is greater than number of elements in index 2"
        )
        result = tool.execute(query="topic")
        assert "Search error" in result


# ---------------------------------------------------------------------------
# Result formatting
# ---------------------------------------------------------------------------

class TestResultFormatting:

    def test_single_result_header_with_lesson(self):
        tool, store = _make_tool()
        store.search.return_value = _make_results(
            docs=["Python is interpreted."],
            metas=[{"course_title": "Python Basics", "lesson_number": 2}],
        )
        store.get_lesson_link.return_value = None
        result = tool.execute(query="Python")
        assert "[Python Basics - Lesson 2]" in result
        assert "Python is interpreted." in result

    def test_single_result_no_lesson_number_in_header(self):
        tool, store = _make_tool()
        store.search.return_value = _make_results(
            docs=["Intro content"],
            metas=[{"course_title": "Python Basics"}],  # lesson_number absent
        )
        result = tool.execute(query="intro")
        assert "[Python Basics]" in result
        assert "Lesson" not in result
        assert "Intro content" in result

    def test_missing_course_title_defaults_to_unknown(self):
        tool, store = _make_tool()
        store.search.return_value = _make_results(
            docs=["content"],
            metas=[{"lesson_number": 1}],  # course_title absent
        )
        store.get_lesson_link.return_value = None
        result = tool.execute(query="q")
        assert "unknown" in result

    def test_multiple_results_all_present(self):
        tool, store = _make_tool()
        store.search.return_value = _make_results(
            docs=["Content A", "Content B"],
            metas=[
                {"course_title": "Course A", "lesson_number": 1},
                {"course_title": "Course B", "lesson_number": 2},
            ],
        )
        store.get_lesson_link.return_value = None
        result = tool.execute(query="q")
        assert "Content A" in result
        assert "Content B" in result
        assert "Course A" in result
        assert "Course B" in result

    def test_multiple_results_separated(self):
        tool, store = _make_tool()
        store.search.return_value = _make_results(
            docs=["Content A", "Content B"],
            metas=[
                {"course_title": "Course A", "lesson_number": 1},
                {"course_title": "Course B", "lesson_number": 2},
            ],
        )
        store.get_lesson_link.return_value = None
        result = tool.execute(query="q")
        # Double newline separates chunks
        assert "\n\n" in result


# ---------------------------------------------------------------------------
# Source tracking
# ---------------------------------------------------------------------------

class TestSourceTracking:

    def test_last_sources_initially_empty(self):
        tool, _ = _make_tool()
        assert tool.last_sources == []

    def test_sources_populated_after_successful_search(self):
        tool, store = _make_tool()
        store.search.return_value = _make_results(
            docs=["content"],
            metas=[{"course_title": "My Course", "lesson_number": 1}],
        )
        store.get_lesson_link.return_value = "https://example.com/lesson"
        tool.execute(query="q")
        assert len(tool.last_sources) == 1
        assert tool.last_sources[0]["label"] == "My Course - Lesson 1"
        assert tool.last_sources[0]["url"] == "https://example.com/lesson"

    def test_source_label_without_lesson_number(self):
        tool, store = _make_tool()
        store.search.return_value = _make_results(
            docs=["content"],
            metas=[{"course_title": "My Course"}],
        )
        tool.execute(query="q")
        assert tool.last_sources[0]["label"] == "My Course"

    def test_source_url_is_none_when_no_lesson_number(self):
        tool, store = _make_tool()
        store.search.return_value = _make_results(
            docs=["content"],
            metas=[{"course_title": "My Course"}],
        )
        tool.execute(query="q")
        assert tool.last_sources[0]["url"] is None
        store.get_lesson_link.assert_not_called()

    def test_get_lesson_link_called_with_correct_args(self):
        tool, store = _make_tool()
        store.search.return_value = _make_results(
            docs=["content"],
            metas=[{"course_title": "My Course", "lesson_number": 3}],
        )
        store.get_lesson_link.return_value = "https://example.com/3"
        tool.execute(query="q")
        store.get_lesson_link.assert_called_once_with("My Course", 3)

    def test_multiple_sources_tracked(self):
        tool, store = _make_tool()
        store.search.return_value = _make_results(
            docs=["doc1", "doc2"],
            metas=[
                {"course_title": "Course A", "lesson_number": 1},
                {"course_title": "Course B", "lesson_number": 2},
            ],
        )
        store.get_lesson_link.return_value = None
        tool.execute(query="q")
        assert len(tool.last_sources) == 2

    def test_last_sources_not_cleared_when_empty_results(self):
        """
        BUG: last_sources is only updated inside _format_results.
        If execute() returns early (empty results), the previous value persists.
        This can cause stale sources to be returned to the caller within
        the same query if the tool is somehow called twice.
        """
        tool, store = _make_tool()

        # First call: populate sources
        store.search.return_value = _make_results(
            docs=["content"],
            metas=[{"course_title": "Course A", "lesson_number": 1}],
        )
        store.get_lesson_link.return_value = "https://example.com"
        tool.execute(query="first")
        assert len(tool.last_sources) == 1

        # Second call: empty results — sources should be cleared
        store.search.return_value = _make_empty()
        tool.execute(query="second")
        # BUG: last_sources still contains stale data from first call
        assert tool.last_sources == [], (
            "BUG: last_sources was not cleared when execute() returned early "
            "due to empty results. It still contains stale source data."
        )

    def test_last_sources_not_cleared_when_error_results(self):
        """
        BUG: same stale-source issue when execute() returns early due to an error.
        """
        tool, store = _make_tool()

        # First call: populate sources
        store.search.return_value = _make_results(
            docs=["content"],
            metas=[{"course_title": "Course A", "lesson_number": 1}],
        )
        store.get_lesson_link.return_value = "https://example.com"
        tool.execute(query="first")
        assert len(tool.last_sources) == 1

        # Second call: error — sources should be cleared
        store.search.return_value = _make_error("No course found matching 'XYZ'")
        tool.execute(query="second", course_name="XYZ")
        # BUG: last_sources still contains stale data
        assert tool.last_sources == [], (
            "BUG: last_sources was not cleared when execute() returned early "
            "due to an error result."
        )


# ---------------------------------------------------------------------------
# ToolManager integration
# ---------------------------------------------------------------------------

class TestToolManager:

    def test_registered_tool_accessible_by_name(self):
        store = MagicMock()
        store.search.return_value = _make_empty()
        tool = CourseSearchTool(store)
        manager = ToolManager()
        manager.register_tool(tool)
        result = manager.execute_tool("search_course_content", query="test")
        assert "No relevant content found" in result

    def test_get_last_sources_returns_tool_sources(self):
        store = MagicMock()
        store.search.return_value = _make_results(
            docs=["content"],
            metas=[{"course_title": "C", "lesson_number": 1}],
        )
        store.get_lesson_link.return_value = "https://example.com"
        tool = CourseSearchTool(store)
        manager = ToolManager()
        manager.register_tool(tool)
        manager.execute_tool("search_course_content", query="q")
        sources = manager.get_last_sources()
        assert len(sources) == 1

    def test_reset_sources_clears_all(self):
        store = MagicMock()
        store.search.return_value = _make_results(
            docs=["content"],
            metas=[{"course_title": "C", "lesson_number": 1}],
        )
        store.get_lesson_link.return_value = "https://example.com"
        tool = CourseSearchTool(store)
        manager = ToolManager()
        manager.register_tool(tool)
        manager.execute_tool("search_course_content", query="q")
        manager.reset_sources()
        assert manager.get_last_sources() == []
