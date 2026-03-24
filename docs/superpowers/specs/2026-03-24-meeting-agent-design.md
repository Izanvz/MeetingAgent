# MeetingAgent — Design Spec
**Date:** 2026-03-24
**Author:** Izan Villarejo Adames
**Status:** Approved

---

## 1. Problem Statement

Meeting analysis is a universal pain point: decisions get lost, action items aren't tracked, and context from past meetings is hard to retrieve. This project builds a LangGraph agent that ingests WhisperX transcriptions, extracts structured intelligence (summaries, decisions, action items with speaker attribution), and enables semantic search over past meetings — all exposed via a production-grade FastAPI.

**Primary goal:** Learn LangChain/LangGraph by building a real, portfolio-worthy project.
**Secondary goal:** Demonstrate production thinking: logging, modularity, Docker, async patterns.

---

## 2. Input / Output Contract

### Input — WhisperX JSON
```json
{
  "title": "Sprint Planning Q1",
  "date": "2026-03-24",
  "segments": [
    {
      "start": 0.0,
      "end": 4.2,
      "speaker": "SPEAKER_00",
      "text": "Necesitamos entregar el módulo antes del viernes."
    }
  ]
}
```

### Output — POST /analyze response (202 Accepted)
```json
{ "job_id": "uuid", "status": "processing" }
```

### Output — GET /jobs/{job_id} when done

The handler JOINs `jobs` + `meetings` + `action_items`. `participants` maps to the `speakers` column in `meetings`.

```json
{
  "job_id": "uuid",
  "status": "done",
  "meeting_id": "uuid",
  "summary": "Sprint planning centrado en la entrega del módulo...",
  "decisions": ["Entrega del módulo el viernes"],
  "action_items": [
    {
      "id": "uuid",
      "meeting_id": "uuid",
      "task": "Preparar demo",
      "owner": "SPEAKER_00",
      "due_date": "viernes",
      "status": "pending"
    }
  ],
  "participants": ["SPEAKER_00", "SPEAKER_01"],
  "report": "# Sprint Planning Q1\n\n## Resumen\n..."
}
```

---

## 3. Repository Structure

```
MeetingAgent/
├── playground/                  ← Fase 1 & 2: scripts de aprendizaje
│   ├── 01_chains_lcel.py
│   ├── 02_tools.py
│   ├── 03_memory.py
│   └── 04_rag_basic.py
│
├── src/
│   ├── agent/                   ← núcleo LangGraph
│   │   ├── graph.py             ← definición del StateGraph
│   │   ├── state.py             ← MeetingAgentState (TypedDict)
│   │   ├── nodes.py             ← funciones de nodo
│   │   └── tools.py             ← @tool functions
│   │
│   ├── api/                     ← FastAPI
│   │   ├── main.py
│   │   ├── routes/
│   │   │   ├── analyze.py       ← POST /analyze, GET /jobs/{id}
│   │   │   ├── meetings.py      ← GET /meetings, GET /meetings/{id}
│   │   │   └── tasks.py         ← GET /tasks, PATCH /tasks/{id}
│   │   └── models.py            ← Pydantic schemas
│   │
│   ├── db/                      ← capa de persistencia
│   │   ├── sqlite.py            ← meetings, action_items, jobs
│   │   └── vector_store.py      ← ChromaDB wrapper
│   │
│   └── providers/
│       └── llm.py               ← provider switch (OpenAI/Claude/Ollama)
│
├── tests/
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── README.md
```

**Architectural principle:** The agent layer (`src/agent/`) has zero knowledge of FastAPI. The API layer has zero knowledge of ChromaDB. Communication happens through well-defined interfaces and the SQLite/ChromaDB abstractions in `src/db/`.

---

## 4. LangGraph Agent Architecture

### Pattern: ReAct Agent (Reason → Act → Observe loop)

```
WhisperX JSON ──→ [agent_node] ←──────────────────┐
                       │                           │
               ¿call a tool?                       │
              /            \                       │
            YES             NO → END               │
             │                                     │
         [tool_node] ────── observes result ───────┘
```

The agent_node is an LLM (with tools bound) that reasons about which tool to call next. The loop continues until the LLM decides no more tools are needed.

### Types

```python
# Used in agent state (no id/meeting_id — those are DB concerns)
class ActionItem(TypedDict):
    task: str
    owner: str        # speaker ID e.g. "SPEAKER_00"
    due_date: str
    status: str       # always "pending" when first extracted

# Used in API responses (includes DB fields)
class ActionItemResponse(BaseModel):
    id: str
    meeting_id: str
    task: str
    owner: str
    due_date: str | None
    status: str
```

### Shared State

```python
class MeetingAgentState(TypedDict):
    # Input
    transcript_segments: list[dict]   # WhisperX segments
    meeting_title: str
    meeting_date: str

    # Accumulated by nodes
    messages: list[BaseMessage]       # ReAct reasoning history
    summary: str
    decisions: list[str]
    action_items: list[ActionItem]    # see ActionItem TypedDict above
    report_markdown: str

    # Control
    meeting_id: str
    job_id: str
```

### Tools (MVP)

| Tool | Responsibility | Typical call order |
|------|---------------|-------------------|
| `analyze_transcript` | Summarize meeting, extract decisions and participants from WhisperX segments | 1st |
| `extract_action_items` | Identify tasks, owners (by speaker), and deadlines | 2nd |
| `search_meetings` | Semantic search over ChromaDB for past meeting context | On demand |
| `generate_report` | Compose markdown report + persist to SQLite | Last |

### Evolution path toward Multi-Agent (post-MVP)

