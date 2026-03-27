import os
from faster_whisper import WhisperModel
from src.api.models import TranscriptSegment

# Model size configurable via env var.
# Options: tiny, base, small, medium, large-v3
# GTX 1660 (6GB VRAM): base/small safe, medium works, large-v3 risky alongside Ollama
_MODEL_SIZE = os.getenv("WHISPER_MODEL", "base")
_DEVICE = os.getenv("WHISPER_DEVICE", "cuda")
_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "float16")

_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel(_MODEL_SIZE, device=_DEVICE, compute_type=_COMPUTE_TYPE)
    return _model


def transcribe(audio_path: str) -> list[TranscriptSegment]:
    """Transcribe an audio file and return transcript segments.

    Speaker diarization is not included — all segments are labeled
    'Speaker 1'. Pass the result through the existing LangGraph pipeline
    which extracts participants from context when possible.
    """
    model = _get_model()
    segments, _ = model.transcribe(audio_path, beam_size=5)
    return [
        TranscriptSegment(
            start=seg.start,
            end=seg.end,
            speaker="Speaker 1",
            text=seg.text.strip(),
        )
        for seg in segments
        if seg.text.strip()
    ]
