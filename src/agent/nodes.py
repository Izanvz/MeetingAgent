import json
import uuid

from src.agent.state import MeetingAgentState
from src.agent.tools import (
    analyze_transcript,
    extract_action_items,
    generate_report,
    get_vector_store,
)
from src.db.sqlite import Database

import os


def _get_db() -> Database:
    return Database(os.getenv("DB_PATH", "data/meetings.db"))


def node_analyze(state: MeetingAgentState) -> dict:
    """Step 1: summarise the transcript and extract decisions."""
    db = _get_db()
    db.update_job_stage(state["job_id"], "summarizing", "Ollama está leyendo la transcripción para resumirla y extraer decisiones")
    segments_json = json.dumps(state["transcript_segments"])
    result = analyze_transcript.invoke({"segments_json": segments_json})
    db.add_job_log(state["job_id"], "info", f"Resumen generado con {len(result.get('decisions', []))} decisiones")
    return {
        "summary": result.get("summary", ""),
        "decisions": result.get("decisions", []),
    }


def node_extract(state: MeetingAgentState) -> dict:
    """Step 2: extract action items with owners and deadlines."""
    db = _get_db()
    db.update_job_stage(state["job_id"], "extracting", "Ollama está detectando tareas, responsables y fechas de entrega")
    segments_json = json.dumps(state["transcript_segments"])
    result = extract_action_items.invoke({"segments_json": segments_json})
    db.add_job_log(state["job_id"], "info", f"Action items detectados: {len(result.get('action_items', []))}")
    return {"action_items": result.get("action_items", [])}


def node_report(state: MeetingAgentState) -> dict:
    """Step 3: generate markdown report (LLM only, no side effects)."""
    db = _get_db()
    db.update_job_stage(state["job_id"], "reporting", "Componiendo reporte markdown final de la reunión")
    result = generate_report.invoke({
        "meeting_title": state["meeting_title"],
        "meeting_date": state["meeting_date"],
        "summary": state["summary"],
        "decisions_json": json.dumps(state["decisions"]),
        "action_items_json": json.dumps(state["action_items"]),
    })
    db.add_job_log(state["job_id"], "info", "Reporte markdown generado")
    return {"report_markdown": result.get("report_markdown", "")}


def node_persist(state: MeetingAgentState) -> dict:
    """Step 4: persist to ChromaDB and SQLite (side effects only)."""
    db = _get_db()
    db.update_job_stage(state["job_id"], "indexing", "Indexando segmentos en Chroma para búsqueda semántica")
    segments = state["transcript_segments"]
    speakers = list({seg.get("speaker", "") for seg in segments if seg.get("speaker")})
    duration_s = max((seg.get("end", 0) for seg in segments), default=None)

    # ChromaDB first - if this fails, nothing is persisted (consistent state)
    get_vector_store().index_segments(
        meeting_id=state["meeting_id"],
        meeting_title=state["meeting_title"],
        date=state["meeting_date"],
        segments=segments,
    )
    db.add_job_log(state["job_id"], "info", f"Segmentos indexados en Chroma: {len(segments)}")

    # SQLite after - only runs if ChromaDB succeeded
    db.update_job_stage(state["job_id"], "saving", "Guardando reunión, speakers y action items en SQLite")
    db.create_meeting({
        "id": state["meeting_id"],
        "title": state["meeting_title"],
        "date": state["meeting_date"],
        "duration_s": duration_s,
        "speakers": speakers,
        "decisions": state["decisions"],
        "summary": state["summary"],
        "report_md": state["report_markdown"],
    })
    for item in state["action_items"]:
        db.create_action_item({
            "id": str(uuid.uuid4()),
            "meeting_id": state["meeting_id"],
            **item,
        })
    db.add_job_log(state["job_id"], "info", f"Persistencia finalizada con {len(state['action_items'])} action items")
    return {}
