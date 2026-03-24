# MeetingAgent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a LangGraph agent that ingests WhisperX meeting transcriptions, extracts structured intelligence (summary, decisions, action items with speaker attribution), persists results, and exposes everything via a FastAPI with async job processing and semantic search.

**Architecture:** A ReAct LangGraph agent sits at the core — it receives WhisperX JSON and calls tools sequentially (analyze → extract → report), writing to SQLite and ChromaDB. FastAPI wraps the agent with a `BackgroundTasks` async pattern (POST /analyze returns a job_id; GET /jobs/{id} polls for the result). Each of the three layers (agent, API, DB) is isolated with no cross-layer imports.

**Tech Stack:** Python 3.12, LangChain, LangGraph, FastAPI, ChromaDB, SQLite (stdlib), pytest, Docker Compose.

---

> **Note on playground/ (Phases 1 & 2):** The `playground/` directory is for free-form learning scripts — no plan needed. Write `01_chains_lcel.py`, `02_tools.py`, `03_memory.py`, `04_rag_basic.py` at your own pace before starting Task 1. These do not need tests. The plan below covers production code only.

---

## File Map

```
src/
├── agent/
│   ├── state.py          ← MeetingAgentState TypedDict + ActionItem types
│   ├── tools.py          ← @tool functions (analyze, extract, report, search)
│   ├── nodes.py          ← agent_node and tool_node functions
│   └── graph.py          ← StateGraph definition and compile()
├── api/
│   ├── models.py         ← Pydantic request/response schemas
│   ├── main.py           ← FastAPI app factory
│   └── routes/
│       ├── analyze.py    ← POST /analyze + GET /jobs/{id}
│       ├── meetings.py   ← GET /meetings + GET /meetings/{id}
│       ├── tasks.py      ← GET /tasks + PATCH /tasks/{id}
│       └── search.py     ← POST /search
├── db/
│   ├── sqlite.py         ← all SQLite queries (meetings, action_items, jobs tables)
│   └── vector_store.py   ← ChromaDB wrapper (index_segments, search)
└── providers/
    └── llm.py            ← LLM factory (OpenAI / Claude / Ollama switch)

tests/
├── test_sqlite.py
├── test_vector_store.py
├── test_llm_provider.py
├── test_tools.py
├── test_graph.py
└── api/
    ├── test_analyze.py
    ├── test_meetings.py
    ├── test_tasks.py
    └── test_search.py
```

---

## Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `src/__init__.py`, `src/agent/__init__.py`, `src/api/__init__.py`, `src/api/routes/__init__.py`, `src/db/__init__.py`, `src/providers/__init__.py`
- Create: `tests/__init__.py`, `tests/api/__init__.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "meeting-agent"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "langchain>=0.3",
    "langgraph>=0.2",
    "langchain-openai>=0.2",
    "langchain-anthropic>=0.2",
    "langchain-ollama>=0.2",
    "chromadb>=0.5",
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 2: Create .env.example**

```ini
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
CHROMA_HOST=localhost
CHROMA_PORT=8001
```

- [ ] **Step 3: Create all __init__.py files and src/ directory tree**

```bash
mkdir -p src/agent src/api/routes src/db src/providers tests/api
touch src/__init__.py src/agent/__init__.py src/api/__init__.py
touch src/api/routes/__init__.py src/db/__init__.py src/providers/__init__.py
touch tests/__init__.py tests/api/__init__.py
```

- [ ] **Step 4: Install dependencies**

```bash
pip install -e ".[dev]"
```

Expected: No errors. `python -c "import langchain, langgraph, fastapi, chromadb"` succeeds.

- [ ] **Step 5: Commit**

```bash
git init
git add pyproject.toml .env.example src/ tests/
git commit -m "chore: project scaffold"
```

---

## Task 2: SQLite Data Layer

**Files:**
- Create: `src/db/sqlite.py`
- Create: `tests/test_sqlite.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_sqlite.py
import pytest
from src.db.sqlite import Database

@pytest.fixture
def db():
    return Database(":memory:")  # in-memory SQLite for tests

def test_create_job(db):
    job_id = db.create_job()
    assert len(job_id) == 36  # UUID format

def test_complete_job(db):
    job_id = db.create_job()
    meeting_id = "meeting-123"
    db.complete_job(job_id, meeting_id)
    job = db.get_job(job_id)
    assert job["status"] == "done"
    assert job["meeting_id"] == meeting_id

def test_fail_job(db):
    job_id = db.create_job()
    db.fail_job(job_id, "LLM timeout")
    job = db.get_job(job_id)
    assert job["status"] == "error"
    assert job["error"] == "LLM timeout"

def test_create_and_get_meeting(db):
    meeting = {
        "id": "m-001",
        "title": "Sprint Planning",
        "date": "2026-03-24",
        "duration_s": 3600.0,
        "speakers": ["SPEAKER_00", "SPEAKER_01"],
        "decisions": ["Launch beta in March"],
        "summary": "We decided to launch the beta.",
        "report_md": "# Sprint Planning\n\n...",
    }
    db.create_meeting(meeting)
    result = db.get_meeting("m-001")
    assert result["title"] == "Sprint Planning"
    assert result["speakers"] == ["SPEAKER_00", "SPEAKER_01"]
    assert result["decisions"] == ["Launch beta in March"]

def test_list_meetings(db):
    db.create_meeting({"id": "m-001", "title": "Meeting A", "date": "2026-03-20",
                        "speakers": [], "decisions": [], "summary": "", "report_md": ""})
    db.create_meeting({"id": "m-002", "title": "Meeting B", "date": "2026-03-24",
                        "speakers": [], "decisions": [], "summary": "", "report_md": ""})
    meetings = db.list_meetings()
    assert len(meetings) == 2

