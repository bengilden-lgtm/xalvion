"""
Local dev entrypoint — respects PORT (Railway/Render/Fly) and optional UVICORN_RELOAD=true.
"""
# Single worker required for SQLite + file-based brain.json. Set DATABASE_URL to Postgres before increasing WEB_CONCURRENCY.
from __future__ import annotations

import os

import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    reload = (os.getenv("UVICORN_RELOAD", "") or "").strip().lower() in {"1", "true", "yes"}
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=reload)
