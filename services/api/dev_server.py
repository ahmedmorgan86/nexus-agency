"""Local API server: loads the repo .env, then runs uvicorn.

  cd services/api && python dev_server.py [--port 8000]

Production must not use this: set real environment variables and run
`uvicorn app.main:app` behind a process manager.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from _env import load_dotenv  # noqa: E402

load_dotenv()

import uvicorn  # noqa: E402

if __name__ == "__main__":
    port = 8000
    argv = sys.argv[1:]
    if "--port" in argv:
        port = int(argv[argv.index("--port") + 1])
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, log_level="info")
