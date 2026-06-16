"""Tool registry — unifies code-defined built-in tools and DB-defined custom tools.

Built-ins are registered at import time via `register_tool` (decorator over a
LangChain `@tool`). Custom tools are loaded from the `tools` table on demand and
built through the adapter matching `tools.type` (see app/tools/adapters/).
"""

from langchain_core.tools import BaseTool

from ..tools.adapters.base import InternalToolAdapter, ToolAdapter


class ToolRegistry:
    def __init__(self) -> None:
        self._internal: dict[str, ToolAdapter] = {}

    # ── built-ins ──
    def register(self, tool: BaseTool) -> BaseTool:
        self._internal[tool.name] = InternalToolAdapter(tool)
        return tool

    def has(self, slug: str) -> bool:
        return slug in self._internal

    def adapter(self, slug: str) -> ToolAdapter:
        if slug in self._internal:
            return self._internal[slug]
        adapter = self._load_custom(slug)
        if adapter is None:
            raise KeyError(f"Unknown tool: {slug}")
        return adapter

    def get_langchain_tool(self, slug: str) -> BaseTool:
        return self.adapter(slug).to_langchain_tool()

    def resolve(self, slugs: list[str]) -> list[BaseTool]:
        """Resolve a list of slugs to bound LangChain tools, skipping unknown ones."""
        out: list[BaseTool] = []
        for slug in slugs:
            try:
                out.append(self.get_langchain_tool(slug))
            except KeyError:
                continue
        return out

    def list_internal(self) -> list[str]:
        return sorted(self._internal.keys())

    # ── custom (DB-backed); built lazily to avoid importing adapters with deps ──
    def _load_custom(self, slug: str) -> ToolAdapter | None:
        from ..core.db import db_enabled, session_scope

        if not db_enabled():
            return None
        from ..models import Tool
        from ..tools.adapters import build_adapter_for_row

        with session_scope() as session:
            row = session.query(Tool).filter(Tool.slug == slug).one_or_none()
            if row is None:
                return None
            return build_adapter_for_row(row)


TOOL_REGISTRY = ToolRegistry()


def register_tool(tool: BaseTool) -> BaseTool:
    """Decorator-style registration; stack above (after) a `@tool` definition."""
    return TOOL_REGISTRY.register(tool)
