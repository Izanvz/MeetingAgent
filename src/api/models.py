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


class JobStepResponse(BaseModel):
    step_key: str
    sort_order: int
    label: str
    detail: str | None = None
    status: str


class JobLogResponse(BaseModel):
    timestamp: str
    level: str
    message: str


class JobResponse(BaseModel):
    job_id: str
    status: str
    stage: str | None = None
    stage_detail: str | None = None
    meeting_id: str | None = None
    error: str | None = None
    summary: str | None = None
    decisions: list[str] | None = None
    participants: list[str] | None = None
    action_items: list[ActionItemResponse] | None = None
    report: str | None = None
    steps: list[JobStepResponse] | None = None
    logs: list[JobLogResponse] | None = None


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


class SystemServiceStatus(BaseModel):
    status: str
    detail: str | None = None


class SystemStats(BaseModel):
    meetings: int
    tasks_pending: int
    tasks_done: int


class SystemConfig(BaseModel):
    runtime_mode: str
    llm_provider: str
    ollama_model: str | None = None
    whisper_model: str
    whisper_device: str
    whisper_compute_type: str
    chroma_host: str
    chroma_port: int


class SystemStatusResponse(BaseModel):
    api: SystemServiceStatus
    database: SystemServiceStatus
    chroma: SystemServiceStatus
    ollama: SystemServiceStatus
    config: SystemConfig
    stats: SystemStats
