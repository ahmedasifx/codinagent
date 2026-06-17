"""Long-term memory store.

Embeddings via the OpenRouter (OpenAI-compatible) endpoint when available; recall uses
pgvector cosine distance when embeddings exist, otherwise a keyword (ILIKE) fallback so
memory still works if the provider has no embeddings endpoint. All DB access is guarded
by db_enabled() — in DB-less mode save/recall are no-ops.
"""

from ..core.config import get_settings
from ..core.db import db_enabled, session_scope

_embeddings = None
_embeddings_failed = False


def _get_embeddings():
    global _embeddings, _embeddings_failed
    if _embeddings is not None or _embeddings_failed:
        return _embeddings
    try:
        from langchain_openai import OpenAIEmbeddings

        s = get_settings()
        _embeddings = OpenAIEmbeddings(
            model=s.embedding_model,
            openai_api_key=s.openrouter_api_key,
            openai_api_base=s.openrouter_base_url,
        )
    except Exception:
        _embeddings_failed = True
    return _embeddings


def embed(text: str) -> list[float] | None:
    emb = _get_embeddings()
    if emb is None:
        return None
    try:
        return emb.embed_query(text)
    except Exception:
        return None


def save(content: str, namespace: str = "default", agent_id=None, meta: dict | None = None) -> bool:
    if not db_enabled():
        return False
    from ..models import Memory

    vec = embed(content)
    with session_scope() as session:
        session.add(
            Memory(namespace=namespace, content=content, embedding=vec, meta=meta or {})
        )
    return True


def recall(query: str, k: int = 3, namespace: str = "default") -> list[str]:
    if not db_enabled():
        return []
    from ..models import Memory

    with session_scope() as session:
        base = session.query(Memory).filter(Memory.namespace == namespace)
        vec = embed(query)
        if vec is not None:
            try:
                rows = (
                    base.filter(Memory.embedding.isnot(None))
                    .order_by(Memory.embedding.cosine_distance(vec))
                    .limit(k)
                    .all()
                )
                if rows:
                    return [r.content for r in rows]
            except Exception:
                pass  # pgvector unavailable → keyword fallback
        # Keyword fallback: most recent rows matching any query word
        like = f"%{query.strip().split(' ')[0]}%" if query.strip() else "%"
        rows = (
            base.filter(Memory.content.ilike(like))
            .order_by(Memory.created_at.desc())
            .limit(k)
            .all()
        )
        return [r.content for r in rows]
