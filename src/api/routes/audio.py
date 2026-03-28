import asyncio
import tempfile
import os
from datetime import date
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, Form
from src.api.models import JobResponse, AnalyzeRequest
from src.api.deps import get_db
from src.db.sqlite import Database
from src.api.routes.analyze import run_agent

router = APIRouter()

ALLOWED_EXTENSIONS = {".mp3", ".mp4", ".wav", ".m4a", ".ogg", ".flac", ".webm"}
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB


@router.post("/meetings/audio", status_code=202, response_model=JobResponse)
async def analyze_audio(
    background: BackgroundTasks,
    db: Database = Depends(get_db),
    file: UploadFile = File(...),
    title: str = Form(default=""),
    meeting_date: str = Form(default=""),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds 500 MB limit")

    resolved_title = title or (file.filename or "Untitled meeting").rsplit(".", 1)[0]
    resolved_date = meeting_date or date.today().isoformat()

    job_id = db.create_job()
    background.add_task(_transcribe_and_analyze, job_id, content, ext, resolved_title, resolved_date)
    return JobResponse(job_id=job_id, status="processing")


async def _transcribe_and_analyze(
    job_id: str,
    audio_bytes: bytes,
    ext: str,
    title: str,
    meeting_date: str,
):
    from src.transcription.whisper import transcribe

    db = get_db()

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        segments = await asyncio.to_thread(transcribe, tmp_path)
        if not segments:
            db.fail_job(job_id, "Transcription returned no segments - check audio quality")
            return

        payload = AnalyzeRequest(title=title, date=meeting_date, segments=segments)
        await run_agent(job_id, payload)

    except Exception as e:
        db.fail_job(job_id, str(e))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
