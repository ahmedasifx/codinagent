"""LLM access via OpenRouter (OpenAI-compatible). Migrated from the original agent.py."""

from langchain_openai import ChatOpenAI

from ..core.config import get_settings


def get_llm(streaming: bool = True, model: str | None = None) -> ChatOpenAI:
    s = get_settings()
    return ChatOpenAI(
        model=model or s.openrouter_model,
        openai_api_key=s.openrouter_api_key,
        openai_api_base=s.openrouter_base_url,
        streaming=streaming,
        temperature=0,
        model_kwargs={
            "extra_headers": {
                "HTTP-Referer": "https://coding-agent.local",
                "X-Title": "AI Agent Platform",
            }
        },
    )
