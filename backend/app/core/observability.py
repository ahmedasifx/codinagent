"""Langfuse observability — tracing + scoring for every agent run.

`start_trace()` creates a trace with a KNOWN id and returns (trace_id, handler) so the
caller can (a) attach the handler to LangGraph and (b) later attach scores (user feedback,
evals) to that same trace_id. `score()` pushes a score. All functions are no-ops when
Langfuse is unconfigured, so the app runs fine without credentials.

Usage in runner.py:
    trace_id, handler = start_trace(session_id=..., agent_slug=..., name=...)
    config = {"callbacks": [handler], ...} if handler else {"recursion_limit": 150}
    if trace_id: yield {"type": "trace", "trace_id": trace_id}
"""

from __future__ import annotations

import logging
import uuid

from .config import get_settings

logger = logging.getLogger(__name__)

_langfuse_client = None
_langfuse_init_attempted = False


def _get_client():
    """Lazy-init the Langfuse client (one per process). Returns None if not configured."""
    global _langfuse_client, _langfuse_init_attempted
    if _langfuse_init_attempted:
        return _langfuse_client
    _langfuse_init_attempted = True

    s = get_settings()
    if not s.langfuse_public_key or not s.langfuse_secret_key:
        return None

    try:
        from langfuse import Langfuse

        _langfuse_client = Langfuse(
            public_key=s.langfuse_public_key,
            secret_key=s.langfuse_secret_key,
            host=s.langfuse_host,
        )
        logger.info("Langfuse tracing enabled → %s", s.langfuse_host)
    except Exception as e:
        logger.warning("Langfuse init failed (tracing disabled): %s", e)

    return _langfuse_client


def start_trace(
    session_id: str | None = None,
    user_id: str | None = None,
    agent_slug: str | None = None,
    name: str | None = None,
) -> tuple[str | None, object | None]:
    """Create a trace with a known id and return (trace_id, langchain_handler).

    Returns (None, None) when Langfuse is unconfigured/unavailable. The trace_id lets the
    caller surface it to the client and attach scores (feedback / evals) to the same trace.

    Args:
        session_id: conversation/thread ID — groups all turns of one session
        user_id:    end-user identifier (user-level filtering in the UI)
        agent_slug: which agent is running (attached as a tag)
        name:       human-readable trace label (defaults to agent_slug)
    """
    client = _get_client()
    if client is None:
        return None, None

    try:
        trace_id = str(uuid.uuid4())
        trace = client.trace(
            id=trace_id,
            name=name or agent_slug or "agent-run",
            session_id=session_id,
            user_id=user_id,
            tags=[agent_slug] if agent_slug else [],
        )
        return trace_id, trace.get_langchain_handler()
    except Exception as e:
        # Keys ARE configured but trace/handler creation failed — a real misconfiguration
        # (wrong SDK version, bad host), not "disabled". Log loudly so it can't hide.
        logger.error("Langfuse start_trace FAILED (tracing off): %s", e, exc_info=True)
        return None, None


def score(
    trace_id: str,
    name: str,
    value: float,
    comment: str | None = None,
    data_type: str = "NUMERIC",
) -> bool:
    """Attach a score to a trace (user feedback, eval, heuristic). No-op if disabled."""
    client = _get_client()
    if client is None or not trace_id:
        return False
    try:
        client.score(
            trace_id=trace_id, name=name, value=value, comment=comment, data_type=data_type
        )
        client.flush()
        return True
    except Exception as e:
        logger.error("Langfuse score FAILED: %s", e, exc_info=True)
        return False


def flush():
    """Flush pending events — call on app shutdown."""
    client = _get_client()
    if client is not None:
        try:
            client.flush()
        except Exception:
            pass
