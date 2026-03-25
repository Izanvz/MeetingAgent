import os
from fastapi import APIRouter
from src.api.models import SearchRequest, SearchResponse, SearchResult
from src.db.vector_store import VectorStore

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
def search_meetings(body: SearchRequest):
    store = VectorStore(
        host=os.getenv("CHROMA_HOST", "localhost"),
        port=int(os.getenv("CHROMA_PORT", "8001")),
    )
    raw = store.search(query=body.query, top_k=body.top_k)
    return SearchResponse(results=[SearchResult(**r) for r in raw])
