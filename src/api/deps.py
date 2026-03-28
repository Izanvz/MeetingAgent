import os
from functools import lru_cache

from src.db.sqlite import Database
from src.db.vector_store import VectorStore

_db_path = "data/meetings.db"


@lru_cache(maxsize=1)
def get_db() -> Database:
    return Database(_db_path)


@lru_cache(maxsize=1)
def get_vector_store() -> VectorStore:
    ephemeral = os.getenv("CHROMA_EPHEMERAL", "0").lower() in ("1", "true", "yes")
    return VectorStore(
        host=os.getenv("CHROMA_HOST", "localhost"),
        port=int(os.getenv("CHROMA_PORT", "8001")),
        ephemeral=ephemeral,
    )
