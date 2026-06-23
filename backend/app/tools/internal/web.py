"""Web search + fetch tools.

Gives agents (lead generation, GTM, future research) read access to the open web.
`web_search` calls a search-API provider (Tavily by default; provider-agnostic via
SEARCH_PROVIDER); `fetch_url` retrieves and extracts the readable text of a page.

Both degrade gracefully: if no key is configured they return an actionable error
string rather than raising, so the agent can report the gap instead of crashing.
"""

import re

import httpx
from langchain_core.tools import tool

from ...core.config import get_settings
from ...registries.tool_registry import register_tool

_MAX_CHARS = 4000  # mirror the REST adapter's truncation


def _strip_html(html: str) -> str:
    """Naive readable-text extraction: drop scripts/styles/tags, collapse whitespace."""
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&[a-z]+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@register_tool
@tool
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web and return ranked results (title, URL, snippet).

    Use to find companies, people, news, pricing, or any public info. Follow up with
    fetch_url to read a promising result in full.
    """
    s = get_settings()
    if not s.search_api_key:
        return (
            "Web search is not configured. Set SEARCH_API_KEY (and optionally "
            "SEARCH_PROVIDER, default 'tavily') in the backend environment."
        )

    provider = (s.search_provider or "tavily").lower()
    max_results = max(1, min(int(max_results or 5), 10))
    try:
        if provider == "tavily":
            resp = httpx.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": s.search_api_key,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "basic",
                },
                timeout=30,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            items = [
                (r.get("title", ""), r.get("url", ""), r.get("content", ""))
                for r in results
            ]
        elif provider == "serper":
            resp = httpx.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": s.search_api_key},
                json={"q": query, "num": max_results},
                timeout=30,
            )
            resp.raise_for_status()
            results = resp.json().get("organic", [])[:max_results]
            items = [
                (r.get("title", ""), r.get("link", ""), r.get("snippet", ""))
                for r in results
            ]
        else:
            return f"Unknown SEARCH_PROVIDER '{provider}'. Supported: tavily, serper."
    except Exception as e:
        return f"Web search failed: {e}"

    if not items:
        return f"No results for: {query}"
    lines = [f"{i+1}. {t}\n   {u}\n   {c[:300]}" for i, (t, u, c) in enumerate(items)]
    return "\n\n".join(lines)


@register_tool
@tool
def fetch_url(url: str) -> str:
    """Fetch a URL and return its readable text content (HTML tags stripped, truncated).

    Use to read a page found via web_search — e.g. a company's about/pricing page — to
    extract firmographics, contacts, or other details.
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        resp = httpx.get(
            url,
            timeout=30,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AgentPlatform/1.0)"},
        )
        resp.raise_for_status()
    except Exception as e:
        return f"Could not fetch {url}: {e}"

    ctype = resp.headers.get("content-type", "")
    body = resp.text if "html" in ctype or not ctype else resp.text
    text = _strip_html(body)
    if len(text) > _MAX_CHARS:
        text = text[:_MAX_CHARS] + "\n…[truncated]"
    return f"URL: {url}\n\n{text}"
