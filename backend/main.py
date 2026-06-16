"""Compatibility shim. The app now lives in app/main.py (the AI Agent Platform).

Keeps `uvicorn main:app` (CLAUDE.md / Dockerfile) working during/after the migration.
"""

from app.main import app  # noqa: F401
