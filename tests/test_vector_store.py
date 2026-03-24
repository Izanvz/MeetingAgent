# tests/test_vector_store.py
import uuid
import pytest
from src.db.vector_store import VectorStore

@pytest.fixture
def store():
    return VectorStore(ephemeral=True, collection_name=f"test_{uuid.uuid4().hex}")

def test_index_and_search(store):
    segments = [
        {"start": 0.0, "end": 4.2, "speaker": "SPEAKER_00",
         "text": "We need to deliver the module by Friday."},
        {"start": 5.0, "end": 9.0, "speaker": "SPEAKER_01",
         "text": "The budget is approved for Q1."},
    ]
    store.index_segments(
        meeting_id="m-001",
        meeting_title="Sprint Planning",
        date="2026-03-24",
        segments=segments,
    )
    results = store.search("deadline for module delivery", top_k=1)
    assert len(results) == 1
    assert "module" in results[0]["text"].lower()
    assert results[0]["speaker"] == "SPEAKER_00"
    assert results[0]["meeting_id"] == "m-001"

def test_search_returns_metadata(store):
    segments = [{"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00", "text": "Launch the beta in March."}]
    store.index_segments("m-002", "Product Meeting", "2026-03-24", segments)
    results = store.search("beta launch", top_k=1)
    r = results[0]
    assert "start" in r
    assert "end" in r
    assert "meeting_title" in r
    assert "date" in r
