"""
FastAPI server — exposes the coding agent via SSE streaming.
"""

import json
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel

from agent import run_agent_stream, close_sandbox


# ── Lifespan ───────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    close_sandbox()


app = FastAPI(title="Coding Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response schemas ─────────────────────────────────────────────────
class Message(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[Message] = []


# ── Endpoints ──────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """SSE stream of agent events."""

    history = [{"role": m.role, "content": m.content} for m in request.history]

    async def event_generator():
        async for event in run_agent_stream(request.message, history):
            yield {"data": json.dumps(event)}
            await asyncio.sleep(0)  # yield control to event loop

    return EventSourceResponse(event_generator())


@app.delete("/sandbox")
async def reset_sandbox():
    """Kill the current E2B sandbox — useful to start fresh."""
    close_sandbox()
    return {"status": "sandbox_reset"}
