"""
Railway / Render pre-deploy entrypoint: create database tables without importing app:app.

Run:
    python deploy_init_db.py

This loads only ``db`` + ORM modules (see ``db.ensure_orm_metadata_imported``) so
pre-deploy stays fast and never pulls the full FastAPI import graph.
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    print("BOOT: predeploy deploy_init_db.py starting", flush=True)
    try:
        from dotenv import load_dotenv

        load_dotenv(override=False)
        print("BOOT: predeploy dotenv loaded (if present)", flush=True)
    except Exception as exc:
        print(f"BOOT: predeploy dotenv skipped err={type(exc).__name__}", flush=True)

    env = (os.getenv("ENVIRONMENT", "development") or "development").strip().lower()
    print(f"BOOT: predeploy ENVIRONMENT={env!r}", flush=True)

    try:
        print("BOOT: predeploy importing db (engine configuration)", flush=True)
        import db  # noqa: F401 — side effect: engine + logging

        from db import init_db

        print("BOOT: predeploy calling init_db()", flush=True)
        init_db()
    except Exception as exc:
        print(
            f"BOOT: predeploy FAILED err={type(exc).__name__}: {exc!s}"[:800],
            flush=True,
        )
        raise
    print("BOOT: predeploy init_db finished OK", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
