from pydantic import BaseModel


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
    status: str


class ActionItemResponse(BaseModel):
    id: str
    meeting_id: str
    task: str
    owner: str | None
    due_date: str | None
    status: str


class JobResponse(BaseModel):
    job_id: str
    status: str
    meeting_id: str | None = None
    error: str | None = None
    summary: str | None = None
    decisions: list[str] | None = None
    participants: list[str] | None = None
    action_items: list[ActionItemResponse] | None = None
    report: str | None = None


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
