"""Minimal .env loader used by the operational scripts (no third-party dependency).

Existing environment variables always win, so CI/production secrets are never overridden
by a stray local file.
"""
from __future__ import annotations

import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_dotenv(path: pathlib.Path | None = None) -> None:
    env_file = path or ROOT / ".env"
    if not env_file.exists():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
