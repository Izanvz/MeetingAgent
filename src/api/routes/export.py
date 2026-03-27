from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from src.api.deps import get_db
from src.db.sqlite import Database
from src.integrations.registry import get_exporter, SUPPORTED_TARGETS

router = APIRouter()


class ExportRequest(BaseModel):
    target: str = Field(..., description=f"Export destination. One of: {SUPPORTED_TARGETS}")
    config: dict = Field(default_factory=dict, description="Target-specific config (e.g. webhook URL)")


class ExportResponse(BaseModel):
    target: str
    dry_run: bool
    meeting_id: str
    created_ids: list[str]
    payload_preview: list[dict]
    message: str


@router.post("/meetings/{meeting_id}/export", response_model=ExportResponse)
async def export_meeting(
    meeting_id: str,
    body: ExportRequest,
    db: Database = Depends(get_db),
):
    meeting = db.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    action_items = db.list_action_items(meeting_id=meeting_id)
    if not action_items:
        raise HTTPException(status_code=422, detail="No action items to export for this meeting")

    try:
        exporter = get_exporter(body.target)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        result = await exporter.export(
            meeting_id=meeting_id,
            meeting_title=meeting["title"],
            action_items=action_items,
            config=body.config,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"{body.target} API error: {e}")

    return ExportResponse(
        target=result.target,
        dry_run=result.dry_run,
        meeting_id=result.meeting_id,
        created_ids=result.created_ids,
        payload_preview=result.payload_preview,
        message=result.message,
    )
