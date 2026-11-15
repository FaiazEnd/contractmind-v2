"""ContractMind v2.0 FastAPI entrypoint with lifespan DB init, REST v1, MCP gateway, and Studio UI."""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import analysis, auth, contracts, copilot, playbook, stream
from app.config import settings
from app.database import ensure_db_initialized
from app.mcp_server.fastserver import router as mcp_router

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
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
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API v1 routers
app.include_router(contracts.router, prefix="/api/v1/contracts", tags=["Contracts"])
app.include_router(analysis.router, prefix="/api/v1/analysis", tags=["Analysis & Deal Room"])
app.include_router(copilot.router, prefix="/api/v1/copilot", tags=["Legal AI Copilot"])
app.include_router(playbook.router, prefix="/api/v1/playbooks", tags=["Playbooks"])
app.include_router(stream.router, prefix="/api/v1/stream", tags=["Streaming"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])

# Model Context Protocol (MCP) JSON-RPC gateway
app.include_router(mcp_router, prefix="/mcp", tags=["MCP Gateway"])

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health", tags=["System"])
async def health_check() -> JSONResponse:
    return JSONResponse({"status": "healthy", "version": "2.0.0"})


@app.get("/", include_in_schema=False)
@app.get("/studio", include_in_schema=False)
async def serve_studio() -> FileResponse:
    index_path = STATIC_DIR / "index.html"
    return FileResponse(str(index_path), media_type="text/html")
