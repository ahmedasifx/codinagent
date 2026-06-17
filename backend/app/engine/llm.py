"""LLM access via OpenRouter (OpenAI-compatible). Migrated from the original agent.py."""

from langchain_openai import ChatOpenAI

from ..core.config import get_settings


def get_llm(streaming: bool = True, model: str | None = None) -> ChatOpenAI:
    s = get_settings()
    primary = model or s.openrouter_model

    # OpenRouter native fallback: try [primary, *fallbacks] in order on error/429.
    fallbacks = [m for m in s.fallback_models if m != primary]
    extra_body = {"models": [primary, *fallbacks]} if fallbacks else None

    return ChatOpenAI(
        model=primary,
        openai_api_key=s.openrouter_api_key,
        openai_api_base=s.openrouter_base_url,
        streaming=streaming,
        temperature=0,
        max_retries=4,
        extra_body=extra_body,
        model_kwargs={
            "extra_headers": {
                "HTTP-Referer": "https://coding-agent.local",
                "X-Title": "AI Agent Platform",
            }
        },
    )
