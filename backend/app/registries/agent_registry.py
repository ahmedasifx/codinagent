"""Agent registry — code-defined core agents + DB-defined custom agents.

Resolves an agent's skills + tools into a compiled LangGraph execution graph and
caches it (keyed by slug). DB-defined custom agents are loaded on demand.
"""

from .types import AgentDef


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, AgentDef] = {}
        self._graph_cache: dict[str, object] = {}

    def register(self, agent: AgentDef) -> AgentDef:
        self._agents[agent.slug] = agent
        return agent

    def get(self, slug: str) -> AgentDef:
        if slug in self._agents:
            return self._agents[slug]
        custom = self._load_custom(slug)
        if custom is None:
            raise KeyError(f"Unknown agent: {slug}")
        return custom

    def list(self) -> list[AgentDef]:
        return list(self._agents.values())

    def compiled_graph(self, slug: str):
        """Build + cache the per-agent graph. Custom agents are not cached (they can
        change between calls)."""
        from ..engine.graph import build_agent_graph

        agent = self.get(slug)
        if not agent.is_core:
            return build_agent_graph(agent)
        if slug not in self._graph_cache:
            self._graph_cache[slug] = build_agent_graph(agent)
        return self._graph_cache[slug]

    def invalidate(self, slug: str) -> None:
        self._graph_cache.pop(slug, None)

    def _load_custom(self, slug: str) -> AgentDef | None:
        from ..core.db import db_enabled, session_scope

        if not db_enabled():
            return None
        from ..models import Agent

        with session_scope() as session:
            row = session.query(Agent).filter(Agent.slug == slug).one_or_none()
            if row is None:
                return None
            # Skill/tool slugs live in config so a custom agent can reference BOTH
            # code-defined (core) and DB-defined slugs uniformly (no FK constraint).
            cfg = row.config or {}
            return AgentDef(
                slug=row.slug,
                name=row.name,
                description=row.description,
                instructions=row.instructions,
                personality=row.personality,
                system_prompt=row.system_prompt,
                model=row.model,
                skills=cfg.get("skills", []),
                tools=cfg.get("tools", []),
                config=cfg,
                is_core=False,
            )


AGENT_REGISTRY = AgentRegistry()


def register_agent(agent: AgentDef) -> AgentDef:
    return AGENT_REGISTRY.register(agent)
