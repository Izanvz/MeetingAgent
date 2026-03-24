from fastapi import FastAPI
from src.api.routes.analyze import router as analyze_router


def create_app(db_path: str = "data/meetings.db") -> FastAPI:
    import src.api.routes.analyze as analyze_module
    analyze_module._db_path = db_path
    app = FastAPI(title="MeetingAgent API")
    app.include_router(analyze_router)
    return app


app = create_app()
