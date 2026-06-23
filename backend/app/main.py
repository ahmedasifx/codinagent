"""FastAPI app for the AI Agent Platform. Replaces the original backend/main.py."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import agents, artifacts, chat, credentials, mcp, tools
from .core.config import get_settings
from .core.observability import flush as flush_langfuse
from .core.sandbox import MANAGER
from .registries.loader import load_builtins


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_builtins()
    yield
    MANAGER.close_all()
    flush_langfuse()


app = FastAPI(title="AI Agent Platform API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(agents.router)
app.include_router(tools.router)
app.include_router(credentials.router)
app.include_router(mcp.router)
app.include_router(artifacts.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.delete("/sandbox")
async def reset_sandbox():
    MANAGER.close_all()
    return {"status": "sandbox_reset"}
