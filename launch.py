"""Local 1-click launcher for ContractMind v2.0."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def configure_environment() -> None:
    os.chdir(BACKEND_DIR)
    from app.config import settings

    _ = settings.DATA_DIR
    _ = settings.UPLOAD_DIR
    _ = settings.CHROMA_PERSIST_DIR


def setup_logging() -> Path:
    log_path = BACKEND_DIR / "backend.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return log_path


def run_migrations() -> None:
    from app.database import init_db
    from app.services.rag_engine import rag_engine

    asyncio.run(init_db())
    count = rag_engine.index_knowledge_base()
    logging.getLogger("contractmind.launcher").info(
        "Database initialized and %d legal precedents indexed.", count
    )


def open_browser_delayed(url: str = "http://localhost:8000") -> None:
    time.sleep(1.5)
    try:
        webbrowser.open(url)
    except Exception:
        pass


def main() -> None:
    configure_environment()
    log_path = setup_logging()
    run_migrations()

    print(f"ContractMind v2.0 starting on http://localhost:8000 (logs: {log_path})")
    threading.Thread(target=open_browser_delayed, daemon=True).start()

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