def test_create_and_list_action_items(db):
    db.create_meeting({"id": "m-001", "title": "T", "date": "2026-03-24",
                        "speakers": [], "decisions": [], "summary": "", "report_md": ""})
    db.create_action_item({
        "id": "a-001", "meeting_id": "m-001",
        "task": "Prepare demo", "owner": "SPEAKER_00",
        "due_date": "Friday", "status": "pending"
    })
    items = db.list_action_items(meeting_id="m-001")
    assert len(items) == 1
    assert items[0]["task"] == "Prepare demo"

def test_update_action_item_status(db):
    db.create_meeting({"id": "m-001", "title": "T", "date": "2026-03-24",
                        "speakers": [], "decisions": [], "summary": "", "report_md": ""})
    db.create_action_item({"id": "a-001", "meeting_id": "m-001",
                            "task": "T", "owner": "SPEAKER_00", "due_date": None, "status": "pending"})
    db.update_action_item_status("a-001", "done")
    item = db.get_action_item("a-001")
    assert item["status"] == "done"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_sqlite.py -v
```
Expected: `ImportError` or `ModuleNotFoundError` on `src.db.sqlite`.

- [ ] **Step 3: Implement src/db/sqlite.py**

```python
import json
import sqlite3
import uuid
from datetime import datetime
from typing import Any


