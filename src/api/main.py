from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from src.api.routes.analyze import router as analyze_router
from src.api.routes.meetings import router as meetings_router
from src.api.routes.tasks import router as tasks_router
from src.api.routes.search import router as search_router


def create_app(db_path: str = "data/meetings.db") -> FastAPI:
    import src.api.deps as deps
    deps._db_path = db_path
    deps.get_db.cache_clear()
    deps.get_vector_store.cache_clear()
    app = FastAPI(title="MeetingAgent API")
    app.include_router(analyze_router)
    app.include_router(meetings_router)
    app.include_router(tasks_router)
    app.include_router(search_router)
    return app


app = create_app()
