"""Tiny Redis cache with a no-op fallback.

Used to cache expensive crawl/scrape results across runs and users (the cost lever for
lead generation). When REDIS_URL is unset or Redis is unreachable, every call is a no-op
so the app behaves exactly as before — mirrors the DB-less / no-key pattern used elsewhere.
"""

from __future__ import annotations

import logging

from .config import get_settings

logger = logging.getLogger(__name__)

_client = None
_init_attempted = False


def _get_client():
    global _client, _init_attempted
    if _init_attempted:
        return _client
    _init_attempted = True

    url = get_settings().redis_url
    if not url:
        return None
    try:
        import redis

        _client = redis.from_url(url, decode_responses=True, socket_timeout=2)
        _client.ping()
        logger.info("Cache enabled → Redis")
    except Exception as e:
        logger.warning("Redis cache unavailable (caching disabled): %s", e)
        _client = None
    return _client


def get(key: str) -> str | None:
    client = _get_client()
    if client is None:
        return None
    try:
        return client.get(key)
    except Exception:
        return None


def set(key: str, value: str, ttl_seconds: int = 86400) -> None:
    client = _get_client()
    if client is None:
        return
    try:
        client.set(key, value, ex=ttl_seconds)
    except Exception:
        pass
