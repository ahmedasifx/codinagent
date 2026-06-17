"""Long-term memory tools — let any agent persist and recall facts across turns."""

from langchain_core.tools import tool

from ...memory import store
from ...registries.tool_registry import register_tool


@register_tool
@tool
def save_memory(content: str, namespace: str = "default") -> str:
    """Save an important fact to long-term memory for later recall.

    Use for durable facts the user will want remembered across conversations
    (preferences, names, decisions). `namespace` groups related memories.
    """
    ok = store.save(content, namespace=namespace)
    return "Saved to memory." if ok else "Memory unavailable (no database configured)."


@register_tool
@tool
def recall_memory(query: str, k: int = 3, namespace: str = "default") -> str:
    """Recall relevant facts previously saved to long-term memory.

    Returns the top-k most relevant memories for the query (semantic when embeddings
    are available, else keyword match).
    """
    hits = store.recall(query, k=k, namespace=namespace)
    if not hits:
        return "No relevant memories found."
    return "\n".join(f"- {h}" for h in hits)
