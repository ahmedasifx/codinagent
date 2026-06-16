"""Central settings, loaded from environment (.env)."""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env regardless of the process's current working directory. (Bare
# load_dotenv() searches up from cwd, which silently misses the file when uvicorn is
# launched from elsewhere. In Docker there is no .env — env_file injects the vars — so
# a missing file here is harmless.)
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_BACKEND_ROOT / ".env")


class Settings:
    def __init__(self) -> None:
        # LLM (OpenRouter, OpenAI-compatible)
        self.openrouter_api_key: str = os.environ.get("OPENROUTER_API_KEY", "")
        self.openrouter_model: str = os.environ.get(
            "OPENROUTER_MODEL", "deepseek/deepseek-coder"
        )
        self.openrouter_base_url: str = "https://openrouter.ai/api/v1"
        self.embedding_model: str = os.environ.get(
            "EMBEDDING_MODEL", "openai/text-embedding-3-small"
        )

        # Sandbox
        self.e2b_api_key: str = os.environ.get("E2B_API_KEY", "")

        # Persistence — empty DATABASE_URL means "DB-less mode": core (code-defined)
        # agents/skills/tools still work; custom records, memory, and run history are
        # simply not persisted.
        self.database_url: str = os.environ.get("DATABASE_URL", "")

        # Artifact store (local disk for dev; swap for S3 behind core/artifacts.py)
        self.artifact_dir: str = os.environ.get(
            "ARTIFACT_DIR", os.path.join(os.getcwd(), "artifact_store")
        )

        # Single-user defaults (multi-tenant later — schema already carries owner_id)
        self.system_user_id: str = os.environ.get(
            "SYSTEM_USER_ID", "00000000-0000-0000-0000-000000000001"
        )
        self.default_agent: str = os.environ.get("DEFAULT_AGENT", "coding_agent")

        # CORS
        self.cors_origins: list[str] = os.environ.get(
            "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
        ).split(",")


@lru_cache
def get_settings() -> Settings:
    return Settings()
