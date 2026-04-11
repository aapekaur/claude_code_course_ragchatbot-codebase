# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run the app (from project root)
./run.sh
# or manually:
cd backend && uv run uvicorn app:app --reload --port 8000
```

Requires a `.env` file in the project root with `ANTHROPIC_API_KEY=...`.

App runs at `http://localhost:8000`. There are no tests or linting configured.

## Architecture

This is a RAG chatbot that answers questions about course documents using Claude + ChromaDB.

**Request flow:**
1. Frontend (`frontend/`) sends `POST /api/query` with `{query, session_id}` to FastAPI (`backend/app.py`)
2. `RAGSystem` (`rag_system.py`) is the central orchestrator — it wires together all backend components
3. `AIGenerator` makes a first Claude API call with the `search_course_content` tool available
4. If Claude decides to search, `CourseSearchTool` → `VectorStore.search()` queries ChromaDB and returns top-5 chunks
5. A second Claude API call synthesizes the chunks into a final answer
6. Sources and answer are returned to the frontend

**Key design decisions:**
- Tool-calling is the retrieval mechanism — Claude decides whether to search, rather than always retrieving
- `VectorStore` maintains two ChromaDB collections: `course_catalog` (titles/metadata for fuzzy course name resolution) and `course_content` (chunked lesson text for semantic search)
- Session history is stored in-memory in `SessionManager` (lost on restart); only the last 2 exchanges are passed to Claude
- On startup, `app.py` loads all `.txt/.pdf/.docx` files from `../docs/` — duplicate courses (matched by title) are skipped

**Course document format** (required for ingestion):
```
Course Title: <title>
Course Link: <url>
Course Instructor: <name>

Lesson 1: <title>
Lesson Link: <url>
<lesson content...>

Lesson 2: <title>
...
```

**Config** (`backend/config.py`): model, chunk size (800 chars), overlap (100 chars), max results (5), ChromaDB path (`./chroma_db` relative to `backend/`).
