import uuid
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from src.api.models import AnalyzeRequest, JobResponse
from src.api.deps import get_db
from src.agent.graph import build_graph
from src.agent.state import MeetingAgentState
from src.db.sqlite import Database

router = APIRouter()
_graph = build_graph()


async def run_agent(job_id: str, payload: AnalyzeRequest):
    db = get_db()
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
        if meeting is None:
            return JobResponse(job_id=job["id"], status="error",
                               error="Meeting analysed but not persisted — check agent logs")
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