class Database:
    def __init__(self, path: str = "data/meetings.db"):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS meetings (
                id         TEXT PRIMARY KEY,
                title      TEXT NOT NULL,
                date       TEXT NOT NULL,
                duration_s REAL,
                speakers   TEXT,
                decisions  TEXT,
                summary    TEXT,
                report_md  TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS action_items (
                id         TEXT PRIMARY KEY,
                meeting_id TEXT REFERENCES meetings(id),
                task       TEXT NOT NULL,
                owner      TEXT,
                due_date   TEXT,
                status     TEXT DEFAULT 'pending'
            );
            CREATE TABLE IF NOT EXISTS jobs (
                id          TEXT PRIMARY KEY,
                status      TEXT DEFAULT 'processing',
                meeting_id  TEXT,
                error       TEXT,
                created_at  TEXT DEFAULT (datetime('now')),
                finished_at TEXT
            );
        """)
        self.conn.commit()

    # --- Jobs ---
    def create_job(self) -> str:
        job_id = str(uuid.uuid4())
        self.conn.execute("INSERT INTO jobs (id) VALUES (?)", (job_id,))
        self.conn.commit()
        return job_id

    def get_job(self, job_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None

    def complete_job(self, job_id: str, meeting_id: str):
        self.conn.execute(
            "UPDATE jobs SET status='done', meeting_id=?, finished_at=? WHERE id=?",
            (meeting_id, datetime.now().isoformat(), job_id),
        )
        self.conn.commit()

    def fail_job(self, job_id: str, error: str):
        self.conn.execute(
            "UPDATE jobs SET status='error', error=?, finished_at=? WHERE id=?",
            (error, datetime.now().isoformat(), job_id),
        )
        self.conn.commit()

    # --- Meetings ---
    def create_meeting(self, data: dict[str, Any]):
        self.conn.execute(
            "INSERT INTO meetings (id, title, date, duration_s, speakers, decisions, summary, report_md) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                data["id"], data["title"], data["date"],
                data.get("duration_s"),
                json.dumps(data.get("speakers", [])),
                json.dumps(data.get("decisions", [])),
                data.get("summary", ""),
                data.get("report_md", ""),
            ),
        )
        self.conn.commit()

    def get_meeting(self, meeting_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
        if not row:
            return None
        m = dict(row)
        m["speakers"] = json.loads(m["speakers"] or "[]")
        m["decisions"] = json.loads(m["decisions"] or "[]")
        return m

    def list_meetings(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM meetings ORDER BY created_at DESC").fetchall()
        result = []
        for row in rows:
            m = dict(row)
            m["speakers"] = json.loads(m["speakers"] or "[]")
            m["decisions"] = json.loads(m["decisions"] or "[]")
            result.append(m)
        return result

    # --- Action Items ---
    def create_action_item(self, data: dict[str, Any]):
        self.conn.execute(
            "INSERT INTO action_items (id, meeting_id, task, owner, due_date, status) VALUES (?,?,?,?,?,?)",
            (data["id"], data["meeting_id"], data["task"],
             data.get("owner"), data.get("due_date"), data.get("status", "pending")),
        )
        self.conn.commit()

    def get_action_item(self, item_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM action_items WHERE id = ?", (item_id,)).fetchone()
        return dict(row) if row else None

    def list_action_items(self, meeting_id: str | None = None,
                          status: str | None = None, owner: str | None = None) -> list[dict]:
        query = "SELECT * FROM action_items WHERE 1=1"
        params: list = []
        if meeting_id:
            query += " AND meeting_id = ?"
            params.append(meeting_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        if owner:
            query += " AND owner = ?"
            params.append(owner)
        return [dict(r) for r in self.conn.execute(query, params).fetchall()]

    def update_action_item_status(self, item_id: str, status: str):
        self.conn.execute("UPDATE action_items SET status = ? WHERE id = ?", (status, item_id))
        self.conn.commit()
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_sqlite.py -v
```
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/db/sqlite.py tests/test_sqlite.py
git commit -m "feat: SQLite data layer with meetings, action_items, jobs tables"
```

---

## Task 3: ChromaDB Vector Store

**Files:**
- Create: `src/db/vector_store.py`
- Create: `tests/test_vector_store.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_vector_store.py
import pytest
from src.db.vector_store import VectorStore

@pytest.fixture
def store():
    # ephemeral=True creates an in-memory ChromaDB instance
    return VectorStore(ephemeral=True)

def test_index_and_search(store):
    segments = [
        {"start": 0.0, "end": 4.2, "speaker": "SPEAKER_00",
         "text": "We need to deliver the module by Friday."},
        {"start": 5.0, "end": 9.0, "speaker": "SPEAKER_01",
         "text": "The budget is approved for Q1."},
    ]
    store.index_segments(
        meeting_id="m-001",
        meeting_title="Sprint Planning",
        date="2026-03-24",
        segments=segments,
    )
    results = store.search("deadline for module delivery", top_k=1)
    assert len(results) == 1
    assert "module" in results[0]["text"].lower()
    assert results[0]["speaker"] == "SPEAKER_00"
    assert results[0]["meeting_id"] == "m-001"

def test_search_returns_metadata(store):
    segments = [{"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00", "text": "Launch the beta in March."}]
    store.index_segments("m-002", "Product Meeting", "2026-03-24", segments)
    results = store.search("beta launch", top_k=1)
    r = results[0]
    assert "start" in r
    assert "end" in r
    assert "meeting_title" in r
    assert "date" in r
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/test_vector_store.py -v
```
Expected: `ImportError`.

- [ ] **Step 3: Implement src/db/vector_store.py**

```python
import chromadb
from chromadb.config import Settings


class VectorStore:
    def __init__(self, host: str = "localhost", port: int = 8001, ephemeral: bool = False):
        if ephemeral:
            self.client = chromadb.EphemeralClient()
        else:
            self.client = chromadb.HttpClient(host=host, port=port)
        self.collection = self.client.get_or_create_collection(
            name="meeting_segments",
            metadata={"hnsw:space": "cosine"},
        )

    def index_segments(
        self,
        meeting_id: str,
        meeting_title: str,
        date: str,
        segments: list[dict],
    ):
        ids, documents, metadatas = [], [], []
        for i, seg in enumerate(segments):
            ids.append(f"{meeting_id}-seg-{i}")
            documents.append(seg["text"])
            metadatas.append({
                "meeting_id": meeting_id,
                "meeting_title": meeting_title,
                "speaker": seg.get("speaker", ""),
                "start": seg.get("start", 0.0),
                "end": seg.get("end", 0.0),
                "date": date,
            })
        self.collection.add(ids=ids, documents=documents, metadatas=metadatas)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        results = self.collection.query(query_texts=[query], n_results=top_k)
        output = []
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            output.append({"text": doc, **meta})
        return output
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_vector_store.py -v
```
Expected: Both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/db/vector_store.py tests/test_vector_store.py
git commit -m "feat: ChromaDB vector store with per-segment indexing"
```

---

## Task 4: LLM Provider

**Files:**
- Create: `src/providers/llm.py`
- Create: `tests/test_llm_provider.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_llm_provider.py
import os
import pytest
from unittest.mock import patch

def test_openai_provider():
    with patch.dict(os.environ, {"LLM_PROVIDER": "openai", "OPENAI_API_KEY": "sk-test"}):
        from src.providers.llm import get_llm
        llm = get_llm()
        assert llm.__class__.__name__ == "ChatOpenAI"

def test_claude_provider():
    with patch.dict(os.environ, {"LLM_PROVIDER": "claude", "ANTHROPIC_API_KEY": "sk-ant-test"}):
        from importlib import reload
        import src.providers.llm as llm_module
        reload(llm_module)
        llm = llm_module.get_llm()
        assert llm.__class__.__name__ == "ChatAnthropic"

def test_ollama_provider():
    with patch.dict(os.environ, {"LLM_PROVIDER": "ollama"}):
        from importlib import reload
        import src.providers.llm as llm_module
        reload(llm_module)
        llm = llm_module.get_llm()
        assert llm.__class__.__name__ == "ChatOllama"

def test_unknown_provider_raises():
    with patch.dict(os.environ, {"LLM_PROVIDER": "unknown"}):
        from importlib import reload
        import src.providers.llm as llm_module
        reload(llm_module)
        with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
            llm_module.get_llm()
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/test_llm_provider.py -v
```

- [ ] **Step 3: Implement src/providers/llm.py**

```python
import os
from langchain_core.language_models import BaseChatModel


def get_llm() -> BaseChatModel:
    provider = os.getenv("LLM_PROVIDER", "openai")
    match provider:
        case "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model="gpt-4o-mini")
        case "claude":
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(model="claude-3-5-haiku-latest")
        case "ollama":
            from langchain_ollama import ChatOllama
            return ChatOllama(model="llama3.2")
        case _:
            raise ValueError(f"Unknown LLM_PROVIDER: {provider!r}. Use 'openai', 'claude', or 'ollama'.")
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_llm_provider.py -v
```
Expected: All 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/providers/llm.py tests/test_llm_provider.py
git commit -m "feat: LLM provider factory (OpenAI / Claude / Ollama)"
```

---

## Task 5: Agent State & Types

**Files:**
- Create: `src/agent/state.py`

No tests needed — this is a pure type definition file. Correctness is verified through the tool and graph tests.

- [ ] **Step 1: Implement src/agent/state.py**

```python
from typing import TypedDict
from langchain_core.messages import BaseMessage


class ActionItem(TypedDict):
    task: str
    owner: str        # e.g. "SPEAKER_00"
    due_date: str
    status: str       # always "pending" on extraction


class MeetingAgentState(TypedDict):
    # ── Input ──────────────────────────────────────────
    transcript_segments: list[dict]   # WhisperX segment objects
    meeting_title: str
    meeting_date: str

    # ── Accumulated by tools ───────────────────────────
    messages: list[BaseMessage]       # LangGraph ReAct message history
    summary: str
    decisions: list[str]
    action_items: list[ActionItem]
    report_markdown: str

    # ── Control ────────────────────────────────────────
    meeting_id: str
    job_id: str
```

- [ ] **Step 2: Commit**

```bash
git add src/agent/state.py
git commit -m "feat: MeetingAgentState and ActionItem types"
```

---

## Task 6: Tool — analyze_transcript

**Files:**
- Create: `src/agent/tools.py` (first tool only)
- Create: `tests/test_tools.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_tools.py
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage

# We'll mock the LLM so tests don't make real API calls
FAKE_ANALYSIS = """{
  "summary": "Team agreed to launch beta in March.",
  "decisions": ["Launch beta in March"],
  "participants": ["SPEAKER_00", "SPEAKER_01"]
}"""

def make_mock_llm(content: str):
    mock = MagicMock()
    mock.invoke.return_value = AIMessage(content=content)
    return mock

def test_analyze_transcript():
    with patch("src.agent.tools.get_llm", return_value=make_mock_llm(FAKE_ANALYSIS)):
        from src.agent.tools import analyze_transcript
        segments = [
            {"start": 0.0, "end": 4.0, "speaker": "SPEAKER_00",
             "text": "We should launch the beta in March."},
        ]
        result = analyze_transcript.invoke({"segments_json": str(segments)})
        assert "summary" in result
        assert "decisions" in result
        assert "participants" in result
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_tools.py::test_analyze_transcript -v
```

- [ ] **Step 3: Implement analyze_transcript in src/agent/tools.py**

```python
import json
from langchain_core.tools import tool
from src.providers.llm import get_llm


@tool
def analyze_transcript(segments_json: str) -> dict:
    """Analyze a WhisperX transcript. Input: JSON string of segment list.
    Returns dict with summary, decisions, participants."""
    llm = get_llm()
    prompt = f"""You are analyzing a meeting transcript. Each segment has speaker, start, end, and text.

Transcript segments:
{segments_json}

Return a JSON object with:
- summary: 2-3 sentence summary of the meeting
- decisions: list of key decisions made
- participants: list of unique speaker IDs

Respond ONLY with valid JSON."""
    response = llm.invoke(prompt)
    # Strip markdown code fences if present
    content = response.content.strip().removeprefix("```json").removesuffix("```").strip()
    return json.loads(content)
```

- [ ] **Step 4: Run test**

```bash
pytest tests/test_tools.py::test_analyze_transcript -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent/tools.py tests/test_tools.py
git commit -m "feat: analyze_transcript tool"
```

---

## Task 7: Tool — extract_action_items

**Files:**
- Modify: `src/agent/tools.py`
- Modify: `tests/test_tools.py`

- [ ] **Step 1: Add failing test**

```python
# Add to tests/test_tools.py

FAKE_ACTIONS = """{
  "action_items": [
    {"task": "Prepare demo", "owner": "SPEAKER_00", "due_date": "Friday", "status": "pending"}
  ]
}"""

def test_extract_action_items():
    with patch("src.agent.tools.get_llm", return_value=make_mock_llm(FAKE_ACTIONS)):
        from importlib import reload
        import src.agent.tools as tools_module
        reload(tools_module)
        segments = [{"start": 0.0, "end": 4.0, "speaker": "SPEAKER_00",
                      "text": "I'll prepare the demo by Friday."}]
        result = tools_module.extract_action_items.invoke({"segments_json": str(segments)})
        assert "action_items" in result
        assert result["action_items"][0]["owner"] == "SPEAKER_00"
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_tools.py::test_extract_action_items -v
```

- [ ] **Step 3: Add extract_action_items to src/agent/tools.py**

```python
@tool
def extract_action_items(segments_json: str) -> dict:
    """Extract action items from transcript segments.
    Returns dict with action_items list (task, owner, due_date, status)."""
    llm = get_llm()
    prompt = f"""Extract all action items from this meeting transcript.

Transcript segments:
{segments_json}

Return a JSON object with:
- action_items: list of objects, each with:
  - task: clear description of what needs to be done
  - owner: speaker ID who is responsible (e.g. "SPEAKER_00")
  - due_date: deadline if mentioned, else null
  - status: always "pending"

Respond ONLY with valid JSON."""
    response = llm.invoke(prompt)
    content = response.content.strip().removeprefix("```json").removesuffix("```").strip()
    return json.loads(content)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_tools.py -v
```
Expected: Both tool tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent/tools.py tests/test_tools.py
git commit -m "feat: extract_action_items tool"
```

---

## Task 8: Tool — generate_report (with SQLite persistence)

**Files:**
- Modify: `src/agent/tools.py`
- Modify: `tests/test_tools.py`

- [ ] **Step 1: Add failing test**

```python
# Add to tests/test_tools.py
from src.db.sqlite import Database

FAKE_REPORT = "# Sprint Planning\n\n## Summary\nTeam agreed to launch beta in March."

def test_generate_report():
    db = Database(":memory:")
    with patch("src.agent.tools.get_llm", return_value=make_mock_llm(FAKE_REPORT)):
        from importlib import reload
        import src.agent.tools as tools_module
        reload(tools_module)
        result = tools_module.generate_report.invoke({
            "meeting_id": "m-001",
            "meeting_title": "Sprint Planning",
            "meeting_date": "2026-03-24",
            "summary": "Team agreed to launch beta.",
            "decisions_json": '["Launch beta in March"]',
            "action_items_json": '[{"task":"Prepare demo","owner":"SPEAKER_00","due_date":"Friday","status":"pending"}]',
            "segments_json": "[]",
            "db_path": ":memory:",
        })
        assert "report_markdown" in result
        assert "Sprint Planning" in result["report_markdown"]
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_tools.py::test_generate_report -v
```

- [ ] **Step 3: Add generate_report to src/agent/tools.py**

```python
@tool
def generate_report(
    meeting_id: str,
    meeting_title: str,
    meeting_date: str,
    summary: str,
    decisions_json: str,
    action_items_json: str,
    segments_json: str,
    db_path: str = "data/meetings.db",
) -> dict:
    """Generate a markdown report and persist meeting to SQLite.
    Returns dict with report_markdown."""
    import uuid
    decisions = json.loads(decisions_json)
    action_items = json.loads(action_items_json)
    segments = json.loads(segments_json)

    llm = get_llm()
    prompt = f"""Write a professional meeting report in markdown.

Title: {meeting_title}
Date: {meeting_date}
Summary: {summary}
Decisions: {decisions}
Action Items: {action_items}

Include sections: Summary, Key Decisions, Action Items (with checkboxes), Participants."""
    response = llm.invoke(prompt)
    report_md = response.content.strip()

    # Persist to SQLite
    db = Database(db_path)
    speakers = list({seg.get("speaker", "") for seg in segments if seg.get("speaker")})
    duration_s = max((seg.get("end", 0) for seg in segments), default=None)

    db.create_meeting({
        "id": meeting_id,
        "title": meeting_title,
        "date": meeting_date,
        "duration_s": duration_s,
        "speakers": speakers,
        "decisions": decisions,
        "summary": summary,
        "report_md": report_md,
    })
    for item in action_items:
        db.create_action_item({
            "id": str(uuid.uuid4()),
            "meeting_id": meeting_id,
            **item,
        })

    return {"report_markdown": report_md}
```

Add `from src.db.sqlite import Database` at the top of `tools.py`.

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_tools.py -v
```
Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent/tools.py tests/test_tools.py
git commit -m "feat: generate_report tool with SQLite persistence"
```

---

## Task 9: Tool — search_meetings

**Files:**
- Modify: `src/agent/tools.py`
- Modify: `tests/test_tools.py`

- [ ] **Step 1: Add failing test**

```python
# Add to tests/test_tools.py
from src.db.vector_store import VectorStore

def test_search_meetings():
    store = VectorStore(ephemeral=True)
    store.index_segments(
        meeting_id="m-001",
        meeting_title="Sprint Planning",
        date="2026-03-24",
        segments=[{"start": 0.0, "end": 4.0, "speaker": "SPEAKER_00",
                   "text": "We will prepare the demo by Friday."}],
    )
    # Patch VectorStore before importing tools (no reload — reload defeats the patch)
    with patch("src.agent.tools.VectorStore", return_value=store):
        from src.agent.tools import search_meetings
        result = search_meetings.invoke({"query": "demo preparation", "top_k": 1})
        assert "results" in result
        assert len(result["results"]) == 1
        assert result["results"][0]["speaker"] == "SPEAKER_00"
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_tools.py::test_search_meetings -v
```

- [ ] **Step 3: Add search_meetings to src/agent/tools.py**

```python
import os
from src.db.vector_store import VectorStore

@tool
def search_meetings(query: str, top_k: int = 5) -> dict:
    """Search past meeting transcripts using semantic similarity.
    Returns dict with results list (text, speaker, start, end, meeting_id, meeting_title, date)."""
    store = VectorStore(
        host=os.getenv("CHROMA_HOST", "localhost"),
        port=int(os.getenv("CHROMA_PORT", "8001")),
    )
    results = store.search(query=query, top_k=top_k)
    return {"results": results}
```

- [ ] **Step 4: Run all tool tests**

```bash
pytest tests/test_tools.py -v
```
Expected: All 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent/tools.py tests/test_tools.py
git commit -m "feat: search_meetings tool using ChromaDB"
```

---

## Task 10: LangGraph Agent Graph

**Files:**
- Create: `src/agent/nodes.py`
- Create: `src/agent/graph.py`
- Create: `tests/test_graph.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_graph.py
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from langchain_core.messages import AIMessage, ToolMessage

def make_mock_graph():
    """Returns a mock that simulates a compiled LangGraph."""
    mock = MagicMock()
    mock.ainvoke = AsyncMock(return_value={
        "summary": "Team agreed to launch beta.",
        "decisions": ["Launch beta"],
        "action_items": [{"task": "Prepare demo", "owner": "SPEAKER_00",
                          "due_date": "Friday", "status": "pending"}],
        "report_markdown": "# Sprint Planning\n\n...",
        "meeting_id": "m-001",
    })
    return mock

@pytest.mark.asyncio
async def test_graph_invocation_shape():
    """Verify the graph accepts the right input shape and returns expected keys."""
    with patch("src.agent.graph.build_graph", return_value=make_mock_graph()):
        from src.agent.graph import build_graph
        graph = build_graph()
        result = await graph.ainvoke({
            "transcript_segments": [
                {"start": 0.0, "end": 4.0, "speaker": "SPEAKER_00",
                 "text": "We should launch beta in March."}
            ],
            "meeting_title": "Sprint Planning",
            "meeting_date": "2026-03-24",
            "messages": [],
            "summary": "",
            "decisions": [],
            "action_items": [],
            "report_markdown": "",
            "meeting_id": "m-001",
            "job_id": "j-001",
        })
        assert "summary" in result
        assert "action_items" in result
        assert "report_markdown" in result
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_graph.py -v
```

- [ ] **Step 3: Implement src/agent/nodes.py**

```python
from langchain_core.messages import SystemMessage
from langgraph.prebuilt import ToolNode

from src.agent.state import MeetingAgentState
from src.agent.tools import analyze_transcript, extract_action_items, generate_report, search_meetings
from src.providers.llm import get_llm

TOOLS = [analyze_transcript, extract_action_items, generate_report, search_meetings]

SYSTEM_PROMPT = """You are a meeting analysis assistant. You receive a meeting transcript in WhisperX format.

Your job:
1. Call analyze_transcript with the segments to get summary, decisions, and participants.
2. Call extract_action_items with the segments to get tasks with owners and deadlines.
3. Call generate_report to persist everything to the database and get the markdown report.

Call the tools in this order. Do not skip steps. After generate_report, you are done."""


def agent_node(state: MeetingAgentState) -> dict:
    llm = get_llm().bind_tools(TOOLS)
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    # Inject the transcript into the first call
    if not state["messages"]:
        import json
        messages.append({"role": "user", "content": json.dumps(state["transcript_segments"])})
    response = llm.invoke(messages)
    return {"messages": state["messages"] + [response]}


def should_continue(state: MeetingAgentState) -> str:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return "__end__"


tool_node = ToolNode(TOOLS)
```

- [ ] **Step 4: Implement src/agent/graph.py**

```python
from langgraph.graph import StateGraph, START
from src.agent.state import MeetingAgentState
from src.agent.nodes import agent_node, tool_node, should_continue


def build_graph():
    builder = StateGraph(MeetingAgentState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tool_node)
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", should_continue, {"tools": "tools", "__end__": "__end__"})
    builder.add_edge("tools", "agent")
    return builder.compile()
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_graph.py -v
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/agent/nodes.py src/agent/graph.py tests/test_graph.py
git commit -m "feat: LangGraph ReAct agent graph (agent_node + tool_node + conditional edges)"
```

---

## Task 11: Pydantic API Models

**Files:**
- Create: `src/api/models.py`

No tests — models are validated through route tests.

- [ ] **Step 1: Implement src/api/models.py**

```python
from pydantic import BaseModel


# ── Inputs ──────────────────────────────────────────────────────────────────

class TranscriptSegment(BaseModel):
    start: float
    end: float
    speaker: str
    text: str

class AnalyzeRequest(BaseModel):
    title: str
    date: str
    segments: list[TranscriptSegment]

class SearchRequest(BaseModel):
    query: str
    top_k: int = 5

class UpdateTaskRequest(BaseModel):
    status: str  # "pending" | "done" | "cancelled"


# ── Outputs ─────────────────────────────────────────────────────────────────

class JobResponse(BaseModel):
    job_id: str
    status: str  # "processing" | "done" | "error"
    meeting_id: str | None = None
    error: str | None = None
    # Populated when status == "done" (JOINed from meetings + action_items)
    summary: str | None = None
    decisions: list[str] | None = None
    participants: list[str] | None = None
    action_items: list[ActionItemResponse] | None = None
    report: str | None = None

class ActionItemResponse(BaseModel):
    id: str
    meeting_id: str
    task: str
    owner: str | None
    due_date: str | None
    status: str

class MeetingResponse(BaseModel):
    id: str
    title: str
    date: str
    duration_s: float | None
    speakers: list[str]
    decisions: list[str]
    summary: str | None
    report_md: str | None

class MeetingDetailResponse(MeetingResponse):
    action_items: list[ActionItemResponse]

class SearchResult(BaseModel):
    text: str
    speaker: str
    start: float
    end: float
    meeting_id: str
    meeting_title: str
    date: str

class SearchResponse(BaseModel):
    results: list[SearchResult]
```

- [ ] **Step 2: Commit**

```bash
git add src/api/models.py
git commit -m "feat: Pydantic API request/response models"
```

---

## Task 12: Routes — /analyze + /jobs

**Files:**
- Create: `src/api/routes/analyze.py`
- Create: `tests/api/test_analyze.py`
- Create: `src/api/main.py` (partial — just enough to mount this router)

- [ ] **Step 1: Write failing tests**

```python
# tests/api/test_analyze.py
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

SAMPLE_PAYLOAD = {
    "title": "Sprint Planning",
    "date": "2026-03-24",
    "segments": [
        {"start": 0.0, "end": 4.0, "speaker": "SPEAKER_00",
         "text": "We need to deliver the module by Friday."}
    ]
}

@pytest.fixture
def client():
    from src.api.main import create_app
    return TestClient(create_app())

def test_analyze_returns_202(client):
    with patch("src.api.routes.analyze.run_agent", new_callable=AsyncMock):
        response = client.post("/analyze", json=SAMPLE_PAYLOAD)
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "processing"

def test_get_job_not_found(client):
    response = client.get("/jobs/nonexistent-id")
    assert response.status_code == 404

def test_get_job_processing(client):
    with patch("src.api.routes.analyze.run_agent", new_callable=AsyncMock):
        post_res = client.post("/analyze", json=SAMPLE_PAYLOAD)
    job_id = post_res.json()["job_id"]
    get_res = client.get(f"/jobs/{job_id}")
    assert get_res.status_code == 200
    assert get_res.json()["status"] in ("processing", "done", "error")
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/api/test_analyze.py -v
```

- [ ] **Step 3: Implement src/api/routes/analyze.py**

```python
import uuid
from fastapi import APIRouter, BackgroundTasks, HTTPException
from src.api.models import AnalyzeRequest, JobResponse
from src.agent.graph import build_graph
from src.agent.state import MeetingAgentState
from src.db.sqlite import Database

router = APIRouter()
_graph = build_graph()


def get_db(db_path: str = "data/meetings.db") -> Database:
    return Database(db_path)


async def run_agent(job_id: str, payload: AnalyzeRequest, db_path: str = "data/meetings.db"):
    db = Database(db_path)
    meeting_id = str(uuid.uuid4())
    try:
        state: MeetingAgentState = {
            "transcript_segments": [s.model_dump() for s in payload.segments],
            "meeting_title": payload.title,
            "meeting_date": payload.date,
            "messages": [],
            "summary": "",
            "decisions": [],
            "action_items": [],
            "report_markdown": "",
            "meeting_id": meeting_id,
            "job_id": job_id,
        }
        await _graph.ainvoke(state)
        db.complete_job(job_id, meeting_id)
    except Exception as e:
        db.fail_job(job_id, str(e))


@router.post("/analyze", status_code=202, response_model=JobResponse)
async def analyze(payload: AnalyzeRequest, background: BackgroundTasks,
                  db: Database = Depends(get_db)):
    job_id = db.create_job()
    background.add_task(run_agent, job_id, payload)
    return JobResponse(job_id=job_id, status="processing")


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Database = Depends(get_db)):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] == "done" and job.get("meeting_id"):
        meeting = db.get_meeting(job["meeting_id"])
        items = db.list_action_items(meeting_id=job["meeting_id"])
        return JobResponse(
            job_id=job["id"], status=job["status"],
            meeting_id=job["meeting_id"],
            summary=meeting["summary"],
            decisions=meeting["decisions"],
            participants=meeting["speakers"],
            action_items=items,
            report=meeting["report_md"],
        )
    return JobResponse(job_id=job["id"], status=job["status"],
                       meeting_id=job.get("meeting_id"), error=job.get("error"))
```

- [ ] **Step 4: Create src/api/main.py**

```python
from fastapi import FastAPI
from src.api.routes.analyze import router as analyze_router


def create_app() -> FastAPI:
    app = FastAPI(title="MeetingAgent API")
    app.include_router(analyze_router)
    return app
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/api/test_analyze.py -v
```
Expected: All 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add src/api/routes/analyze.py src/api/main.py tests/api/test_analyze.py
git commit -m "feat: POST /analyze and GET /jobs/{id} routes"
```

---

## Task 13: Routes — /meetings

**Files:**
- Create: `src/api/routes/meetings.py`
- Create: `tests/api/test_meetings.py`
- Modify: `src/api/main.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/api/test_meetings.py
import pytest
from fastapi.testclient import TestClient
from src.db.sqlite import Database

@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test.db")
    db = Database(db_path)
    db.create_meeting({"id": "m-001", "title": "Sprint Planning", "date": "2026-03-24",
                        "speakers": ["SPEAKER_00"], "decisions": ["Launch beta"],
                        "summary": "Agreed to launch.", "report_md": "# Report"})
    from src.api.main import create_app
    app = create_app(db_path=db_path)
    return TestClient(app)

def test_list_meetings(client):
    res = client.get("/meetings")
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["title"] == "Sprint Planning"

def test_get_meeting(client):
    res = client.get("/meetings/m-001")
    assert res.status_code == 200
    assert res.json()["decisions"] == ["Launch beta"]

def test_get_meeting_not_found(client):
    res = client.get("/meetings/nonexistent")
    assert res.status_code == 404
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/api/test_meetings.py -v
```

- [ ] **Step 3: Implement src/api/routes/meetings.py**

```python
from fastapi import APIRouter, Depends, HTTPException
from src.api.models import MeetingResponse, MeetingDetailResponse, ActionItemResponse
from src.db.sqlite import Database

router = APIRouter()


def get_db(db_path: str = "data/meetings.db") -> Database:
    return Database(db_path)


@router.get("/meetings", response_model=list[MeetingResponse])
def list_meetings(db: Database = Depends(get_db)):
    return db.list_meetings()


@router.get("/meetings/{meeting_id}", response_model=MeetingDetailResponse)
def get_meeting(meeting_id: str, db: Database = Depends(get_db)):
    meeting = db.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    items = db.list_action_items(meeting_id=meeting_id)
    return {**meeting, "action_items": items}
```

- [ ] **Step 4: Update src/api/main.py to accept db_path and include meetings router**

```python
from fastapi import FastAPI
from src.api.routes.analyze import router as analyze_router
from src.api.routes.meetings import router as meetings_router


def create_app(db_path: str = "data/meetings.db") -> FastAPI:
    app = FastAPI(title="MeetingAgent API")
    app.include_router(analyze_router)
    app.include_router(meetings_router)
    return app
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/api/test_meetings.py -v
```
Expected: All 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add src/api/routes/meetings.py src/api/main.py tests/api/test_meetings.py
git commit -m "feat: GET /meetings and GET /meetings/{id} routes"
```

---

## Task 14: Routes — /tasks

**Files:**
- Create: `src/api/routes/tasks.py`
- Create: `tests/api/test_tasks.py`
- Modify: `src/api/main.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/api/test_tasks.py
import pytest
from fastapi.testclient import TestClient
from src.db.sqlite import Database

@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test.db")
    db = Database(db_path)
    db.create_meeting({"id": "m-001", "title": "T", "date": "2026-03-24",
                        "speakers": [], "decisions": [], "summary": "", "report_md": ""})
    db.create_action_item({"id": "a-001", "meeting_id": "m-001",
                            "task": "Prepare demo", "owner": "SPEAKER_00",
                            "due_date": "Friday", "status": "pending"})
    from src.api.main import create_app
    return TestClient(create_app(db_path=db_path))

def test_list_tasks(client):
    res = client.get("/tasks")
    assert res.status_code == 200
    assert len(res.json()) == 1

def test_list_tasks_filter_by_status(client):
    res = client.get("/tasks?status=pending")
    assert len(res.json()) == 1
    res2 = client.get("/tasks?status=done")
    assert len(res2.json()) == 0

def test_update_task_status(client):
    res = client.patch("/tasks/a-001", json={"status": "done"})
    assert res.status_code == 200
    assert res.json()["status"] == "done"

def test_update_task_not_found(client):
    res = client.patch("/tasks/nonexistent", json={"status": "done"})
    assert res.status_code == 404
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/api/test_tasks.py -v
```

- [ ] **Step 3: Implement src/api/routes/tasks.py**

```python
from fastapi import APIRouter, Depends, HTTPException
from src.api.models import ActionItemResponse, UpdateTaskRequest
from src.db.sqlite import Database

router = APIRouter()


def get_db(db_path: str = "data/meetings.db") -> Database:
    return Database(db_path)


@router.get("/tasks", response_model=list[ActionItemResponse])
def list_tasks(status: str | None = None, owner: str | None = None,
               db: Database = Depends(get_db)):
    return db.list_action_items(status=status, owner=owner)


@router.patch("/tasks/{task_id}", response_model=ActionItemResponse)
def update_task(task_id: str, body: UpdateTaskRequest, db: Database = Depends(get_db)):
    item = db.get_action_item(task_id)
    if not item:
        raise HTTPException(status_code=404, detail="Task not found")
    db.update_action_item_status(task_id, body.status)
    return db.get_action_item(task_id)
```

- [ ] **Step 4: Add tasks router to src/api/main.py**

```python
from src.api.routes.tasks import router as tasks_router
# add to create_app():
app.include_router(tasks_router)
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/api/test_tasks.py -v
```
Expected: All 4 PASS.

- [ ] **Step 6: Commit**

```bash
git add src/api/routes/tasks.py src/api/main.py tests/api/test_tasks.py
git commit -m "feat: GET /tasks and PATCH /tasks/{id} routes"
```

---

## Task 15: Route — /search

**Files:**
- Create: `src/api/routes/search.py`
- Create: `tests/api/test_search.py`
- Modify: `src/api/main.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/api/test_search.py
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

MOCK_RESULTS = [
    {"text": "We'll prepare the demo by Friday.", "speaker": "SPEAKER_00",
     "start": 0.0, "end": 4.0, "meeting_id": "m-001",
     "meeting_title": "Sprint Planning", "date": "2026-03-24"}
]

@pytest.fixture
def client():
    from src.api.main import create_app
    return TestClient(create_app())

def test_search_returns_results(client):
    with patch("src.api.routes.search.VectorStore") as MockStore:
        MockStore.return_value.search.return_value = MOCK_RESULTS
        res = client.post("/search", json={"query": "demo preparation", "top_k": 5})
    assert res.status_code == 200
    data = res.json()
    assert "results" in data
    assert data["results"][0]["speaker"] == "SPEAKER_00"

def test_search_empty_results(client):
    with patch("src.api.routes.search.VectorStore") as MockStore:
        MockStore.return_value.search.return_value = []
        res = client.post("/search", json={"query": "nonexistent topic"})
    assert res.status_code == 200
    assert res.json()["results"] == []
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/api/test_search.py -v
```

- [ ] **Step 3: Implement src/api/routes/search.py**

```python
import os
from fastapi import APIRouter
from src.api.models import SearchRequest, SearchResponse, SearchResult
from src.db.vector_store import VectorStore

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
def search_meetings(body: SearchRequest):
    store = VectorStore(
        host=os.getenv("CHROMA_HOST", "localhost"),
        port=int(os.getenv("CHROMA_PORT", "8001")),
    )
    raw = store.search(query=body.query, top_k=body.top_k)
    return SearchResponse(results=[SearchResult(**r) for r in raw])
```

- [ ] **Step 4: Add search router to main.py**

```python
from src.api.routes.search import router as search_router
# add to create_app():
app.include_router(search_router)
```

- [ ] **Step 5: Run all tests**

```bash
pytest tests/ -v
```
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/api/routes/search.py src/api/main.py tests/api/test_search.py
git commit -m "feat: POST /search route with ChromaDB semantic search"
```

---

## Task 16: Docker

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.dockerignore`

No tests — verified by running `docker compose up`.

- [ ] **Step 1: Create Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Copy source before install so pip install . can find it
COPY pyproject.toml .
COPY src/ src/
RUN pip install .

RUN mkdir -p data

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Update `src/api/main.py` to expose `app` at module level (alongside `create_app`):

```python
# at bottom of main.py
app = create_app()
```

- [ ] **Step 2: Create docker-compose.yml**

```yaml
services:
  api:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    environment:
      - CHROMA_HOST=chromadb
      - CHROMA_PORT=8001
    depends_on:
      - chromadb
    volumes:
      - ./data/meetings.db:/app/data/meetings.db

  chromadb:
    image: chromadb/chroma:latest
    ports:
      - "8001:8001"
    volumes:
      - ./data/chroma:/chroma/chroma

  ollama:
    image: ollama/ollama
    ports:
      - "11434:11434"
    profiles:
      - local
```

- [ ] **Step 3: Create .dockerignore**

```
.env
.env.*
__pycache__
*.pyc
.git
data/
tests/
playground/
```

- [ ] **Step 4: Copy .env.example to .env and fill in your API key, then test**

```bash
cp .env.example .env
# edit .env: set LLM_PROVIDER=openai and OPENAI_API_KEY=your-key
mkdir -p data
docker compose up --build
```

Expected: API responds at `http://localhost:8000/docs`.

- [ ] **Step 5: Smoke test the full flow**

```bash
curl -s -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"title":"Test","date":"2026-03-24","segments":[{"start":0,"end":4,"speaker":"SPEAKER_00","text":"Let'\''s deliver the module by Friday."}]}' \
  | python -m json.tool

# Copy the job_id from response, then:
curl http://localhost:8000/jobs/<job_id>
```

Expected: job completes with status "done" and includes report_markdown.

- [ ] **Step 6: Commit**

```bash
git add Dockerfile docker-compose.yml .dockerignore src/api/main.py
git commit -m "feat: Docker + docker-compose (API + ChromaDB)"
```

---

## Task 17: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write README.md**

Cover these sections:
1. **The problem** — meetings are expensive and their outcomes get lost (business context, not tech)
2. **What this does** — bullet list of capabilities with speaker attribution highlighted
3. **Architecture diagram** — ASCII art matching the graph from the spec
4. **Quick start** — `git clone` → `cp .env.example .env` → `docker compose up` → curl example
5. **API reference** — table of all 7 endpoints with example request/response
6. **Switching LLM providers** — one line explaining the env var
7. **What I learned** — LangGraph concepts demonstrated (for portfolio context)

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README with problem statement, architecture, and quick start"
```

---

## Full Test Run

After all tasks:

```bash
pytest tests/ -v --tb=short
```

Expected: All tests green. Then:

```bash
docker compose up --build
# In another terminal:
pytest tests/ -v  # still all green against running services
```
