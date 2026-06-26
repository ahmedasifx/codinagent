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

from ...core import cache
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


# ── Crawl4AI sidecar (JS-rendering crawler) ──────────────────────────────────────
_CRAWL_MAX_CHARS = 8000  # crawled markdown is cleaner/denser than raw HTML; allow more


def _crawl4ai_headers() -> dict[str, str]:
    token = get_settings().crawl4ai_token
    return {"Authorization": f"Bearer {token}"} if token else {}


def _markdown_of(result: dict) -> str:
    """Pull the best markdown out of a Crawl4AI result (shape varies by version)."""
    md = result.get("markdown")
    if isinstance(md, dict):
        md = md.get("fit_markdown") or md.get("raw_markdown") or ""
    return md or result.get("cleaned_html") or ""


def _post_crawl(urls: list[str], crawler_params: dict) -> list[dict] | str:
    """POST to the sidecar /crawl. Returns a list of per-URL results, or an error string."""
    s = get_settings()
    if not s.crawl4ai_url:
        return (
            "Crawl4AI is not configured (CRAWL4AI_URL unset). Use fetch_url for static "
            "pages, or configure the crawl4ai sidecar for JS-rendered sites."
        )
    payload = {
        "urls": urls,
        "crawler_config": {"type": "CrawlerRunConfig", "params": crawler_params},
    }
    try:
        resp = httpx.post(
            f"{s.crawl4ai_url.rstrip('/')}/crawl",
            json=payload,
            headers=_crawl4ai_headers(),
            timeout=150,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return f"Crawl failed: {e}"
    results = data.get("results")
    if results is None:
        results = data if isinstance(data, list) else [data]
    return results


@register_tool
@tool
def scrape_page(url: str) -> str:
    """Fetch a page with a real browser (JS rendered) and return clean markdown.

    Use for modern/JS-heavy sites where fetch_url returns an empty shell (most SaaS
    company sites). Slower than fetch_url — prefer fetch_url for simple static pages.
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    key = f"scrape:{url}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    results = _post_crawl([url], {"cache_mode": "bypass"})
    if isinstance(results, str):
        return results
    if not results or not results[0].get("success", True):
        return f"Could not scrape {url} (no content returned)."

    text = _markdown_of(results[0]).strip()
    if len(text) > _CRAWL_MAX_CHARS:
        text = text[:_CRAWL_MAX_CHARS] + "\n…[truncated]"
    out = f"URL: {url}\n\n{text}"
    cache.set(key, out)
    return out


@register_tool
@tool
def crawl_site(url: str, max_pages: int = 5) -> str:
    """Crawl a site a few links deep (JS rendered) and return each page's markdown.

    Use to gather a company's about/team/pricing/contact pages in one call for
    enrichment. Capped at max_pages (default 5) to bound cost/latency.
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    max_pages = max(1, min(int(max_pages or 5), 15))

    key = f"crawl:{url}:{max_pages}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    results = _post_crawl(
        [url],
        {
            "cache_mode": "bypass",
            "deep_crawl_strategy": {
                "type": "BFSDeepCrawlStrategy",
                "params": {"max_depth": 1, "max_pages": max_pages},
            },
        },
    )
    if isinstance(results, str):
        return results
    if not results:
        return f"Could not crawl {url} (no pages returned)."

    parts = []
    for r in results:
        md = _markdown_of(r).strip()
        if md:
            parts.append(f"### {r.get('url', url)}\n{md[:3000]}")
    if not parts:
        return f"Crawled {url} but extracted no readable content."
    out = "\n\n".join(parts)
    if len(out) > _CRAWL_MAX_CHARS:
        out = out[:_CRAWL_MAX_CHARS] + "\n…[truncated]"
    cache.set(key, out)
    return out
