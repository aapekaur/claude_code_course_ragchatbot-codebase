# Testing Infrastructure Changes

## Files Changed

### `pyproject.toml`
- Added `httpx>=0.27.0` to dev dependencies (required by FastAPI's `TestClient`)
- Added `[tool.pytest.ini_options]` with `testpaths = ["backend/tests"]` and `pythonpath = ["backend"]` so pytest finds tests and resolves backend imports without manual `sys.path` hacks

### `backend/tests/conftest.py`
- Added three shared fixtures available to all test modules:
  - `mock_rag_system` — a `MagicMock` RAGSystem pre-configured with sensible defaults (query returns `("Test answer", [])`, analytics returns 2 courses, session manager creates `"test-session-id"`)
  - `sample_query_payload` — a dict `{"query": "What is Python?", "session_id": "session-abc"}` for reuse across query endpoint tests
  - `sample_sources` — a list of two source items for response shape assertions

### `backend/tests/test_api_endpoints.py` (new file)
- 20 tests across three endpoint groups: `POST /api/query`, `GET /api/courses`, `POST /api/clear-session`
- Uses a `_make_test_app(rag_system)` helper that builds a minimal FastAPI app mirroring the real routes from `app.py` but **without** the `StaticFiles` mount — this avoids the `../frontend` directory-not-found error when running tests
- The `TestClient` from `fastapi.testclient` drives all HTTP assertions
- Covers: 200 success paths, request validation (422 on missing fields), 500 error propagation, session auto-creation, and correct delegation to `rag_system` methods
