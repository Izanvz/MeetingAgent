from fastapi import APIRouter, Depends, HTTPException
from src.api.models import MeetingResponse, MeetingDetailResponse, ActionItemResponse
from src.api.deps import get_db
from src.db.sqlite import Database

router = APIRouter()


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
