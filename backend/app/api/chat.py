"""Chat endpoints (SSE). Generalized per-agent streaming + backward-compatible alias."""

import asyncio
import json

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from ..core.config import get_settings
from ..engine.runner import run_agent_stream
from ..schemas.chat import ChatRequest

router = APIRouter()


def _sse(message: str, history, agent_slug: str | None):
    async def event_generator():
        async for event in run_agent_stream(message, history, agent_slug):
            yield {"data": json.dumps(event)}
            await asyncio.sleep(0)

    return EventSourceResponse(event_generator())


@router.post("/agents/{agent_slug}/chat/stream")
async def agent_chat_stream(agent_slug: str, request: ChatRequest):
    history = [{"role": m.role, "content": m.content} for m in request.history]
    return _sse(request.message, history, agent_slug)


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Backward-compatible alias → the default agent (keeps the current frontend working)."""
    history = [{"role": m.role, "content": m.content} for m in request.history]
    return _sse(request.message, history, get_settings().default_agent)
