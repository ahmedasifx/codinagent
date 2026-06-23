"""Langfuse observability — tracing for every agent run.

Provides a single function `get_langfuse_handler()` that returns a
LangChain CallbackHandler wired to Langfuse, or None when Langfuse is not
configured. All callers treat None as "no tracing" so the app runs fine
without credentials.

Usage in runner.py:
    handler = get_langfuse_handler(session_id=..., user_id=..., agent_slug=...)
    config = {"callbacks": [handler], ...} if handler else {"recursion_limit": 150}
"""

from __future__ import annotations

import logging

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


def get_langfuse_handler(
    session_id: str | None = None,
    user_id: str | None = None,
    agent_slug: str | None = None,
    trace_name: str | None = None,
):
    """Return a configured CallbackHandler, or None if Langfuse is not set up.

    Args:
        session_id: conversation/thread ID — groups all turns of one session
        user_id:    end-user identifier (used for user-level filtering in UI)
        agent_slug: which agent is running (attached as a tag)
        trace_name: human-readable trace label (defaults to agent_slug)
    """
    client = _get_client()
    if client is None:
        return None

    try:
        from langfuse.callback import CallbackHandler

        tags = [agent_slug] if agent_slug else []
        return CallbackHandler(
            public_key=get_settings().langfuse_public_key,
            secret_key=get_settings().langfuse_secret_key,
            host=get_settings().langfuse_host,
            session_id=session_id,
            user_id=user_id,
            tags=tags,
            trace_name=trace_name or agent_slug or "agent-run",
        )
    except Exception as e:
        logger.warning("Could not create Langfuse handler: %s", e)
        return None


def flush():
    """Flush pending events — call on app shutdown."""
    client = _get_client()
    if client is not None:
        try:
            client.flush()
        except Exception:
            pass
