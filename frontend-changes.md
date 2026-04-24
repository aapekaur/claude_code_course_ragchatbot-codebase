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

# Frontend Changes

## Code Quality Tooling — Prettier Setup

### What was added

**`frontend/package.json`**
- New file. Declares `prettier` as a dev dependency with two npm scripts:
  - `npm run format` — formats all frontend files in-place
  - `npm run format:check` — checks formatting without modifying files (suitable for CI)

**`frontend/.prettierrc`**
- New file. Prettier configuration:
  - 100-character print width
  - 2-space indentation, no tabs
  - Single quotes in JS
  - ES5 trailing commas
  - LF line endings

**`frontend/package-lock.json`**
- Auto-generated lockfile from `npm install`.

**`format-frontend.sh`** (project root)
- Convenience shell script to run Prettier from the project root.
- `./format-frontend.sh` — formats files in-place.
- `./format-frontend.sh --check` — exits non-zero if any file is out of format (use in CI).

### Files reformatted

`frontend/index.html`, `frontend/script.js`, and `frontend/style.css` were reformatted by Prettier on initial setup. Changes are purely stylistic (indentation, quote style, self-closing HTML tags, trailing commas) — no logic was altered.
