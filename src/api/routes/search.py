from fastapi import APIRouter, Depends
from src.api.models import SearchRequest, SearchResponse, SearchResult
from src.api.deps import get_vector_store
from src.db.vector_store import VectorStore

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
def search_meetings(body: SearchRequest, store: VectorStore = Depends(get_vector_store)):
    raw = store.search(query=body.query, top_k=body.top_k)
    return SearchResponse(results=[SearchResult(**r) for r in raw])
