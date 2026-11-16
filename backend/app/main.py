"""ContractMind v2.0 FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse

from app.api.v1 import analysis, auth, contracts, copilot, playbook, stream
from app.config import settings
from app.database import init_db
from app.mcp_server.fastserver import router as mcp_router
from app.services.rag_engine import rag_engine


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize SQLite schema, default playbooks, and 2,000 SEC EDGAR precedents."""
    await init_db()
    rag_engine.index_knowledge_base()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Autonomous Multi-Agent Legal Intelligence, Negotiation & Deal Room Suite",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API v1 Routers
app.include_router(contracts.router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")
app.include_router(copilot.router, prefix="/api/v1")
app.include_router(playbook.router, prefix="/api/v1")
app.include_router(stream.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")

# Model Context Protocol (MCP) Server
app.include_router(mcp_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy", "version": settings.APP_VERSION}


@app.get("/", response_model=None)
@app.get("/studio", response_model=None)
async def serve_studio() -> FileResponse | HTMLResponse:
    index_path = settings.STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return HTMLResponse(
        "<h1>ContractMind v2.0</h1><p>Studio frontend not found at backend/static/index.html.</p>"
    )
