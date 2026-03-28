from dotenv import load_dotenv
load_dotenv()

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from src.api.routes.analyze import router as analyze_router
from src.api.routes.meetings import router as meetings_router
from src.api.routes.tasks import router as tasks_router
from src.api.routes.search import router as search_router
from src.api.routes.audio import router as audio_router
from src.api.routes.export import router as export_router

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


def create_app(db_path: str = "data/meetings.db") -> FastAPI:
    import src.api.deps as deps
    deps._db_path = db_path
    deps.get_db.cache_clear()
    deps.get_vector_store.cache_clear()

    app = FastAPI(title="MeetingAgent API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:8000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(analyze_router)
    app.include_router(meetings_router)
    app.include_router(tasks_router)
    app.include_router(search_router)
    app.include_router(audio_router)
    app.include_router(export_router)

    @app.get("/", include_in_schema=False)
    async def dashboard():
        return FileResponse(os.path.join(_STATIC_DIR, "index.html"))

    if os.path.isdir(_STATIC_DIR):
        app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    return app


app = create_app()
