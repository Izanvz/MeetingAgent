import os

import httpx
from fastapi import APIRouter, Depends

from src.api.deps import get_db
from src.api.models import (
    SystemConfig,
    SystemServiceStatus,
    SystemStats,
    SystemStatusResponse,
)
from src.db.sqlite import Database

router = APIRouter()


def _detect_runtime_mode() -> str:
    if os.getenv("MEETINGAGENT_RUNTIME_MODE"):
        return os.getenv("MEETINGAGENT_RUNTIME_MODE", "local")
    if os.path.exists("/.dockerenv"):
        return "docker"
    if os.getenv("KUBERNETES_SERVICE_HOST"):
        return "container"
    return "local"


async def _check_ollama(base_url: str, model: str | None) -> SystemServiceStatus:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{base_url.rstrip('/')}/api/tags")
            response.raise_for_status()
            data = response.json()
        models = [item.get("name") for item in data.get("models", [])]
        if model and model not in models:
            return SystemServiceStatus(status="degraded", detail=f"Modelo configurado no descargado: {model}")
        detail = model or (models[0] if models else "sin modelo configurado")
        return SystemServiceStatus(status="online", detail=detail)
    except Exception as exc:
        return SystemServiceStatus(status="offline", detail=str(exc))


async def _check_chroma(host: str, port: int) -> SystemServiceStatus:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"http://{host}:{port}/api/v2/heartbeat")
            response.raise_for_status()
        return SystemServiceStatus(status="online", detail=f"{host}:{port}")
    except Exception as exc:
        return SystemServiceStatus(status="offline", detail=str(exc))


def _check_database(db: Database) -> SystemServiceStatus:
    try:
        db.conn.execute("SELECT 1")
        return SystemServiceStatus(status="online", detail="SQLite disponible")
    except Exception as exc:
        return SystemServiceStatus(status="offline", detail=str(exc))


@router.get("/system/status", response_model=SystemStatusResponse)
async def get_system_status(db: Database = Depends(get_db)):
    llm_provider = os.getenv("LLM_PROVIDER", "ollama")
    ollama_model = os.getenv("OLLAMA_MODEL")
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    chroma_host = os.getenv("CHROMA_HOST", "localhost")
    chroma_port = int(os.getenv("CHROMA_PORT", "8001"))

    meetings = db.list_meetings()
    tasks_pending = len(db.list_action_items(status="pending"))
    tasks_done = len(db.list_action_items(status="done"))

    ollama_status = await _check_ollama(ollama_base_url, ollama_model) if llm_provider == "ollama" else SystemServiceStatus(
        status="external",
        detail=llm_provider,
    )

    return SystemStatusResponse(
        api=SystemServiceStatus(status="online", detail="FastAPI disponible"),
        database=_check_database(db),
        chroma=await _check_chroma(chroma_host, chroma_port),
        ollama=ollama_status,
        config=SystemConfig(
            runtime_mode=_detect_runtime_mode(),
            llm_provider=llm_provider,
            ollama_model=ollama_model,
            whisper_model=os.getenv("WHISPER_MODEL", "base"),
            whisper_device=os.getenv("WHISPER_DEVICE", "cuda"),
            whisper_compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "float16"),
            chroma_host=chroma_host,
            chroma_port=chroma_port,
        ),
        stats=SystemStats(
            meetings=len(meetings),
            tasks_pending=tasks_pending,
            tasks_done=tasks_done,
        ),
    )
