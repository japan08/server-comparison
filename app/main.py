from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api.router import api_router
from app.core.database import engine
from app.core.config import get_settings
from app.models import Base

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.database_url.startswith("sqlite+aiosqlite:///"):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="Cloud Compare",
    description="AI-powered cloud server price comparison API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/", include_in_schema=False)
def serve_frontend():
    """Serve the CloudCompare single-page frontend."""
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"message": "Frontend not found. Run from project root."}
