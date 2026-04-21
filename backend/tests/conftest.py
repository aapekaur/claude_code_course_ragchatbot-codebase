import sys
import os
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def mock_rag_system():
    rag = MagicMock()
    rag.query.return_value = ("Test answer", [])
    rag.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["Python Basics", "Machine Learning"],
    }
    rag.session_manager.create_session.return_value = "test-session-id"
    return rag


@pytest.fixture
def sample_query_payload():
    return {"query": "What is Python?", "session_id": "session-abc"}


@pytest.fixture
def sample_sources():
    return [
        {"label": "Python Basics - Lesson 1", "url": "https://example.com/lesson1"},
        {"label": "Python Basics - Lesson 2", "url": None},
    ]
