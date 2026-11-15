"""ContractMind v2.0 FastAPI Entrypoint with Lifespan DB Initialization, API Routers, MCP Gateway & Studio SPA."""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import analysis, auth, contracts, copilot, playbook, stream
from app.config import settings
from app.database import ensure_db_initialized
from app.mcp_server.fastserver import mcp_router

STATIC_DIR = BACKEND_DIR / "static"
INDEX_HTML = STATIC_DIR / "index.html"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize SQLite schema and default playbooks on startup."""
    await ensure_db_initialized()
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

# Model Context Protocol (MCP) Gateway
app.include_router(mcp_router)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health")
async def health_check() -> JSONResponse:
    """Service health probe."""
    return JSONResponse({"status": "healthy", "version": "2.0.0"})


@app.get("/", include_in_schema=False)
@app.get("/studio", include_in_schema=False)
async def serve_studio() -> FileResponse:
    """Serve the Warm Editorial Neo-Legal Studio v2.1 Single-Page Application."""
    if not INDEX_HTML.exists():
        return JSONResponse({"error": "Frontend index.html not found"}, status_code=404)  # type: ignore[return-value]
    return FileResponse(str(INDEX_HTML), media_type="text/html")
