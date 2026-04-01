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
from src.api.routes.system import router as system_router

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


def _serve_app_shell() -> FileResponse:
    return FileResponse(os.path.join(_STATIC_DIR, "index.html"))


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
    app.include_router(system_router)

    @app.get("/", include_in_schema=False)
    async def dashboard():
        return _serve_app_shell()

    @app.get("/app/upload", include_in_schema=False)
    async def upload_page():
        return _serve_app_shell()

    @app.get("/app/meetings", include_in_schema=False)
    async def meetings_page():
        return _serve_app_shell()

    @app.get("/app/search", include_in_schema=False)
    async def search_page():
        return _serve_app_shell()

    @app.get("/app/setup", include_in_schema=False)
    async def setup_page():
        return _serve_app_shell()

    if os.path.isdir(_STATIC_DIR):
        app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    return app


app = create_app()
