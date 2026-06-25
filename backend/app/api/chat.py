"""Chat endpoints (SSE). Generalized per-agent streaming + backward-compatible alias."""

import asyncio
import json

from fastapi import APIRouter
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from ..core.config import get_settings
from ..core.observability import score as lf_score
from ..engine.runner import run_agent_stream
from ..schemas.chat import ChatRequest

router = APIRouter()


class FeedbackRequest(BaseModel):
    trace_id: str
    value: float  # 1 = thumbs up, 0 = thumbs down
    comment: str | None = None


@router.post("/feedback", status_code=204)
async def submit_feedback(req: FeedbackRequest):
    """Attach a user-feedback score to a run's Langfuse trace. No-op if Langfuse is off."""
    lf_score(req.trace_id, name="user_feedback", value=req.value, comment=req.comment)


def _sse(message: str, history, agent_slug: str | None, request: ChatRequest):
    async def event_generator():
        async for event in run_agent_stream(
            message, history, agent_slug,
            planning=request.planning,
            approved_plan=request.approved_plan,
            session_id=request.session_id,
        ):
            yield {"data": json.dumps(event)}
            await asyncio.sleep(0)

    return EventSourceResponse(event_generator())


@router.post("/agents/{agent_slug}/chat/stream")
async def agent_chat_stream(agent_slug: str, request: ChatRequest):
    history = [{"role": m.role, "content": m.content} for m in request.history]
    return _sse(request.message, history, agent_slug, request)


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Backward-compatible alias → the default agent (keeps the current frontend working)."""
    history = [{"role": m.role, "content": m.content} for m in request.history]
    return _sse(request.message, history, get_settings().default_agent, request)