`search_meetings` is designed as a self-contained tool that can be promoted to a dedicated sub-graph (retrieval agent) without modifying the rest of the graph. This is the natural path to an Option C architecture.

---

## 5. Data Layer

### SQLite — Structured persistence

```sql
CREATE TABLE meetings (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    date        TEXT NOT NULL,
    duration_s  REAL,
    speakers    TEXT,              -- JSON array e.g. ["SPEAKER_00","SPEAKER_01"]
    decisions   TEXT,              -- JSON array e.g. ["Beta launch in March"]
    summary     TEXT,
    report_md   TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE action_items (
    id          TEXT PRIMARY KEY,
    meeting_id  TEXT REFERENCES meetings(id),
    task        TEXT NOT NULL,
    owner       TEXT,
    due_date    TEXT,
    status      TEXT DEFAULT 'pending'  -- pending/done/cancelled
);

CREATE TABLE jobs (
    id          TEXT PRIMARY KEY,
    status      TEXT DEFAULT 'processing',  -- processing/done/error
    meeting_id  TEXT,
    error       TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    finished_at TEXT
);
```

### ChromaDB — Semantic search

Each WhisperX segment is indexed as an individual document with rich metadata:

```python
{
    "id": "{meeting_id}-seg-{index}",
    "document": segment["text"],
    "metadata": {
        "meeting_id": "uuid",
        "meeting_title": "Sprint Planning Q1",
        "speaker": "SPEAKER_00",
        "start": 142.3,
        "end": 146.8,
        "date": "2026-03-24"
    }
}
```

**Chunking rationale:** Indexing per-segment (not per-meeting) enables high-resolution retrieval — the search returns the exact moment in the meeting where something was said, with speaker and timestamp. This is the key differentiator over naive RAG implementations.

---

## 6. API Design

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/analyze` | Submit WhisperX JSON → 202 + job_id |
| GET | `/jobs/{job_id}` | Poll job status and result |
| GET | `/meetings` | List all analyzed meetings |
| GET | `/meetings/{id}` | Full meeting with action items |
| GET | `/tasks` | All action items (filterable by status, owner) |
| PATCH | `/tasks/{id}` | Update action item status |
| POST | `/search` | Semantic search over past meetings (see schema below) |

### POST /search — Request and response

```json
// Request
{ "query": "¿quién se comprometió a preparar la demo?", "top_k": 5 }

// Response — list of matching segments, enriched with meeting metadata
{
  "results": [
    {
      "text": "Necesitamos entregar el módulo antes del viernes.",
      "speaker": "SPEAKER_00",
      "start": 142.3,
      "end": 146.8,
      "meeting_id": "uuid",
      "meeting_title": "Sprint Planning Q1",
      "date": "2026-03-24"
    }
  ]
}
```

`top_k` defaults to 5. Results are ordered by semantic similarity (ChromaDB cosine distance).

### Async pattern

```python
@router.post("/analyze", status_code=202)
async def analyze(payload: WhisperXPayload, background: BackgroundTasks):
    job_id = create_job(db)
    background.add_task(run_agent, job_id, payload)
    return {"job_id": job_id, "status": "processing"}

async def run_agent(job_id: str, payload: WhisperXPayload):
    try:
        result = await graph.ainvoke(payload.to_state())
        complete_job(db, job_id, result)
    except Exception as e:
        fail_job(db, job_id, str(e))
```

FastAPI `BackgroundTasks` is sufficient for MVP — no Celery/Redis needed. Limitation: job is lost if the process crashes. Acceptable for portfolio scope.

---

## 7. LLM Provider Configuration

```python
# src/providers/llm.py
def get_llm():
    provider = os.getenv("LLM_PROVIDER", "openai")
    match provider:
        case "openai":  return ChatOpenAI(model="gpt-4o-mini")
        case "claude":  return ChatAnthropic(model="claude-3-5-haiku-latest")
        case "ollama":  return ChatOllama(model="llama3.2")
```

`.env` variables: `LLM_PROVIDER`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `CHROMA_HOST` (default: `chromadb` inside Docker, `localhost` for local dev), `CHROMA_PORT` (default: `8001`)

---

## 8. Docker Compose

```yaml
services:
  api:
    build: .
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [chromadb]
    volumes:
      - ./data/meetings.db:/app/data/meetings.db

  chromadb:
    image: chromadb/chroma:latest
    ports: ["8001:8001"]
    volumes:
      - ./data/chroma:/chroma/chroma

  ollama:           # optional fallback
    image: ollama/ollama
    ports: ["11434:11434"]
    profiles: ["local"]
```

`docker compose up` starts API + ChromaDB.
`docker compose --profile local up` adds Ollama.

---

## 9. Development Phases

| Phase | Focus | Duration |
|-------|-------|----------|
| 1 | LangChain fundamentals — LCEL, tools, memory, basic RAG (`playground/`) | 3-5 days |
| 2 | LangGraph — StateGraph, ReAct, conditionals, checkpointers | 5-7 days |
| 3 | Agent core — full graph + tools + SQLite + ChromaDB | 1-2 weeks |
| 4 | FastAPI + provider config + streaming + logging | 4-6 days |
| 5 | Docker + README + LinkedIn post | 3-4 days |

---

## 10. Quality Criteria

- [ ] `docker compose up` works from a fresh clone with no manual config
- [ ] Agent works with OpenAI, Claude, AND Ollama (env var switch)
- [ ] Each layer (`agent/`, `api/`, `db/`) is independently testable
- [ ] Speaker attribution is preserved in action items
- [ ] Semantic search returns segment-level results with timestamp + speaker
- [ ] README explains the business problem, not just the tech stack
