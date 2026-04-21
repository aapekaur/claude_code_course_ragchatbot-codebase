"""
Tests for FastAPI endpoints in app.py.

Uses a minimal test app that mirrors the real routes without mounting
static files (which don't exist in the test environment).
"""
import pytest
from unittest.mock import MagicMock
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from pydantic import BaseModel
from typing import List, Optional

from models import SourceItem


# ---------------------------------------------------------------------------
# Minimal test app (mirrors app.py routes, no static file mount)
# ---------------------------------------------------------------------------

def _make_test_app(rag_system):
    """Return a TestClient wrapping a minimal FastAPI app with injected rag_system."""

    app = FastAPI()
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    class QueryRequest(BaseModel):
        query: str
        session_id: Optional[str] = None

    class QueryResponse(BaseModel):
        answer: str
        sources: List[SourceItem]
        session_id: str

    class CourseStats(BaseModel):
        total_courses: int
        course_titles: List[str]

    class ClearSessionRequest(BaseModel):
        session_id: Optional[str] = None

    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id
            if not session_id:
                session_id = rag_system.session_manager.create_session()
            answer, sources = rag_system.query(request.query, session_id)
            return QueryResponse(answer=answer, sources=sources, session_id=session_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/clear-session")
    async def clear_session(request: ClearSessionRequest):
        if request.session_id:
            rag_system.session_manager.clear_session(request.session_id)
        return {"status": "ok"}

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"],
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return TestClient(app)


# ---------------------------------------------------------------------------
# POST /api/query
# ---------------------------------------------------------------------------

class TestQueryEndpoint:

    def test_returns_200_with_valid_payload(self, mock_rag_system, sample_query_payload):
        client = _make_test_app(mock_rag_system)
        response = client.post("/api/query", json=sample_query_payload)
        assert response.status_code == 200

    def test_response_contains_answer(self, mock_rag_system, sample_query_payload):
        mock_rag_system.query.return_value = ("Test answer", [])
        client = _make_test_app(mock_rag_system)
        data = client.post("/api/query", json=sample_query_payload).json()
        assert data["answer"] == "Test answer"

    def test_response_contains_session_id(self, mock_rag_system, sample_query_payload):
        client = _make_test_app(mock_rag_system)
        data = client.post("/api/query", json=sample_query_payload).json()
        assert "session_id" in data
        assert data["session_id"] == sample_query_payload["session_id"]

    def test_session_created_when_not_provided(self, mock_rag_system):
        client = _make_test_app(mock_rag_system)
        response = client.post("/api/query", json={"query": "Hello?"})
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-session-id"

    def test_sources_returned_in_response(self, mock_rag_system, sample_sources):
        mock_rag_system.query.return_value = ("Answer", [
            {"label": "Python Basics - Lesson 1", "url": "https://example.com/lesson1"},
        ])
        client = _make_test_app(mock_rag_system)
        data = client.post("/api/query", json={"query": "Q?"}).json()
        assert isinstance(data["sources"], list)
        assert len(data["sources"]) == 1
        assert data["sources"][0]["label"] == "Python Basics - Lesson 1"

    def test_empty_sources_list_returned(self, mock_rag_system):
        mock_rag_system.query.return_value = ("General answer", [])
        client = _make_test_app(mock_rag_system)
        data = client.post("/api/query", json={"query": "Q?"}).json()
        assert data["sources"] == []

    def test_rag_query_called_with_correct_args(self, mock_rag_system, sample_query_payload):
        client = _make_test_app(mock_rag_system)
        client.post("/api/query", json=sample_query_payload)
        mock_rag_system.query.assert_called_once_with(
            sample_query_payload["query"], sample_query_payload["session_id"]
        )

    def test_missing_query_field_returns_422(self, mock_rag_system):
        client = _make_test_app(mock_rag_system)
        response = client.post("/api/query", json={"session_id": "abc"})
        assert response.status_code == 422

    def test_rag_exception_returns_500(self, mock_rag_system):
        mock_rag_system.query.side_effect = RuntimeError("Something went wrong")
        client = _make_test_app(mock_rag_system)
        response = client.post("/api/query", json={"query": "Q?"})
        assert response.status_code == 500

    def test_500_detail_contains_error_message(self, mock_rag_system):
        mock_rag_system.query.side_effect = RuntimeError("DB unavailable")
        client = _make_test_app(mock_rag_system)
        data = client.post("/api/query", json={"query": "Q?"}).json()
        assert "DB unavailable" in data["detail"]


# ---------------------------------------------------------------------------
# GET /api/courses
# ---------------------------------------------------------------------------

class TestCoursesEndpoint:

    def test_returns_200(self, mock_rag_system):
        client = _make_test_app(mock_rag_system)
        response = client.get("/api/courses")
        assert response.status_code == 200

    def test_response_contains_total_courses(self, mock_rag_system):
        client = _make_test_app(mock_rag_system)
        data = client.get("/api/courses").json()
        assert data["total_courses"] == 2

    def test_response_contains_course_titles(self, mock_rag_system):
        client = _make_test_app(mock_rag_system)
        data = client.get("/api/courses").json()
        assert data["course_titles"] == ["Python Basics", "Machine Learning"]

    def test_analytics_exception_returns_500(self, mock_rag_system):
        mock_rag_system.get_course_analytics.side_effect = RuntimeError("Chroma error")
        client = _make_test_app(mock_rag_system)
        response = client.get("/api/courses")
        assert response.status_code == 500

    def test_empty_course_list(self, mock_rag_system):
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": [],
        }
        client = _make_test_app(mock_rag_system)
        data = client.get("/api/courses").json()
        assert data["total_courses"] == 0
        assert data["course_titles"] == []


# ---------------------------------------------------------------------------
# POST /api/clear-session
# ---------------------------------------------------------------------------

class TestClearSessionEndpoint:

    def test_returns_200(self, mock_rag_system):
        client = _make_test_app(mock_rag_system)
        response = client.post("/api/clear-session", json={"session_id": "abc"})
        assert response.status_code == 200

    def test_response_status_ok(self, mock_rag_system):
        client = _make_test_app(mock_rag_system)
        data = client.post("/api/clear-session", json={"session_id": "abc"}).json()
        assert data["status"] == "ok"

    def test_clear_session_called_with_session_id(self, mock_rag_system):
        client = _make_test_app(mock_rag_system)
        client.post("/api/clear-session", json={"session_id": "xyz"})
        mock_rag_system.session_manager.clear_session.assert_called_once_with("xyz")

    def test_clear_session_not_called_when_no_session_id(self, mock_rag_system):
        client = _make_test_app(mock_rag_system)
        client.post("/api/clear-session", json={})
        mock_rag_system.session_manager.clear_session.assert_not_called()

    def test_null_session_id_does_not_call_clear(self, mock_rag_system):
        client = _make_test_app(mock_rag_system)
        client.post("/api/clear-session", json={"session_id": None})
        mock_rag_system.session_manager.clear_session.assert_not_called()
