"""ContractMind v2.0 1-Click Launcher: configures directories, initializes DB, starts Uvicorn, opens browser."""

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
LOG_FILE = BACKEND_DIR / "backend.log"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.chdir(BACKEND_DIR)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("contractmind.launch")


def _open_browser_when_ready() -> None:
    time.sleep(1.8)
    try:
        webbrowser.open("http://localhost:8000")
    except Exception as exc:
        logger.warning("Could not open browser automatically: %s", exc)


def main() -> None:
    from app.config import settings
    from app.database import init_db
    import uvicorn

    logger.info("Initializing ContractMind v2.0 (%s)", settings.DATABASE_URL)
    asyncio.run(init_db())

    if os.environ.get("CONTRACTMIND_NO_BROWSER") != "1":
        threading.Thread(target=_open_browser_when_ready, daemon=True).start()

    logger.info("Starting Uvicorn server on http://0.0.0.0:8000")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        log_level="info",
    )


if __name__ == "__main__":
    main()
