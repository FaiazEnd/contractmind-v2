"""Local 1-click launcher for ContractMind v2.0."""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _configure_logging() -> None:
    log_path = BACKEND_DIR / "backend.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def _open_browser_delayed(url: str) -> None:
    time.sleep(1.5)
    try:
        webbrowser.open(url)
    except Exception:
        pass


def main() -> None:
    from app.config import settings
    from app.database import init_db
    import uvicorn

    Path(settings.CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    _configure_logging()

    asyncio.run(init_db())
    threading.Thread(target=_open_browser_delayed, args=("http://localhost:8000",), daemon=True).start()

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
